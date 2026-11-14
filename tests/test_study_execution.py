import copy
import json
import os
from pathlib import Path
import subprocess
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from hypersearch.store import StaleLease, Store
from hypersearch.study import execute, run_verifier
from hypersearch.study_contract import wrapper
from hypersearch.study_json import digest, encode
from hypersearch.study_receipts import export_receipt, trusted_receipt, validate_receipt
from study_fixture import git, make


class StudyExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.core, self.consumer, self.bundle = make(self.root)
        self.patch = patch("hypersearch.study.CORE_ROOT", self.core)
        self.patch.start()
        self.db = self.root / "run.sqlite"
        self.export = self.root / "receipts"

    def tearDown(self):
        self.patch.stop(); self.temp.cleanup()

    def run_study(self, value=None, **kwargs):
        return execute(value or wrapper(self.bundle), consumer_root=self.consumer,
                       database=self.db, export=kwargs.pop("export", self.export), **kwargs)

    def receipt(self, result):
        raw = Path(result["receipt_path"]).read_bytes()
        return trusted_receipt(raw, result["receipt_sha256"])

    def test_known_answer_dedup_replay_and_external_commitment(self):
        first = self.run_study()
        receipt = self.receipt(first)
        self.assertEqual(receipt["outcome"]["verification"]["lower_bound"], 4)
        self.assertEqual(receipt["execution"]["bundle"], self.bundle)
        self.assertEqual(self.run_study()["execution"], "not_rerun")
        replay = wrapper(self.bundle, parent=first["receipt_sha256"], replay_id="second-environment")
        result = self.run_study(replay, parent_receipt=receipt, export=self.root / "replay")
        self.assertTrue(self.receipt(result)["replay_matches_parent"])
        self.assertEqual(Store(self.db, max_attempts=5).snapshot()["budget"]["spent"], 2)
        changed = copy.deepcopy(receipt); changed["diagnostics"] = "rewritten"
        with self.assertRaisesRegex(ValueError, "external digest"):
            trusted_receipt(encode(changed), first["receipt_sha256"])
        with self.assertRaises(ValueError):
            trusted_receipt(encode(receipt), "0" * 64)

    def test_wrong_pin_hidden_dirty_and_invalid_admission_leave_database_unchanged(self):
        store = Store(self.db, max_attempts=5)
        store.submit("a-unrelated", {"untouched": True})
        before = store.snapshot()
        bad = copy.deepcopy(self.bundle); bad["instrument"]["commit"] = "0" * 40
        with self.assertRaises(ValueError):
            self.run_study(wrapper(bad))
        path = self.core / "src/hypersearch/cli.py"
        git(self.core, "update-index", "--assume-unchanged", "src/hypersearch/cli.py")
        original = path.read_bytes()
        path.write_bytes(original + b"# hidden mutation\n")
        self.assertEqual(git(self.core, "status", "--porcelain"), "")
        with self.assertRaisesRegex(ValueError, "working bytes"):
            self.run_study()
        self.assertEqual(store.snapshot(), before)
        self.assertFalse(self.export.exists())
        path.write_bytes(original)
        git(self.core, "update-index", "--no-assume-unchanged", "src/hypersearch/cli.py")
        self.assertEqual(self.run_study()["outcome_status"], "VERIFIED_WITNESS")
        self.assertEqual(store.snapshot()["tasks"][0]["state"], "pending")

    def test_runtime_failure_and_malformed_output_are_not_negative_mathematics(self):
        for index, failure in enumerate((ValueError("bad child JSON"), OSError("worker launch failure"))):
            self.db = self.root / f"failure-{index}.sqlite"
            with patch("hypersearch.study.run_verifier", side_effect=failure):
                result = self.run_study()
            receipt = self.receipt(result)
            self.assertEqual(receipt["outcome"], {"status": "EXECUTION_FAILED", "verification": None})
            # Repeated identical requests return committed evidence, not a free retry.
            self.assertEqual(self.run_study()["execution"], "not_rerun")
        self.assertEqual(Store(self.db, max_attempts=5).snapshot()["budget"]["spent"], 1)

    def test_timeout_is_incomplete(self):
        with patch("hypersearch.study.subprocess.run", side_effect=subprocess.TimeoutExpired("fixture", 30)):
            result, diagnostics = run_verifier(self.bundle, self.core)
        self.assertEqual(result, {"status": "INCOMPLETE", "verification": None})
        self.assertIn("timeout", diagnostics)
        with patch("hypersearch.study.run_verifier", return_value=(result, diagnostics)):
            receipt = self.receipt(self.run_study())
        self.assertEqual(receipt["outcome"]["status"], "INCOMPLETE")

    def test_stale_completion_never_exports_and_remains_charged(self):
        with patch("hypersearch.study.Store.complete", side_effect=StaleLease("expired")):
            with self.assertRaises(StaleLease):
                self.run_study()
        self.assertFalse(self.export.exists())
        state = Store(self.db, max_attempts=5).snapshot()
        self.assertEqual(state["budget"]["spent"], 1)
        self.assertEqual(state["results"], [])

    def test_export_failure_recovers_without_rerun_and_corruption_is_preserved(self):
        with patch("hypersearch.study.export_receipt", side_effect=OSError("interrupted export")):
            with self.assertRaises(OSError):
                self.run_study()
        result = self.run_study()
        self.assertEqual(result["execution"], "not_rerun")
        receipt = self.receipt(result)
        path = Path(result["receipt_path"]); path.write_bytes(b"damaged")
        with self.assertRaisesRegex(ValueError, "collision or corruption"):
            export_receipt(receipt, self.export)
        self.assertEqual(path.read_bytes(), b"damaged")
        self.assertEqual(Store(self.db, max_attempts=5).snapshot()["budget"]["spent"], 1)

    def test_corrupt_completed_result_and_task_identity_refuse_reexport(self):
        self.run_study()
        store = Store(self.db, max_attempts=5)
        before = store.snapshot()
        with sqlite3.connect(self.db) as database:
            database.execute("UPDATE results SET digest=?", ("0" * 64,))
        with self.assertRaisesRegex(ValueError, "external digest"):
            self.run_study(export=self.root / "bad-result")
        self.assertFalse((self.root / "bad-result").exists())
        with sqlite3.connect(self.db) as database:
            database.execute("UPDATE results SET digest=?", (before["results"][0]["digest"],))
            database.execute("UPDATE tasks SET digest=?", ("0" * 64,))
        with self.assertRaisesRegex(ValueError, "task identity"):
            self.run_study(export=self.root / "bad-task")
        self.assertFalse((self.root / "bad-task").exists())
        self.assertEqual(store.snapshot()["budget"]["spent"], 1)

    def test_malformed_completed_child_output_is_execution_failure(self):
        forged = {"status": "VERIFIED_WITNESS", "verification": {"verified": True, "lower_bound": 999}}
        with patch("hypersearch.study.run_verifier", return_value=(forged, "")):
            receipt = self.receipt(self.run_study())
        self.assertEqual(receipt["outcome"], {"status": "EXECUTION_FAILED", "verification": None})

    def test_sqlite_sidecars_cannot_alias_inputs_exports_or_symlinks(self):
        for suffix in ("-journal", "-wal", "-shm"):
            sidecar = Path(str(self.db) + suffix)
            sidecar.write_bytes(b"preserve input")
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                self.run_study(inputs=(sidecar,))
            self.assertEqual(sidecar.read_bytes(), b"preserve input")
            self.assertFalse(self.db.exists())
            sidecar.unlink()
            with self.assertRaises(ValueError):
                self.run_study(export=sidecar)
            target = self.consumer / "certificate.json"
            original = target.read_bytes()
            sidecar.symlink_to(target)
            with self.assertRaises(ValueError):
                self.run_study()
            self.assertEqual(target.read_bytes(), original)
            sidecar.unlink()
            os.link(target, sidecar)
            with self.assertRaises(ValueError):
                self.run_study()
            self.assertEqual(target.read_bytes(), original)
            sidecar.unlink()

    def test_database_hardlink_cannot_modify_pinned_source(self):
        source = self.consumer / "pinned.sqlite"
        with sqlite3.connect(source) as database:
            database.execute("CREATE TABLE original (value TEXT)")
        git(self.consumer, "add", "pinned.sqlite")
        git(self.consumer, "commit", "-m", "Pin synthetic database")
        self.bundle["consumer"]["commit"] = git(self.consumer, "rev-parse", "HEAD")
        original = source.read_bytes()
        os.link(source, self.db)
        with self.assertRaisesRegex(ValueError, "hardlinked"):
            self.run_study()
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual(git(self.consumer, "status", "--porcelain"), "")

    def test_outputs_cannot_overlap_sources_or_each_other(self):
        for database, output in ((self.consumer / "run.sqlite", self.export),
                                 (self.db, self.core / "receipts"), (self.db, self.db)):
            with self.subTest(database=database, output=output), self.assertRaises(ValueError):
                execute(wrapper(self.bundle), consumer_root=self.consumer, database=database, export=output)
        self.assertFalse(self.db.exists())


class MultiwiseStudyTests(unittest.TestCase):
    def test_bounded_positive_and_completed_refutation(self):
        for false in (False, True):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                core, consumer, bundle = make(root, multi=True, false=false)
                with patch("hypersearch.study.CORE_ROOT", core):
                    result = execute(wrapper(bundle), consumer_root=consumer,
                                     database=root / "tasks.sqlite", export=root / "receipts")
                receipt = trusted_receipt(Path(result["receipt_path"]).read_bytes(), result["receipt_sha256"])
                self.assertEqual(receipt["outcome"]["status"], "REFUTED_WITNESS" if false else "VERIFIED_WITNESS")
                if false:
                    self.assertNotIn("lower_bound", receipt["outcome"]["verification"])
