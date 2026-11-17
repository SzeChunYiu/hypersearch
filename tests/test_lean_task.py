from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from hypersearch.lean_task import prepare_task, register_candidate
from hypersearch.lean_request import question_digest
from hypersearch.store import Store
from hypersearch.study_json import parse
import test_lean_request as request_fixtures
from test_lean_snapshot import artifact


class LeanTaskTests(unittest.TestCase):
    def setUp(self):
        fixture = request_fixtures.LeanRequestTests()
        fixture.setUp()
        self.question = fixture.question
        self.arguments = {"expected_question_sha256": fixture.expected,
                          "challenge_snapshot": fixture.challenge,
                          "candidate": fixture.candidate,
                          "limits": {"timeout_seconds": 10, "memory_megabytes": 256}}
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / "tasks.sqlite", max_attempts=3)

    def test_registers_immutable_pending_task_without_grant(self):
        self.store.submit("unrelated", {"input": "untouched"})
        result = register_candidate(self.store, self.question, **self.arguments)
        state = self.store.snapshot()
        self.assertEqual(state["budget"]["spent"], 0)
        self.assertEqual(len(state["results"]), 0)
        self.assertEqual({t["state"] for t in state["tasks"]}, {"pending"})
        self.assertEqual(set(result), {"task_id", "specification_sha256", "scope"})
        before = deepcopy(state)
        self.assertEqual(result, register_candidate(self.store, self.question, **self.arguments))
        self.assertEqual(self.store.snapshot(), before)

    def test_rejected_requests_leave_store_unchanged(self):
        before = self.store.snapshot()
        for field in ("declaration", "runtime_sha256"):
            question = deepcopy(self.question)
            question[field] = "Other" if field == "declaration" else "a" * 64
            args = deepcopy(self.arguments)
            args["candidate"]["question_sha256"] = question_digest(question)
            with self.assertRaises(ValueError):
                register_candidate(self.store, question, **args)
            self.assertEqual(self.store.snapshot(), before)
        for value in (True, 0, 3601):
            args = deepcopy(self.arguments)
            args["limits"]["timeout_seconds"] = value
            with self.assertRaises(ValueError):
                register_candidate(self.store, self.question, **args)
            self.assertEqual(self.store.snapshot(), before)

    def test_source_or_limits_changes_produce_distinct_tasks(self):
        original, _ = prepare_task(self.question, **self.arguments)
        args = deepcopy(self.arguments)
        args["limits"]["timeout_seconds"] += 1
        self.assertNotEqual(original, prepare_task(self.question, **args)[0])
        args = deepcopy(self.arguments)
        args["candidate"]["source_snapshot"]["files"] = [artifact("Solution.lean", b"-- altered\n")]
        self.assertNotEqual(original, prepare_task(self.question, **args)[0])

    def test_file_order_does_not_duplicate_work_and_bytes_are_detached(self):
        args = deepcopy(self.arguments)
        files = args["candidate"]["source_snapshot"]["files"]
        files.append(artifact("Helper.lean"))
        task, raw = prepare_task(self.question, **args)
        files.reverse()
        self.assertEqual((task, raw), prepare_task(self.question, **args))
        args["limits"]["timeout_seconds"] = 99
        self.assertEqual(parse(raw)["limits"]["timeout_seconds"], 10)


if __name__ == "__main__":
    unittest.main()
