"""Frozen pinned-program route. Synthetic programs only."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from hypersearch import program as route
from hypersearch import program_contract as contract
from hypersearch.census_contract import wrapper as census_wrapper
from hypersearch.store import Store
from hypersearch.study_contract import wrapper as study_wrapper
from hypersearch.study_json import encode
from census_fixture import make_census
from program_fixture import HOLDS, make_program
from study_fixture import launch


def source(body):
    return ("import json, os, sys\narguments = json.loads(sys.stdin.read())\n" + body + "\n").encode()


class ProgramRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def run_in_process(self, core, consumer, value, name="run", **more):
        with patch("hypersearch.study.CORE_ROOT", core):
            return route.execute(value, consumer_root=consumer, database=self.root / (name + ".sqlite"),
                                 export=self.root / name, **more)

    def outcome(self, body, name, **options):
        root = Path(tempfile.mkdtemp(dir=self.root))
        core, consumer, bundle = make_program(root, source(body), **options)
        result = self.run_in_process(core, consumer, contract.wrapper(bundle), name=name)
        receipt = contract.trusted_receipt(Path(result["receipt_path"]).read_bytes(), result["receipt_sha256"])
        return result["outcome_status"], receipt

    def test_output_is_recorded_deduplicated_and_replayed(self):
        core, consumer, bundle = make_program(self.root, arguments={"n": 7})
        first = self.run_in_process(core, consumer, contract.wrapper(bundle))
        self.assertEqual((first["execution"], first["outcome_status"]), ("completed", "PROGRAM_HOLDS"))
        receipt = contract.trusted_receipt(Path(first["receipt_path"]).read_bytes(), first["receipt_sha256"])
        record = receipt["outcome"]["verification"]
        self.assertEqual(record["summary"], {"echo": {"n": 7}})          # arguments reach the program on stdin
        self.assertEqual((record["evidence_kind"], record["result_checked_by_instrument"], record["formal_proof"]),
                         ("pinned_program_output", False, False))
        self.assertEqual(record["program_sha256"], bundle["artifacts"]["program"]["sha256"])
        self.assertEqual(self.run_in_process(core, consumer, contract.wrapper(bundle))["execution"], "not_rerun")
        again = contract.wrapper(bundle, parent=first["receipt_sha256"], replay_id="second")
        with patch("hypersearch.study.CORE_ROOT", core):
            replay = route.execute(again, consumer_root=consumer, database=self.root / "run.sqlite",
                                   export=self.root / "replay", parent_receipt=receipt)
        self.assertTrue(replay["replay_matches_parent"])
        self.assertEqual(Store(self.root / "run.sqlite", max_attempts=5).snapshot()["budget"]["spent"], 2)

    def test_program_runs_isolated_from_environment_and_imports(self):
        checks = ('ok = bool(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode)\n'
                  'ok = ok and set(os.environ) <= {"PATH", "LC_CTYPE"} and os.getcwd() not in sys.path\n'
                  'ok = ok and os.listdir(".") == ["program.py"]\n'
                  'print(json.dumps({"holds": ok, "summary": {"environment": sorted(os.environ)}}))')
        with patch.dict(os.environ, {"PYTHONPATH": "/nonexistent", "SECRET_TOKEN": "x"}):
            status, receipt = self.outcome(checks, "isolated")
        self.assertEqual(status, "PROGRAM_HOLDS", receipt["outcome"])

    def test_false_result_and_every_malformed_output(self):
        self.assertEqual(self.outcome('print(json.dumps({"holds": False, "summary": {}}))', "fails")[0], "PROGRAM_FAILS")
        for index, body in enumerate(('print("not json")', 'print(json.dumps({"holds": 1, "summary": {}}))',
                                      'print(json.dumps({"holds": True, "summary": []}))',
                                      'print(json.dumps({"holds": True, "summary": {}, "extra": 1}))',
                                      'print(json.dumps({"holds": True}))', 'print(json.dumps({"holds": True, "summary": {"x": 0.5}}))',
                                      'print(json.dumps({"holds": True, "summary": {"x": "y" * 70000}}))',
                                      'raise SystemExit(3)', 'raise RuntimeError("boom")', 'x = bytearray(2 * 1024 ** 3)',
                                      'open("big", "wb").write(b"0" * 4000000)')):
            status, receipt = self.outcome(body, f"bad{index}", memory=256)
            self.assertEqual((status, receipt["outcome"]["verification"]), ("EXECUTION_FAILED", None), body)

    def test_timeout_is_incomplete_and_kills_what_the_program_started(self):
        marker = self.root / "pid"
        body = ('import subprocess, time\nchild = subprocess.Popen(["sleep", "600"])\n'
                'open(arguments["pid"], "w").write(str(child.pid))\ntime.sleep(600)')
        status, receipt = self.outcome(body, "timeout", arguments={"pid": str(marker)}, timeout=2)
        self.assertEqual((status, receipt["diagnostics"]), ("INCOMPLETE", "program timeout"))
        pid = int(marker.read_text())
        for _ in range(50):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            if Path(f"/proc/{pid}/stat").read_text().split(")")[1].split()[0] == "Z":
                break
            time.sleep(0.1)
        else:
            self.fail("the program's own child survived the timeout")

    def test_admission_is_closed(self):
        core, consumer, bundle = make_program(self.root)
        def changed(**question):
            value = copy.deepcopy(bundle); value["question"].update(question); return value
        def limited(**limits):
            value = copy.deepcopy(bundle); value["limits"].update(limits); return value
        wrong_verifier = copy.deepcopy(bundle); wrong_verifier["instrument"]["verifier"] = "hypersearch.zero-sum-census/v1"
        renamed = copy.deepcopy(bundle); renamed["artifacts"]["program"]["path"] = "program.sh"
        for bad in (changed(adapter="zero-sum-census"), changed(claim_type="exhaustive-census"), changed(program_sha256="0" * 64),
                    changed(arguments=[1]), changed(arguments={"x": "y" * 5000}), changed(extra=1), limited(timeout_seconds=0),
                    limited(timeout_seconds=21601), limited(commit_margin_seconds=4), limited(memory_megabytes=63),
                    limited(memory_megabytes=True), wrong_verifier, renamed):
            with self.assertRaises(ValueError, msg=bad["question"]):
                contract.wrapper(bad)
        with self.assertRaises(ValueError):       # routes do not accept each other's bundles
            study_wrapper(bundle)
        with self.assertRaises(ValueError):
            census_wrapper(bundle)
        other = Path(tempfile.mkdtemp(dir=self.root))
        with self.assertRaises(ValueError):
            contract.wrapper(make_census(other)[2])

    def test_parent_rejects_a_record_that_is_not_this_task(self):
        _, _, bundle = make_program(self.root, arguments={"n": 1})
        honest = contract.record({"holds": True, "summary": {"a": 1}}, bundle)
        self.assertEqual(contract.verification(honest, bundle)["status"], "PROGRAM_HOLDS")
        for change in ({"holds": "yes"}, {"summary": None}, {"program_sha256": "0" * 64}, {"arguments": {"n": 2}},
                       {"result_checked_by_instrument": True}, {"formal_proof": True}, {"scope": "other"}):
            with self.assertRaises(ValueError, msg=change):
                contract.verification(dict(honest, **change), bundle)
        with self.assertRaises(ValueError):
            contract.outcome({"status": "PROGRAM_FAILS", "verification": honest}, bundle)

    def test_actual_cli_exit_codes_and_launch_contract(self):
        for body, code, status in ((HOLDS, 0, "PROGRAM_HOLDS"),
                                   (source('print(json.dumps({"holds": False, "summary": {}}))'), 1, "PROGRAM_FAILS"),
                                   (source('raise SystemExit(1)'), 2, "EXECUTION_FAILED")):
            root = Path(tempfile.mkdtemp(dir=self.root))
            core, consumer, bundle = make_program(root, body)
            path = root / "bundle.json"; path.write_bytes(encode(bundle))
            arguments = ["-m", "hypersearch", "run-program", "--bundle", str(path), "--consumer-root", str(consumer),
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
