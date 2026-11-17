from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from hypersearch.lean_task import prepare_task, register_candidate, read_current_candidate
from hypersearch.lean_request import question_digest
from hypersearch.store import Store, StaleLease
from hypersearch.study_json import parse, encode, digest
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

    def grant_fixture(self):
        self.now = 1000.0
        self.store.clock = lambda: self.now
        record = register_candidate(self.store, self.question, **self.arguments)
        lease = self.store.acquire("fixture-worker", 10, task_id=record["task_id"])
        expected = {"expected_task_sha256": record["specification_sha256"],
                    "expected_question_sha256": self.arguments["expected_question_sha256"]}
        return lease, expected

    def test_live_lease_revalidates_without_store_mutation(self):
        lease, expected = self.grant_fixture()
        before = self.store.snapshot()
        value = read_current_candidate(self.store, lease, **expected)
        self.assertEqual(value, parse(lease.spec_json.encode()))
        self.assertEqual(self.store.snapshot(), before)
        value["scope"] = "tampered"
        self.assertEqual(read_current_candidate(self.store, lease, **expected)["scope"],
                         "uncommissioned_lean_candidate")

    def test_expired_reclaimed_and_completed_lease_refused(self):
        lease, expected = self.grant_fixture()
        self.now = lease.expires_at
        with self.assertRaises(StaleLease):
            read_current_candidate(self.store, lease, **expected)
        newer = self.store.acquire("replacement", 10, task_id=lease.task_id)
        with self.assertRaises(StaleLease):
            read_current_candidate(self.store, lease, **expected)
        read_current_candidate(self.store, newer, **expected)
        self.store.complete(newer, {"scope": "synthetic_no_proof"})
        with self.assertRaises(StaleLease):
            read_current_candidate(self.store, newer, **expected)
        self.assertEqual(self.store.snapshot()["budget"]["spent"], 2)

    def test_lease_field_substitution_refused(self):
        lease, expected = self.grant_fixture()
        before = self.store.snapshot()
        for changes in ({"worker": "other"}, {"fence": lease.fence + 1},
                        {"expires_at": lease.expires_at + 1}, {"task_id": "unrelated"},
                        {"spec_json": "{}"}, {"spec_digest": "0" * 64}):
            with self.subTest(changes=changes), self.assertRaises(StaleLease):
                read_current_candidate(self.store, replace(lease, **changes), **expected)
        self.assertEqual(self.store.snapshot(), before)

    def test_external_expected_id_cannot_be_replaced_by_lease(self):
        lease, expected = self.grant_fixture()
        for field in expected:
            bad = {**expected, field: "0" * 64}
            with self.subTest(field=field), self.assertRaises(ValueError):
                read_current_candidate(self.store, lease, **bad)

    def test_self_consistent_but_invalid_stored_scope_is_refused(self):
        _, raw = prepare_task(self.question, **self.arguments)
        value = parse(raw)
        value["scope"] = "formal_proof"
        changed_digest = digest(encode(value))
        task_id = "lean-draft-" + changed_digest
        self.store.submit(task_id, value)
        lease = self.store.acquire("fixture-worker", 10, task_id=task_id)
        with self.assertRaises(ValueError):
            read_current_candidate(self.store, lease,
                expected_task_sha256=changed_digest,
                expected_question_sha256=self.arguments["expected_question_sha256"])


if __name__ == "__main__":
    unittest.main()
