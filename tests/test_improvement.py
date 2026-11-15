"""Adversarial conformance tests for the finite-suite improvement gate."""
import copy
import json
import unittest

from hypersearch.improvement import EVALUATOR, PLAN, RUN, evaluate, evaluator_source_sha256
from hypersearch.study_json import digest, encode


def fixtures():
    suite = [{"case_id": name, "task_sha256": digest(name.encode()),
              "expected": expected, "weight": 1}
             for name, expected in (("positive-a", "ACCEPT"), ("negative-a", "REJECT"),
                                    ("positive-b", "ACCEPT"), ("negative-b", "REJECT"))]
    plan = {"schema": PLAN,
            "evaluator": {"id": EVALUATOR, "source_sha256": evaluator_source_sha256()},
            "baseline": {"id": "baseline-v1", "source_sha256": "a" * 64},
            "candidate": {"id": "candidate-v2", "source_sha256": "b" * 64},
            "suite": suite, "budget": {"unit": "bounded-operations", "max_operations": 8},
            "minimum_correct_weight_gain": 2}
    plan_raw = encode(plan)

    def run(role, observed):
        source = plan[role]
        rows = [{"case_id": spec["case_id"], "task_sha256": spec["task_sha256"],
                 "status": "COMPLETED", "observed": result, "operations": 1}
                for spec, result in zip(suite, observed)]
        return {"schema": RUN, "run_id": role + "-run", "plan_sha256": digest(plan_raw),
                "role": role, "source_id": source["id"],
                "source_sha256": source["source_sha256"], "execution_status": "COMPLETE",
                "total_operations": 4, "cases": rows}
    baseline = run("baseline", ["REJECT", "REJECT", "REJECT", "REJECT"])
    candidate = run("candidate", ["ACCEPT", "REJECT", "ACCEPT", "REJECT"])
    return plan, baseline, candidate


def call(plan=None, baseline=None, candidate=None, raws=None):
    original = fixtures()
    plan = copy.deepcopy(original[0] if plan is None else plan)
    plan_raw = encode(plan) if raws is None else raws[0]
    baseline = copy.deepcopy(original[1] if baseline is None else baseline)
    candidate = copy.deepcopy(original[2] if candidate is None else candidate)
    for run in (baseline, candidate):
        run["plan_sha256"] = digest(plan_raw)
    baseline_raw = encode(baseline) if raws is None else raws[1]
    candidate_raw = encode(candidate) if raws is None else raws[2]
    return json.loads(evaluate(plan_raw, baseline_raw, candidate_raw, digest(plan_raw)))


