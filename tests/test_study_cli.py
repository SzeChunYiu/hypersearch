import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from hypersearch.study_json import encode
from hypersearch.store import Store
from study_fixture import make


def command(core, *arguments):
    return subprocess.run([sys.executable, "-B", "-S", "-m", "hypersearch", *map(str, arguments)],
                          env={"PATH": os.defpath, "PYTHONPATH": str(core / "src"),
                               "PYTHONDONTWRITEBYTECODE": "1"},
                          capture_output=True, text=True, timeout=90)


class StudyCliTests(unittest.TestCase):
    def test_public_cli_original_and_digest_committed_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            core, consumer, bundle = make(root)
            source = root / "bundle.json"; source.write_bytes(encode(bundle))
            result = command(core, "run-study", "--bundle", source, "--consumer-root", consumer,
                             "--db", root / "tasks.sqlite", "--export", root / "receipts")
            self.assertEqual(result.returncode, 0, result.stderr)
            first = json.loads(result.stdout)
            result = command(core, "replay-study", "--receipt", first["receipt_path"],
                             "--expected-receipt-sha256", first["receipt_sha256"], "--replay-id", "independent-replay",
                             "--consumer-root", consumer, "--db", root / "tasks.sqlite", "--export", root / "replay")
            self.assertEqual(result.returncode, 0, result.stderr)
            replay = json.loads(result.stdout)
            self.assertTrue(replay["replay_matches_parent"])
            before = Store(root / "tasks.sqlite", max_attempts=5).snapshot()
            changed = command(core, "replay-study", "--receipt", replay["receipt_path"],
                              "--expected-receipt-sha256", replay["receipt_sha256"], "--replay-id", "independent-replay",
                              "--consumer-root", consumer, "--db", root / "tasks.sqlite", "--export", root / "changed-lineage")
            self.assertEqual(changed.returncode, 2)
            self.assertIn("immutable", changed.stderr)
            self.assertEqual(Store(root / "tasks.sqlite", max_attempts=5).snapshot(), before)
            self.assertFalse((root / "changed-lineage").exists())
            refused = command(core, "replay-study", "--receipt", first["receipt_path"],
                              "--expected-receipt-sha256", "0" * 64, "--replay-id", "tampered",
                              "--consumer-root", consumer, "--db", root / "refused.sqlite", "--export", root / "refused")
            self.assertEqual(refused.returncode, 2)
            self.assertFalse((root / "refused.sqlite").exists())

    def test_cli_refutation_is_distinct_from_malformed_refusal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            core, consumer, bundle = make(root, multi=True, false=True)
            source = root / "bundle.json"; source.write_bytes(encode(bundle))
            result = command(core, "run-study", "--bundle", source, "--consumer-root", consumer,
                             "--db", root / "tasks.sqlite", "--export", root / "receipts")
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertEqual(json.loads(result.stdout)["outcome_status"], "REFUTED_WITNESS")
            source.write_bytes(b'{"schema":1,"schema":2}')
            result = command(core, "run-study", "--bundle", source, "--consumer-root", consumer,
                             "--db", root / "bad.sqlite", "--export", root / "bad")
            self.assertEqual(result.returncode, 2)
            self.assertFalse((root / "bad.sqlite").exists())
