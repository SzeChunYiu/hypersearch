"""Exhaustive census verifier and its frozen route. Small synthetic groups only."""
import copy
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from hypersearch import census as route
from hypersearch import census_contract as contract
from hypersearch.census_verifier import census, offending_subsequence, validate_question
from hypersearch.store import Store
from hypersearch.study_contract import wrapper as study_wrapper
from hypersearch.study_json import encode
from census_fixture import make_census
from study_fixture import launch, make


def ask(moduli, length, short_max, long_min=None):
    return {"moduli": list(moduli), "length": length, "short_max": short_max, "long_min": long_min}


def oracle(moduli, length, short_max, long_min):
    """A different algorithm: every multiset, every subsequence, direct sums."""
    elements = list(itertools.product(*[range(n) for n in moduli]))
    zero, total = (0,) * len(moduli), 0
    for sequence in itertools.combinations_with_replacement(elements, length):
        sizes = [r for r in range(1, length + 1) if r <= short_max or (long_min is not None and r >= long_min)]
        total += not any(tuple(sum(c) % n for c, n in zip(zip(*part), moduli)) == zero
                         for r in sizes for part in itertools.combinations(sequence, r))
    return total


class CensusVerifierTests(unittest.TestCase):
    def test_agrees_with_an_independent_oracle(self):
        for case in (([2], 3, 2, None), ([3], 3, 3, None), ([4], 4, 2, 4), ([2, 2], 4, 2, None), ([3, 3], 5, 3, None),
                     ([3, 3], 6, 3, 5), ([5], 5, 4, None), ([2, 4], 5, 3, 5), ([6], 5, 2, 4), ([2, 2, 2], 4, 3, None),
                     ([3, 3], 4, 4, None), ([2, 3], 5, 3, 4), ([4], 5, 3, 3 + 1)):
            self.assertEqual(census(ask(*case))["count"], oracle(*case), case)

    def test_known_constants_of_small_groups(self):
        # D(G): no zero-sum-free sequence of that length; eta(G): none avoiding zero-sums of length <= exp(G).
        for moduli, length, short_max, survivors in (([3, 3], 4, 4, True), ([3, 3], 5, 5, False), ([3, 3], 6, 3, True),
                                                     ([3, 3], 7, 3, False), ([2, 2, 2], 7, 2, True), ([2, 2, 2], 8, 2, False),
                                                     ([4, 4], 6, 6, True), ([4, 4], 7, 7, False), ([5], 4, 4, True), ([5], 5, 5, False)):
            result = census(ask(moduli, length, short_max))
            self.assertEqual(result["count"] > 0, survivors, (moduli, length))
            self.assertEqual(result["levels"][0], 1)
            if survivors:
                self.assertIsNone(offending_subsequence(result["example"], moduli, short_max, None))
        self.assertEqual(census(ask([2, 2, 2], 7, 2))["levels"], [1, 7, 21, 35, 35, 21, 7, 1])

    def test_long_condition_is_checked_only_on_complete_sequences(self):
        plain, capped = census(ask([3, 3], 6, 3)), census(ask([3, 3], 6, 3, 5))
        self.assertEqual(plain["levels"], capped["levels"])           # the walk is the same family
        self.assertEqual((plain["count"], capped["count"]), (24, 0))  # each survivor has a long zero-sum

    def test_question_bounds_are_closed(self):
        for bad in (ask([3, 3], 0, 1), ask([3, 3], 21, 3), ask([9, 9], 4, 2), ask([3, 3], 4, 5), ask([3, 3], 4, 0),
                    ask([3, 3], 6, 3, 3), ask([3, 3], 6, 3, 7), ask([3, 3], 6, 2, 4), ask([3, True], 4, 2),
                    ask((3, 3), 4, 2) | {"moduli": (3, 3)}, ask([3, 3], 4, 2) | {"extra": 1}, ask([], 4, 2), ask([1], 4, 2)):
            with self.assertRaises(ValueError, msg=bad):
                validate_question(bad)

    def test_parent_rejects_inconsistent_or_unsupported_results(self):
        with tempfile.TemporaryDirectory() as directory:
            _, _, bundle = make_census(Path(directory), length=6)
        honest = census(ask([3, 3], 6, 3))
        self.assertEqual(contract.verification(honest, bundle)["status"], "CENSUS_NONEMPTY")
        for change in ({"count": 0}, {"example": None}, {"example": [[1, 0], [2, 0]] + honest["example"][2:]},
                       {"levels": honest["levels"][:-1]}, {"levels": [1, 0] + honest["levels"][2:]}, {"length": 5},
                       {"formal_proof": True}, {"count": honest["levels"][-1] + 1}, {"scope": "other"}):
            with self.assertRaises(ValueError, msg=change):
                contract.verification(dict(honest, **change), bundle)
        for change in ({"levels": [1, 5] + honest["levels"][2:]}, {"levels": [1, 8, 10**6] + honest["levels"][3:]},
                       {"levels": [1, 8, 32, 0, 0, 0, 0], "count": 0, "example": None},
                       {"example": honest["example"][::-1]}):
            with self.assertRaises(ValueError, msg=change):
                contract.verification(dict(honest, **change), bundle)

    def test_parent_refutes_a_false_zero_below_the_standard_sequence(self):
        # C_3^2 has the zero-sum-free sequence 01 01 10 10, so a zero at length 4 is provably false.
        with tempfile.TemporaryDirectory() as directory:
            _, _, bundle = make_census(Path(directory), length=4, short_max=4)
        honest = census(ask([3, 3], 4, 4))
        self.assertEqual((honest["count"], contract.verification(honest, bundle)["status"]), (72, "CENSUS_NONEMPTY"))
        for levels in ([1, 8, 32, 0, 0], [1, 8, 32, 72, 0], [1, 8, 0, 0, 0]):
            with self.assertRaises(ValueError, msg=levels):
                contract.verification(dict(honest, count=0, example=None, levels=levels), bundle)
        self.assertEqual(contract._free_prefix([3, 3], 7), 4)
        self.assertEqual(contract._free_prefix([2, 4], 3), 3)

    def test_subset_check_is_inclusive_at_both_bounds(self):
        ones = lambda n: [[1]] * n
        self.assertIsNotNone(offending_subsequence(ones(5), [5], 5, None))   # zero-sum of length exactly short_max
        self.assertIsNone(offending_subsequence(ones(5), [5], 4, None))
        self.assertIsNotNone(offending_subsequence(ones(5), [5], 4, 5))      # zero-sum of length exactly long_min
        self.assertIsNone(offending_subsequence(ones(6), [5], 4, 6))         # its only zero-sums have length 5


class CensusRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def run_in_process(self, core, consumer, value, name="run", **more):
        with patch("hypersearch.study.CORE_ROOT", core):
            return route.execute(value, consumer_root=consumer, database=self.root / (name + ".sqlite"),
                                 export=self.root / name, **more)

    def test_empty_census_dedup_and_replay(self):
        core, consumer, bundle = make_census(self.root)                      # eta(C3^2) = 7
        first = self.run_in_process(core, consumer, contract.wrapper(bundle))
        self.assertEqual((first["execution"], first["outcome_status"]), ("completed", "CENSUS_EMPTY"))
        raw = Path(first["receipt_path"]).read_bytes()
        receipt = contract.trusted_receipt(raw, first["receipt_sha256"])
        self.assertEqual(receipt["schema"], "hypersearch.census-receipt/v1")
        self.assertEqual(receipt["outcome"]["verification"]["levels"], [1, 8, 32, 72, 96, 72, 24, 0])
        self.assertEqual(self.run_in_process(core, consumer, contract.wrapper(bundle))["execution"], "not_rerun")
        again = contract.wrapper(bundle, parent=first["receipt_sha256"], replay_id="second")
        with patch("hypersearch.study.CORE_ROOT", core):
            replay = route.execute(again, consumer_root=consumer, database=self.root / "run.sqlite",
                                   export=self.root / "replay", parent_receipt=receipt)
        self.assertTrue(replay["replay_matches_parent"])
        self.assertEqual(Store(self.root / "run.sqlite", max_attempts=5).snapshot()["budget"]["spent"], 2)

    def test_timeout_and_crash_are_never_census_results(self):
        core, consumer, bundle = make_census(self.root)
        with patch("hypersearch.study.subprocess.run", side_effect=subprocess.TimeoutExpired("fixture", 1)):
            timed_out = route.run_census(bundle, core)
        self.assertEqual(timed_out[0], {"status": "INCOMPLETE", "verification": None})
        with patch("hypersearch.census.run_census", return_value=timed_out):
            result = self.run_in_process(core, consumer, contract.wrapper(bundle), name="timeout")
        self.assertEqual(result["outcome_status"], "INCOMPLETE")
        with patch("hypersearch.census.run_census", side_effect=ValueError("forged output")):
            result = self.run_in_process(core, consumer, contract.wrapper(bundle), name="crash")
        self.assertEqual(result["outcome_status"], "EXECUTION_FAILED")

    def test_routes_do_not_accept_each_others_bundles(self):
        core, consumer, bundle = make_census(self.root)
        with self.assertRaises(ValueError):
            study_wrapper(bundle)
        other = Path(tempfile.mkdtemp(dir=self.root))
        _, _, study_bundle = make(other)
        with self.assertRaises(ValueError):
            contract.wrapper(study_bundle)
        wrong = copy.deepcopy(bundle); wrong["instrument"]["verifier"] = "hypersearch.multiwise-subsets/v1"
        with self.assertRaises(ValueError):
            contract.wrapper(wrong)

    def test_actual_cli_exit_codes_and_launch_contract(self):
        for length, code, status in ((7, 0, "CENSUS_EMPTY"), (6, 1, "CENSUS_NONEMPTY")):
            root = Path(tempfile.mkdtemp(dir=self.root))
            core, consumer, bundle = make_census(root, length=length)
            source = root / "bundle.json"; source.write_bytes(encode(bundle))
            arguments = ["-m", "hypersearch", "run-census", "--bundle", str(source), "--consumer-root", str(consumer),
                         "--db", str(root / "tasks.sqlite"), "--export", str(root / "receipts")]
            env = {"PATH": os.defpath, "PYTHONPATH": str(core / "src")}
            refused = subprocess.run([sys.executable, "-B", "-S", *arguments], env=env, capture_output=True, text=True)
            self.assertEqual(refused.returncode, 2); self.assertIn("launch with", refused.stderr)
            self.assertFalse((root / "tasks.sqlite").exists())
            result = subprocess.run([sys.executable, *launch(root / "private-cache"), *arguments], env=env,
                                    capture_output=True, text=True, timeout=120)
            self.assertEqual(result.returncode, code, result.stderr)
            self.assertEqual(json.loads(result.stdout)["outcome_status"], status)


if __name__ == "__main__":
    unittest.main()