class ImprovementTests(unittest.TestCase):
    def test_material_gain_accepts_without_authority(self):
        result = call()
        self.assertEqual(result["verdict"], "ACCEPT")
        self.assertEqual(result["results"]["correct_weight_gain"], 2)
        self.assertEqual(result["promotion_authority"], "none")
        self.assertEqual(result["cost_measurement"], "reported_not_independently_measured")
        self.assertEqual(result["execution_attestation"], "none")
        self.assertEqual(result["expected_label_validation"], "not_performed")
        self.assertEqual(result["evaluator_source_validation"], "local_source_bundle_match")
        self.assertEqual(result["candidate_source_validation"], "declared_record_match_only")

    def test_no_benefit_and_regression_controls_reject(self):
        plan, baseline, candidate = fixtures()
        candidate["cases"] = copy.deepcopy(baseline["cases"])
        self.assertEqual(call(plan, baseline, candidate)["reasons"], ["minimum_gain_not_met"])
        baseline["cases"] = copy.deepcopy(fixtures()[2]["cases"])
        self.assertEqual(call(plan, baseline, candidate)["reasons"], ["candidate_case_regression"])

    def test_false_acceptance_rejects_despite_aggregate_gain(self):
        plan, baseline, candidate = fixtures()
        candidate["cases"][3]["observed"] = "ACCEPT"
        result = call(plan, baseline, candidate)
        self.assertEqual(result["verdict"], "REJECT")
        self.assertEqual(result["reasons"], ["candidate_false_acceptance"])
        self.assertEqual(result["results"]["candidate"]["false_acceptance_case_ids"], ["negative-b"])

    def test_timeout_missing_cost_and_failed_case_are_inconclusive_and_retained(self):
        for status, execution, operations in (("TIMEOUT", "TIMEOUT", 1),
                                               ("FAILED", "INCOMPLETE", 1),
                                               ("NOT_RUN", "UNKNOWN_COST", None)):
            with self.subTest(status=status):
                plan, baseline, candidate = fixtures()
                row = candidate["cases"][0]
                row.update(status=status, observed=None, operations=operations)
                candidate["execution_status"] = execution
                if operations is None:
                    candidate["total_operations"] = None
                result = call(plan, baseline, candidate)
                self.assertEqual(result["verdict"], "INCONCLUSIVE")
                retained = result["results"]["candidate"]["retained_cases"]
                changed = next(row for row in retained if row["case_id"] == "positive-a")
                self.assertEqual(changed["status"], status)

    def test_budget_overrun_rejects(self):
        plan, baseline, candidate = fixtures()
        candidate["cases"][0]["operations"] = 6
        candidate["total_operations"] = 9
        result = call(plan, baseline, candidate)
        self.assertEqual((result["verdict"], result["reasons"]),
                         ("REJECT", ["matched_budget_exceeded"]))

    def test_known_overrun_rejects_even_if_run_is_incomplete(self):
        plan, baseline, candidate = fixtures()
        candidate["cases"][0].update(status="FAILED", observed=None, operations=6)
        candidate["execution_status"] = "INCOMPLETE"
        candidate["total_operations"] = 9
        result = call(plan, baseline, candidate)
        self.assertEqual((result["verdict"], result["reasons"]),
                         ("REJECT", ["matched_budget_exceeded"]))

    def test_order_invariant_and_deterministic(self):
        plan, baseline, candidate = fixtures()
        result = call(plan, baseline, candidate)
        baseline["cases"].reverse()
        candidate["cases"] = candidate["cases"][1:] + candidate["cases"][:1]
        reordered = call(plan, baseline, candidate)
        for value in (result, reordered):
            value.pop("baseline_run_sha256")
            value.pop("candidate_run_sha256")
        self.assertEqual(result, reordered)
        self.assertEqual(call(), call())

    def test_identity_duplicate_omission_and_favourable_only_refuse(self):
        mutations = []
        plan, baseline, candidate = fixtures()
        changed = copy.deepcopy(candidate); changed["source_sha256"] = "c" * 64
        mutations.append((plan, baseline, changed))
        changed = copy.deepcopy(candidate); changed["cases"][1] = copy.deepcopy(changed["cases"][0])
        mutations.append((plan, baseline, changed))
        changed = copy.deepcopy(candidate); changed["cases"].pop()
        mutations.append((plan, baseline, changed))
        changed = copy.deepcopy(candidate); changed["cases"][0]["task_sha256"] = "f" * 64
        mutations.append((plan, baseline, changed))
        for values in mutations:
            with self.subTest(), self.assertRaises(ValueError):
                call(*values)

    def test_closed_schema_numeric_and_raw_identity_refusals(self):
        plan, baseline, candidate = fixtures()
        for mutation in ("extra", "bool", "zero-gain", "same-id", "duplicate-task",
                         "evaluator", "no-negative"):
            changed = copy.deepcopy(plan)
            if mutation == "extra":
                changed["authority"] = "promotion"
            elif mutation == "bool":
                changed["budget"]["max_operations"] = True
            elif mutation == "zero-gain":
                changed["minimum_correct_weight_gain"] = 0
            elif mutation == "same-id":
                changed["candidate"]["id"] = changed["baseline"]["id"]
            elif mutation == "duplicate-task":
                changed["suite"][1]["task_sha256"] = changed["suite"][0]["task_sha256"]
            elif mutation == "evaluator":
                changed["evaluator"]["source_sha256"] = "0" * 64
            else:
                for row in changed["suite"]:
                    row["expected"] = "ACCEPT"
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                call(changed, baseline, candidate)
        plan_raw = encode(plan)
        baseline["plan_sha256"] = candidate["plan_sha256"] = digest(plan_raw)
        with self.assertRaisesRegex(ValueError, "plan digest mismatch"):
            evaluate(plan_raw + b" ", encode(baseline), encode(candidate), digest(plan_raw))
        duplicate = plan_raw[:-1] + b',"schema":"hypersearch.improvement-plan/v1"}'
        with self.assertRaises(ValueError):
            evaluate(duplicate, encode(baseline), encode(candidate), digest(duplicate))


if __name__ == "__main__":
    unittest.main()
