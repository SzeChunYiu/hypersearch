from copy import deepcopy
import unittest

from hypersearch.lean_request import (CANDIDATE_SCHEMA, QUESTION_SCHEMA, CHECKERS,
                                     bind_candidate, question_digest)
from hypersearch.lean_snapshot import snapshot_digest
from test_lean_snapshot import artifact, snapshot


class LeanRequestTests(unittest.TestCase):
    def setUp(self):
        self.challenge = snapshot(artifact("Challenge.lean"))
        self.question = {
            "schema": QUESTION_SCHEMA, "challenge_module": "Challenge",
            "solution_module": "Solution", "declaration": "demo",
            "challenge_snapshot_sha256": snapshot_digest(self.challenge),
            "dependency_snapshot_sha256": "1" * 64, "runtime_sha256": "2" * 64,
            "evaluator_sha256": "3" * 64, "allowed_axioms": [],
            "checkers": {name: "4" * 64 for name in CHECKERS}}
        self.expected = question_digest(self.question)
        self.candidate = {"schema": CANDIDATE_SCHEMA, "question_sha256": self.expected,
                          "source_snapshot": snapshot(artifact("Solution.lean"))}

    def bind(self, question=None, candidate=None, challenge=None):
        return bind_candidate(self.question if question is None else question,
            expected_question_sha256=self.expected,
            challenge_snapshot=self.challenge if challenge is None else challenge,
            candidate=self.candidate if candidate is None else candidate)

    def test_pure_identity_without_claim_authority(self):
        before = deepcopy((self.question, self.candidate, self.challenge))
        result = self.bind()
        self.assertEqual(result["question_sha256"], self.expected)
        self.assertEqual(set(result), {"schema", "question_sha256", "source_snapshot_sha256",
                                      "candidate_sha256"})
        self.assertEqual(before, (self.question, self.candidate, self.challenge))

    def test_goal_runtime_dependency_and_checker_substitution(self):
        for field in ("declaration", "challenge_module", "solution_module", "runtime_sha256",
                      "dependency_snapshot_sha256", "evaluator_sha256", "challenge_snapshot_sha256"):
            q = deepcopy(self.question)
            q[field] = "5" * 64 if field.endswith("sha256") else "Other"
            c = deepcopy(self.candidate)
            c["question_sha256"] = question_digest(q)
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.bind(q, c)
        q = deepcopy(self.question)
        q["checkers"]["nanoda"] = "5" * 64
        with self.assertRaises(ValueError):
            self.bind(q)

    def test_missing_checker_and_extra_axiom(self):
        for name in CHECKERS:
            q = deepcopy(self.question)
            del q["checkers"][name]
            with self.subTest(name=name), self.assertRaises(ValueError):
                question_digest(q)
        for axioms in (["propext"], False, {}, None):
            q = deepcopy(self.question)
            q["allowed_axioms"] = axioms
            with self.assertRaises(ValueError):
                question_digest(q)

    def test_candidate_cannot_supply_policy_or_receipt(self):
        for field in ("allowed_axioms", "checkers", "formal_proof", "verified", "expected_question_sha256"):
            c = deepcopy(self.candidate)
            c[field] = True
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.bind(candidate=c)

    def test_changed_challenge_and_missing_module(self):
        with self.assertRaises(ValueError):
            self.bind(challenge=snapshot(artifact("Challenge.lean", b"-- different\n")))
        c = deepcopy(self.candidate)
        c["source_snapshot"] = snapshot(artifact("Other.lean"))
        with self.assertRaises(ValueError):
            self.bind(candidate=c)

    def test_changed_source_creates_new_candidate_not_new_goal(self):
        c = deepcopy(self.candidate)
        c["source_snapshot"] = snapshot(artifact("Solution.lean", b"-- no proof\n"))
        result = self.bind(candidate=c)
        self.assertNotEqual(result["candidate_sha256"], self.bind()["candidate_sha256"])
        self.assertEqual(result["question_sha256"], self.expected)

    def test_identifier_injection_and_wrong_question(self):
        for name in ("../Other", "demo; command", "", True, "A." ):
            q = deepcopy(self.question)
            q["declaration"] = name
            with self.assertRaises(ValueError):
                question_digest(q)
        c = deepcopy(self.candidate)
        c["question_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            self.bind(candidate=c)


if __name__ == "__main__":
    unittest.main()
