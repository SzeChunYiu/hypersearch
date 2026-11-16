"""Admitted exploration route: receipted, replayable, never evidence. Synthetic programs only."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from hypersearch import exploration as route
from hypersearch import exploration_contract as contract
from hypersearch import program as program_route
from hypersearch import program_contract
from hypersearch.export_check import check
from hypersearch.store import Store
from hypersearch.study_json import digest, encode
from exploration_fixture import OBSERVES, make_exploration
from program_fixture import make_program
from study_fixture import launch


def source(body):
    return ("import json, os, sys\narguments = json.loads(sys.stdin.read())\n" + body + "\n").encode()


class ExplorationRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def run_in_process(self, core, consumer, value, name="run", runner=route, **more):
        with patch("hypersearch.study.CORE_ROOT", core):
            return runner.execute(value, consumer_root=consumer, database=self.root / (name + ".sqlite"),
                                  export=self.root / name, **more)

    def outcome(self, body, name, **options):
        root = Path(tempfile.mkdtemp(dir=self.root))
        core, consumer, bundle = make_exploration(root, source(body), **options)
        result = self.run_in_process(core, consumer, contract.wrapper(bundle), name=name)
        receipt = contract.trusted_receipt(Path(result["receipt_path"]).read_bytes(), result["receipt_sha256"])
        return result["outcome_status"], receipt

    def test_observations_are_recorded_as_non_citable_and_replayed(self):
        core, consumer, bundle = make_exploration(self.root, arguments={"n": 7})
        first = self.run_in_process(core, consumer, contract.wrapper(bundle))
        self.assertEqual((first["execution"], first["outcome_status"]), ("completed", "EXPLORATION_RECORDED"))
        receipt = contract.trusted_receipt(Path(first["receipt_path"]).read_bytes(), first["receipt_sha256"])
        self.assertEqual(receipt["schema"], "hypersearch.exploration-receipt/v1")
        self.assertTrue(receipt["task_id"].startswith("exploration-"))
        record = receipt["outcome"]["verification"]
        self.assertEqual(record["observations"], {"echo": {"n": 7}})
        self.assertNotIn("holds", record)                               # an exploration states no answer
        self.assertEqual((record["evidence_kind"], record["citable"], record["result_checked_by_instrument"],
                          record["formal_proof"], record["novelty_assessed"]),
                         ("exploration_log", False, False, False, False))
        self.assertEqual(self.run_in_process(core, consumer, contract.wrapper(bundle))["execution"], "not_rerun")
        again = contract.wrapper(bundle, parent=first["receipt_sha256"], replay_id="second")
        with patch("hypersearch.study.CORE_ROOT", core):
            replay = route.execute(again, consumer_root=consumer, database=self.root / "run.sqlite",
                                   export=self.root / "replay", parent_receipt=receipt)
        self.assertTrue(replay["replay_matches_parent"])
        self.assertIn("usage", replay)
        self.assertEqual(Store(self.root / "run.sqlite", max_attempts=5).snapshot()["budget"]["spent"], 2)

    def test_a_verdict_or_malformed_output_is_a_failed_execution(self):
        for index, body in enumerate((
                'print(json.dumps({"holds": True, "summary": {}}))',           # the program route's verdict shape
                'print(json.dumps({"observations": {}, "holds": True}))',
                'print(json.dumps({"observations": {}, "citable": True}))',
                'print(json.dumps({"observations": []}))', 'print("not json")',
                'print(json.dumps({"observations": {"x": 0.5}}))',
                'print(json.dumps({"observations": {"x": "y" * 70000}}))',
                'print(json.dumps({"observations": {"x": [[[[[[[[[[[[[[[1]]]]]]]]]]]]]]]}}))',
                'raise SystemExit(3)')):
            status, receipt = self.outcome(body, f"bad{index}")
            self.assertEqual((status, receipt["outcome"]["verification"]), ("EXECUTION_FAILED", None), body)

    def test_routes_do_not_accept_each_others_bundles_or_receipts(self):
        core, consumer, bundle = make_exploration(Path(tempfile.mkdtemp(dir=self.root)))
        _, _, program_bundle = make_program(Path(tempfile.mkdtemp(dir=self.root)))
        with self.assertRaises(ValueError):
            program_contract.wrapper(bundle)
        with self.assertRaises(ValueError):
            contract.wrapper(program_bundle)
        for key, value in (("adapter", "pinned-program"), ("claim_type", "program-output")):
            changed = copy.deepcopy(bundle); changed["question"][key] = value
            with self.assertRaises(ValueError):
                contract.wrapper(changed)
        changed = copy.deepcopy(bundle); changed["instrument"]["verifier"] = "hypersearch.pinned-program/v1"
        with self.assertRaises(ValueError):
            contract.wrapper(changed)
        first = self.run_in_process(core, consumer, contract.wrapper(bundle))
        raw = Path(first["receipt_path"]).read_bytes()
        with self.assertRaises(ValueError):
            program_contract.trusted_receipt(raw, first["receipt_sha256"])
        forged = json.loads(raw)
        forged["outcome"]["verification"]["citable"] = True
        forged["outcome_sha256"] = digest(encode(forged["outcome"]))
        with self.assertRaises(ValueError):
            contract.validate_receipt(forged)
        with self.assertRaises(ValueError):                              # nor under a census or program parent
            program_route.execute(program_contract.wrapper(make_program(Path(tempfile.mkdtemp(dir=self.root)))[2],
                                                           parent=first["receipt_sha256"], replay_id="x"),
                                  consumer_root=consumer, database=self.root / "x.sqlite", export=self.root / "x",
                                  parent_receipt=json.loads(raw))

    def test_check_export_never_admits_an_exploration_receipt(self):
        root = Path(tempfile.mkdtemp(dir=self.root))
        core, consumer, bundle = make_exploration(root)
        with self.assertRaises(ValueError):
            check("exploration", [str(self.root)])
        first = self.run_in_process(core, consumer, contract.wrapper(bundle), name="explore")
        program_root = Path(tempfile.mkdtemp(dir=self.root))
        pcore, pconsumer, pbundle = make_program(program_root)
        self.run_in_process(pcore, pconsumer, program_contract.wrapper(pbundle), name="evidence", runner=program_route)
        Path(self.root / "evidence" / Path(first["receipt_path"]).name).write_bytes(Path(first["receipt_path"]).read_bytes())
        report = check("program", [str(self.root / "evidence")])
        self.assertFalse(report["ok"])
        self.assertEqual(report["receipts"], 1)
        self.assertIn("exploration receipt is not evidence", [p["problem"] for p in report["problems"]])
        alone = check("program", [str(self.root / "explore")])
        self.assertFalse(alone["ok"])
        self.assertEqual(alone["receipts"], 0)

    def test_actual_cli_exit_codes_and_launch_contract(self):
        for body, code, status in ((OBSERVES, 0, "EXPLORATION_RECORDED"),
                                   (source('raise SystemExit(1)'), 2, "EXECUTION_FAILED")):
            root = Path(tempfile.mkdtemp(dir=self.root))
            core, consumer, bundle = make_exploration(root, body)
            path = root / "bundle.json"; path.write_bytes(encode(bundle))
            arguments = ["-m", "hypersearch", "run-exploration", "--bundle", str(path), "--consumer-root",
                         str(consumer), "--db", str(root / "tasks.sqlite"), "--export", str(root / "receipts")]
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
