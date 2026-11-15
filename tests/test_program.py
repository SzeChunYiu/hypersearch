"""Frozen pinned-program route. Synthetic programs only."""
import base64
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile

from hypersearch import program as route
from hypersearch import program_contract as contract
from hypersearch.census_contract import execution_identity as census_identity, wrapper as census_wrapper
from hypersearch.store import Store
from hypersearch.study_contract import wrapper as study_wrapper
from hypersearch.study_json import digest, encode
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

    def test_a_refused_start_names_its_reason_and_changes_nothing(self):
        # The attempt ceiling counts every lease in the database, not leases per task.
        core, consumer, bundle = make_program(self.root, attempts=1)
        first = self.run_in_process(core, consumer, contract.wrapper(bundle))
        self.assertEqual(first["execution"], "completed")
        receipt = contract.trusted_receipt(Path(first["receipt_path"]).read_bytes(), first["receipt_sha256"])
        replay = contract.wrapper(bundle, parent=first["receipt_sha256"], replay_id="second")
        with patch("hypersearch.study.CORE_ROOT", core):
            refused = route.execute(replay, consumer_root=consumer, database=self.root / "run.sqlite",
                                    export=self.root / "refused", parent_receipt=receipt)
        self.assertEqual((refused["execution"], refused["reason"]), ("not_started", "attempt budget exhausted"))
        self.assertEqual((refused["budget"], refused["task_state"]), ({"maximum": 1, "spent": 1}, "pending"))
        after = Store(self.root / "run.sqlite", max_attempts=1).snapshot()
        self.assertEqual((len(after["results"]), after["budget"]["spent"]), (1, 1))
        self.assertFalse((self.root / "refused").exists())
        # A task that another attempt holds is refused for the other reason, with budget to spare.
        root = Path(tempfile.mkdtemp(dir=self.root))
        core, consumer, bundle = make_program(root)
        value = contract.wrapper(bundle)
        task_id, _ = contract.execution_identity(value)
        store = Store(self.root / "busy.sqlite", max_attempts=5)
        store.submit(task_id, value)
        self.assertIsNotNone(store.acquire("someone-else", lease_seconds=60, task_id=task_id))
        busy = self.run_in_process(core, consumer, value, name="busy")
        self.assertEqual((busy["execution"], busy["reason"], busy["task_state"]),
                         ("not_started", "task is leased to another attempt", "running"))
        self.assertEqual(busy["budget"], {"maximum": 5, "spent": 1})

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
        good = 'print(json.dumps({"holds": True, "summary": {}}))'
        deep = 'print(\'{"holds": true, "summary": {"x": \' + "[" * 2000 + "]" * 2000 + "}}")'
        for index, body in enumerate(('print("not json")', 'print(json.dumps({"holds": 1, "summary": {}}))',
                                      'print(json.dumps({"holds": True, "summary": []}))',
                                      'print(json.dumps({"holds": True, "summary": {}, "extra": 1}))',
                                      'print(json.dumps({"holds": True}))', 'print(json.dumps({"holds": True, "summary": {"x": 0.5}}))',
                                      'print(json.dumps({"holds": True, "summary": {"x": "y" * 70000}}))',
                                      good + '\nsys.stdout.flush()\nraise SystemExit(3)', good + '\nsys.stdout.flush()\nos.kill(os.getpid(), 9)',
                                      good + '\n' + good, deep, 'print(json.dumps({"holds": True, "summary": {"x": [[[[[[[[[[[[[[[[1]]]]]]]]]]]]]]]]}}))')):
            status, receipt = self.outcome(body, f"bad{index}", memory=256)
            self.assertEqual((status, receipt["outcome"]["verification"]), ("EXECUTION_FAILED", None), body)
        status, _ = self.outcome('print(json.dumps({"holds": True, "summary": {"x": [[[[[[[[[[[[[[1]]]]]]]]]]]]]]}}))', "depth16")
        self.assertEqual(status, "PROGRAM_HOLDS")       # the object, fourteen lists and the scalar: depth 16, the last admitted
        status, _ = self.outcome('print(json.dumps({"holds": True, "summary": {"x": [[[[[[[[[[[[[[[1]]]]]]]]]]]]]]]}}))', "depth17")
        self.assertEqual(status, "EXECUTION_FAILED")

    def test_program_runs_as_plain_source_in_the_real_main_module(self):
        hidden = ('# -*- coding: utf-7 -*-\nimport json\nhidden = 0\n# +AAo-hidden = 1\n'
                  'print(json.dumps({"holds": hidden == 0, "summary": {"hidden": hidden}}))\n').encode()
        root = Path(tempfile.mkdtemp(dir=self.root))
        core, consumer, bundle = make_program(root, hidden)
        result = self.run_in_process(core, consumer, contract.wrapper(bundle), name="cookie")
        self.assertEqual(result["outcome_status"], "PROGRAM_HOLDS")     # the declaration is ignored: no hidden line runs
        body = ('from __future__ import annotations\nimport dataclasses, json, pickle, typing\n'
                '@dataclasses.dataclass\nclass A:\n    x: int = 1\n    y: typing.ClassVar[int] = 2\n'
                'ok = len(dataclasses.fields(A)) == 1 and __name__ == "__main__" and isinstance(pickle.dumps(A()), bytes)\n'
                'print(json.dumps({"holds": ok, "summary": {"names": sorted(n for n in globals() if not n.startswith("__"))}}))\n')
        root = Path(tempfile.mkdtemp(dir=self.root))
        core, consumer, bundle = make_program(root, body.encode())
        result = self.run_in_process(core, consumer, contract.wrapper(bundle), name="namespace")
        self.assertEqual(result["outcome_status"], "PROGRAM_HOLDS")
        receipt = contract.trusted_receipt(Path(result["receipt_path"]).read_bytes(), result["receipt_sha256"])
        self.assertEqual(receipt["outcome"]["verification"]["summary"]["names"],
                         ["A", "annotations", "dataclasses", "json", "ok", "pickle", "typing"])   # nothing added by the launch

    def test_limits_are_really_imposed_on_the_program(self):
        body = ('import resource, signal\nsignal.signal(signal.SIGXFSZ, signal.SIG_IGN)\nseen = {}\n'
                'try:\n    block = bytearray(2 * 1024 ** 3); seen["memory"] = False\nexcept MemoryError:\n    seen["memory"] = True\n'
                'try:\n    open("big", "wb").write(b"0" * 4000000); seen["file"] = False\nexcept OSError:\n    seen["file"] = True\n'
                'seen["core"] = resource.getrlimit(resource.RLIMIT_CORE)[0]\n'
                'seen["address"] = resource.getrlimit(resource.RLIMIT_AS)[0]\n'
                'print(json.dumps({"holds": True, "summary": seen}))')
        status, receipt = self.outcome(body, "limits", memory=256)
        self.assertEqual(status, "PROGRAM_HOLDS")
        self.assertEqual(receipt["outcome"]["verification"]["summary"],
                         {"memory": True, "file": True, "core": 0, "address": 256 * 1048576})

    def test_replay_with_a_different_output_is_a_mismatch(self):
        flag = self.root / "flag"
        body = 'print(json.dumps({"holds": True, "summary": {"n": json.loads(open(arguments["flag"]).read())}}))'
        core, consumer, bundle = make_program(self.root, source(body), arguments={"flag": str(flag)})
        flag.write_text("1")
        first = self.run_in_process(core, consumer, contract.wrapper(bundle))
        receipt = contract.trusted_receipt(Path(first["receipt_path"]).read_bytes(), first["receipt_sha256"])
        for index, (later, same) in enumerate((("1", True), ("true", False), ("2", False))):  # 1 == True in Python
            flag.write_text(later)
            again = contract.wrapper(bundle, parent=first["receipt_sha256"], replay_id=f"replay-{index}")
            with patch("hypersearch.study.CORE_ROOT", core):
                replay = route.execute(again, consumer_root=consumer, database=self.root / "run.sqlite",
                                       export=self.root / f"replay{index}", parent_receipt=receipt)
            self.assertIs(replay["replay_matches_parent"], same, later)
        task, _ = contract.execution_identity(again)
        self.assertTrue(task.startswith("program-replay-"))
        _, _, census_bundle = make_census(Path(tempfile.mkdtemp(dir=self.root)))
        other = census_wrapper(census_bundle, parent="0" * 64, replay_id="replay-2")
        self.assertNotEqual(task.split("-")[-1], census_identity(other)[0].split("-")[-1])

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

    def refrozen(self, bundle, question=None, limits=None, program=None, drop=(), manifest=None):
        """Change a bundle and re-freeze its manifest, so only the changed field can be the reason for refusal."""
        value = copy.deepcopy(bundle)
        value["question"].update(question or {}); value["limits"].update(limits or {})
        for key in drop:
            del value["limits"][key]
        if program is not None:
            value["artifacts"]["program"].update(bytes=len(program), sha256=digest(program),
                                                 base64=base64.b64encode(program).decode("ascii"))
            value["question"]["program_sha256"] = digest(program)
        kept = {k: v["sha256"] for k, v in value["artifacts"].items() if k != "study_manifest"}
        manifest = encode(dict({"schema": "hypersearch.program-manifest/v1", "study_id": value["study_id"],
                                "question": value["question"], "limits": value["limits"], "artifact_sha256": kept},
                               **(manifest or {})))
        value["artifacts"]["study_manifest"].update(bytes=len(manifest), sha256=digest(manifest),
                                                    base64=base64.b64encode(manifest).decode("ascii"))
        return value

    def test_admission_is_closed(self):
        core, consumer, bundle = make_program(self.root)
        self.assertEqual(contract.wrapper(self.refrozen(bundle, question={"arguments": {"n": 2}}))["kind"], "original")
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("__main__.py", HOLDS.decode())
        nested = {"x": 1}
        for _ in range(16):
            nested = {"x": nested}
        for bad in (dict(question={"adapter": "zero-sum-census"}), dict(question={"claim_type": "exhaustive-census"}),
                    dict(question={"program_sha256": "0" * 64}), dict(question={"assumptions_sha256": "0" * 64}),
                    dict(question={"arguments": [1]}), dict(question={"arguments": {"x": "y" * 5000}}),
                    dict(question={"arguments": nested}), dict(question={"extra": 1}),
                    dict(limits={"timeout_seconds": 0}), dict(limits={"timeout_seconds": 21601}),
                    dict(limits={"commit_margin_seconds": 4}), dict(limits={"commit_margin_seconds": 61}),
                    dict(limits={"memory_megabytes": 63}), dict(limits={"memory_megabytes": 65537}),
                    dict(limits={"memory_megabytes": True}), dict(limits={"db_max_attempts": 0}), dict(limits={"extra": 1}),
                    dict(drop=("memory_megabytes",)), dict(manifest={"schema": "hypersearch.census-manifest/v1"}),
                    dict(manifest={"study_id": "other"}), dict(manifest={"limits": dict(bundle["limits"], timeout_seconds=31)}),
                    dict(manifest={"artifact_sha256": {}}), dict(manifest={"question": dict(bundle["question"], arguments={"n": 9})}),
                    dict(program=archive.getvalue()),
                    dict(program=b"print(1)\n\"\"\"" + archive.getvalue()), dict(program=b"\x00" + HOLDS),
                    dict(program=b"   \n"), dict(program=b"\xff\xfe" + HOLDS), dict(program=b"# note\rprint(1)\n" + HOLDS),
                    dict(program=HOLDS + b"\x7f"), dict(program=HOLDS + "x = '\u202e'\n".encode()),
                    dict(program=HOLDS + "x = '\u00e9'\n".encode()), dict(program="\ufeff".encode() + HOLDS)):
            with self.assertRaises(ValueError, msg=bad):
                contract.wrapper(self.refrozen(bundle, **bad))
        disguised = self.refrozen(bundle, program=archive.getvalue())
        with self.assertRaises(ValueError):       # refused again at run time, whatever admitted it
            route.run_program(disguised, core)
        wrong_verifier = copy.deepcopy(bundle); wrong_verifier["instrument"]["verifier"] = "hypersearch.zero-sum-census/v1"
        renamed = copy.deepcopy(bundle); renamed["artifacts"]["program"]["path"] = "program.sh"
        unbound = copy.deepcopy(bundle); unbound["question"]["arguments"] = {"n": 2}       # manifest not re-frozen
        for bad in (wrong_verifier, renamed, unbound):
            with self.assertRaises(ValueError):
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
                       {"result_checked_by_instrument": True}, {"formal_proof": True}, {"scope": "other"},
                       {"evidence_kind": "proof"}, {"novelty_assessed": True}, {"summary": {"x": "y" * 70000}},
                       {"extra": 1}):
            with self.assertRaises(ValueError, msg=change):
                contract.verification(dict(honest, **change), bundle)
        for forged in ({"status": "PROGRAM_FAILS", "verification": honest}, {"status": "VERIFIED_WITNESS", "verification": None},
                       {"status": "INCOMPLETE", "verification": honest}):
            with self.assertRaises(ValueError, msg=forged["status"]):
                contract.outcome(forged, bundle)
        self.assertEqual(contract.outcome({"status": "INCOMPLETE", "verification": None}, bundle)["status"], "INCOMPLETE")

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
