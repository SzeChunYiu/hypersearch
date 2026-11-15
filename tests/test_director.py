"""Synthetic software conformance only; no research-effectiveness measurement."""
import copy
import hashlib
import json
import unittest
from unittest.mock import patch

from hypersearch.director import recommend
from hypersearch.director_contract import COSTS, OBSERVATION, POLICY
from hypersearch.study_json import digest, encode


def fixture():
    gate = {"permission": "allowed", "hold": "clear", "dependency": "ready"}
    def row(name, gain, cost):
        return {"candidate_id": name, "task_sha256": digest(name.encode()),
                "declared_gain": gain, "declared_cost": dict(zip(COSTS, cost)),
                "gate": dict(gate)}
    return {"schema": OBSERVATION, "observation_id": "synthetic",
            "consumer_commit": "a" * 40, "gain_unit": "hypothetical",
            "cost_unit": "declared-work", "gate": gate,
            "candidates": [row("b", 8, [2, 1, 1, 0]), row("a", 4, [1, 1, 0, 0]),
                           row("c", 3, [1, 0, 0, 0])]}


def call(observation=None, policy_id="supplied-order/v1", seed=0, raw=None):
    observed = encode(observation if observation is not None else fixture()) if raw is None else raw
    policy = encode({"schema": POLICY, "policy_id": policy_id, "seed": seed})
    return recommend(observed, policy, expected_observation_sha256=digest(observed),
                     expected_policy_sha256=digest(policy))


class DirectorTests(unittest.TestCase):
    def test_policies_ranking_tie_and_replay(self):
        self.assertEqual(json.loads(call())["ranked_candidate_ids"], ["b", "a", "c"])
        self.assertEqual(json.loads(call(policy_id="declared-gain-cost/v1"))[
            "ranked_candidate_ids"], ["c", "a", "b"])
        actual = call(policy_id="seeded-hash-order/v1", seed=17)
        expected = sorted(["a", "b", "c"], key=lambda x: hashlib.sha256(
            json.dumps({"candidate_id": x, "seed": 17}, sort_keys=True,
                       separators=(",", ":")).encode()).hexdigest())
        self.assertEqual(json.loads(actual)["ranked_candidate_ids"], expected)
        self.assertEqual(actual, call(policy_id="seeded-hash-order/v1", seed=17))
        self.assertNotEqual(actual, call(policy_id="seeded-hash-order/v1", seed=18))

    def test_no_store_and_no_authority(self):
        with patch("hypersearch.store.Store.__init__", side_effect=AssertionError("Store used")):
            result = json.loads(call())
        self.assertEqual((result["mode"], result["authority"]), ("shadow", "none"))
        self.assertIs(result["execution_allowed"], False)
        self.assertIs(result["requires_live_admission_recheck"], True)
        self.assertEqual(result["selected_task_sha256"], digest(b"b"))

    def test_exact_identity_and_immutable_snapshots(self):
        obs = fixture()
        before = copy.deepcopy(obs)
        raw = encode(obs)
        policy = encode({"schema": POLICY, "policy_id": "supplied-order/v1", "seed": 0})
        result = recommend(raw, policy, expected_observation_sha256=digest(raw),
                           expected_policy_sha256=digest(policy))
        self.assertIs(type(result), bytes)
        self.assertEqual(obs, before)
        changed = json.loads(call(raw=raw + b" "))
        self.assertNotEqual(changed["observation_sha256"], json.loads(result)["observation_sha256"])
        for changed_raw, changed_policy in ((raw + b" ", policy), (raw, policy + b" ")):
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                recommend(changed_raw, changed_policy, expected_observation_sha256=digest(raw),
                          expected_policy_sha256=digest(policy))
        with self.assertRaises(ValueError):
            recommend(bytearray(raw), policy, expected_observation_sha256=digest(raw),
                      expected_policy_sha256=digest(policy))

    def test_gate_distinctions_at_both_levels(self):
        cases = [("permission", x) for x in ("pending", "denied", "revoked")]
        cases += [("hold", "active"), ("dependency", "pending"), ("dependency", "revoked")]
        for level in ("observation", "candidate"):
            for field, value in cases:
                with self.subTest(level=level, field=field, value=value):
                    obs = fixture()
                    if level == "observation":
                        obs["gate"][field] = value
                    else:
                        for row in obs["candidates"]:
                            row["gate"][field] = value
                    result = json.loads(call(obs))
                    self.assertEqual(result["action"], "defer")
                    self.assertIsNone(result["selected_task_sha256"])
                    self.assertIn(level + ":" + field + ":" + value,
                                  result["excluded"][0]["reasons"])

    def test_revoked_best_candidate_cannot_win_any_policy(self):
        obs = fixture()
        obs["candidates"][0]["declared_gain"] = 10**12
        obs["candidates"][0]["gate"]["permission"] = "revoked"
        for policy in ("supplied-order/v1", "declared-gain-cost/v1", "seeded-hash-order/v1"):
            result = json.loads(call(obs, policy))
            self.assertNotIn("b", result["ranked_candidate_ids"])

    def test_stop_and_defer(self):
        obs = fixture()
        for row in obs["candidates"]:
            row["declared_gain"] = -1
        self.assertEqual(json.loads(call(obs))["action"], "stop")
        obs["candidates"] = []
        self.assertEqual(json.loads(call(obs))["action"], "stop")
        obs["gate"]["hold"] = "active"
        self.assertEqual(json.loads(call(obs))["action"], "defer")

    def test_numeric_and_cost_refusals(self):
        for value in (True, 1.5, float("inf"), float("nan"), 10**12 + 1):
            obs = fixture()
            obs["candidates"][0]["declared_gain"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                call(raw=json.dumps(obs).encode())
        for costs in ({x: 0 for x in COSTS}, {x: -1 for x in COSTS},
                      {"execution": 1}, {x: True for x in COSTS}):
            obs = fixture()
            obs["candidates"][0]["declared_cost"] = costs
            with self.subTest(costs=costs), self.assertRaises(ValueError):
                call(obs)

    def test_closed_schema_and_identity_refusals(self):
        for mutation in ("extra", "duplicate", "gate", "hash", "commit", "count"):
            obs = fixture()
            if mutation == "extra":
                obs["authority"] = "yes"
            elif mutation == "duplicate":
                obs["candidates"].append(copy.deepcopy(obs["candidates"][0]))
            elif mutation == "gate":
                obs["gate"]["permission"] = "assumed"
            elif mutation == "hash":
                obs["candidates"][0]["task_sha256"] = "bad"
            elif mutation == "commit":
                obs["consumer_commit"] = "main"
            else:
                obs["candidates"] *= 334
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                call(obs)
        for raw in (b'{"schema":"x","schema":"y"}', b"[]", b"\xff", b" " * (1048576 + 1)):
            with self.assertRaises(ValueError):
                call(raw=raw)

    def test_unknown_policy_and_seed_refusal(self):
        for name, seed in (("optimal/v1", 0), ("supplied-order/v1", 1),
                           ("seeded-hash-order/v1", True), ("seeded-hash-order/v1", -1),
                           ("seeded-hash-order/v1", 2**64)):
            with self.subTest(name=name, seed=seed), self.assertRaises(ValueError):
                call(policy_id=name, seed=seed)


if __name__ == "__main__":
    unittest.main()
