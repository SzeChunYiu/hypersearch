import copy
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hypersearch.store import Store
from hypersearch.study import execute
from hypersearch.study_contract import wrapper
from hypersearch.study_receipts import trusted_receipt
from study_fixture import make


class StableReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.core, self.consumer, self.bundle = make(self.root)
        self.patch = patch("hypersearch.study.CORE_ROOT", self.core); self.patch.start()
        self.db = self.root / "tasks.sqlite"
        self.original = self.run_task(wrapper(self.bundle), "original")
        self.first = self.run_task(wrapper(self.bundle, parent=self.original["receipt_sha256"],
                                      replay_id="stable-id"), "first", self.original)

    def tearDown(self):
        self.patch.stop(); self.temp.cleanup()

    def run_task(self, execution, label, parent=None, consumer=None):
        parent_value = None if parent is None else trusted_receipt(
            Path(parent["receipt_path"]).read_bytes(), parent["receipt_sha256"])
        return execute(execution, consumer_root=consumer or self.consumer, database=self.db,
                       export=self.root / label, parent_receipt=parent_value)

    def test_same_replay_id_cannot_change_valid_parent(self):
        before = Store(self.db, max_attempts=5).snapshot()
        changed = wrapper(self.bundle, parent=self.first["receipt_sha256"], replay_id="stable-id")
        with self.assertRaisesRegex(ValueError, "immutable"):
            self.run_task(changed, "changed-parent", self.first)
        self.assertEqual(Store(self.db, max_attempts=5).snapshot(), before)
        self.assertFalse((self.root / "changed-parent").exists())
        same = wrapper(self.bundle, parent=self.original["receipt_sha256"], replay_id="stable-id")
        self.assertEqual(self.run_task(same, "same-again", self.original)["execution"], "not_rerun")

    def test_same_replay_id_cannot_change_valid_bundle(self):
        other = self.root / "other"; other.mkdir()
        _, consumer, bundle = make(other, multi=True)
        verifier = bundle["instrument"]["verifier"]
        bundle["instrument"] = copy.deepcopy(self.bundle["instrument"])
        bundle["instrument"]["verifier"] = verifier
        parent = self.run_task(wrapper(bundle), "other-original", consumer=consumer)
        before = Store(self.db, max_attempts=5).snapshot()
        changed = wrapper(bundle, parent=parent["receipt_sha256"], replay_id="stable-id")
        with self.assertRaisesRegex(ValueError, "immutable"):
            self.run_task(changed, "changed-bundle", parent, consumer=consumer)
        self.assertEqual(Store(self.db, max_attempts=5).snapshot(), before)
        self.assertFalse((self.root / "changed-bundle").exists())

    def test_changed_lineage_race_is_one_atomic_binding(self):
        parents = (self.original, self.first)
        def attempt(index):
            parent = parents[index]
            execution = wrapper(self.bundle, parent=parent["receipt_sha256"], replay_id="racing-id")
            try:
                return self.run_task(execution, "race-" + str(index), parent)["execution"]
            except ValueError as error:
                self.assertIn("immutable", str(error))
                return "conflict"
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(attempt, range(2)))
        self.assertCountEqual(outcomes, ["completed", "conflict"])
        state = Store(self.db, max_attempts=5).snapshot()
        self.assertEqual(state["budget"]["spent"], 3)
        self.assertEqual(len(state["tasks"]), 3)

    def test_same_wrapper_race_never_grants_two_attempts(self):
        execution = wrapper(self.bundle, parent=self.original["receipt_sha256"], replay_id="duplicate-id")
        def attempt(index):
            return self.run_task(execution, "duplicate-" + str(index), self.original)["execution"]
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(attempt, range(2)))
        self.assertIn("completed", outcomes)
        self.assertTrue(set(outcomes) <= {"completed", "not_started", "not_rerun"})
        self.assertEqual(Store(self.db, max_attempts=5).snapshot()["budget"]["spent"], 3)
        self.assertEqual(self.run_task(execution, "duplicate-final", self.original)["execution"], "not_rerun")
