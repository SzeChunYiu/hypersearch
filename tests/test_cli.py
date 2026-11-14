import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hypersearch.cli import execute_spec, main, VERIFIER
from hypersearch.store import Store
from hypersearch.math_adapter import search


class CliTests(unittest.TestCase):
    def test_end_to_end_and_reopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "run.sqlite")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(main(["demo", "--db", db]), 0)
            result = json.loads(out.getvalue())
            self.assertEqual(result["verification"]["lower_bound"], 4)
            self.assertFalse(result["verification"]["formal_proof"])
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(main(["demo", "--db", db]), 0)
            self.assertEqual(json.loads(out.getvalue())["execution"], "not_started")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["status", "--db", db]), 0)

    def test_invalid_demo_never_creates_persistent_state(self):
        invalid = (["--moduli", "0"], ["--moduli", "65"],
                   ["--moduli", "8", "9"], ["--moduli", "2", "2", "2", "2"],
                   ["--max-steps", "0"], ["--max-steps", "100001"])
        with tempfile.TemporaryDirectory() as tmp:
            for index, arguments in enumerate(invalid):
                with self.subTest(arguments=arguments):
                    db = Path(tmp) / f"invalid-{index}.sqlite"
                    with contextlib.redirect_stderr(io.StringIO()):
                        self.assertEqual(main(["demo", "--db", str(db), *arguments]), 2)
                    self.assertFalse(db.exists())

    def test_invalid_demo_leaves_pending_work_and_attempts_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "pending.sqlite"
            store = Store(db)
            spec = {"schema": "hypersearch.task/v1", "domain": "finite-abelian-zero-sum",
                    "moduli": [2], "max_steps": 10, "verifier": VERIFIER}
            store.submit("a-existing-task", spec)
            before = store.snapshot()
            for arguments in (["--moduli", "0"], ["--max-steps", "0"]):
                with self.subTest(arguments=arguments):
                    with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                        self.assertEqual(main(["demo", "--db", str(db), *arguments]), 2)
                    self.assertEqual(store.snapshot(), before)

    def test_admitted_execution_failure_remains_charged_and_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "failure.sqlite"
            with patch("hypersearch.cli.search", side_effect=ValueError("synthetic runtime failure")):
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(main(["demo", "--db", str(db)]), 2)
            state = Store(db).snapshot()
            self.assertEqual(state["budget"]["spent"], 1)
            self.assertEqual(len(state["tasks"]), 1)
            self.assertEqual(json.loads(state["results"][0]["result"])["execution"], "failed")
            self.assertEqual([event["kind"] for event in state["events"]],
                             ["submitted", "acquired", "completed"])

    def test_wrong_task_certificate_rejected(self):
        spec = {"schema": "hypersearch.task/v1", "domain": "finite-abelian-zero-sum",
                "moduli": [2, 2, 2], "max_steps": 100, "verifier": VERIFIER}
        with patch("hypersearch.cli.search", return_value=search([3])):
            with self.assertRaises(ValueError):
                execute_spec(spec)
        spec["verifier"] = "trust-me"
        with self.assertRaises(ValueError):
            execute_spec(spec)

    def test_verify_and_invalid_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "certificate.json"
            path.write_text(json.dumps(search([2, 2, 2])))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["verify", str(path), "--moduli", "2", "2", "2"]), 0)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(["verify", str(path), "--moduli", "3"]), 2)
                self.assertEqual(main(["demo", "--db", str(Path(tmp) / "invalid.sqlite"), "--moduli", "0"]), 2)



class MultiwiseCliTests(unittest.TestCase):
    def test_multwise_cli_bindings(self):
        cert = {"schema": "hypersearch.multiwise-certificate/v1", "moduli": [2], "k": 2,
                "sequence": [[1], [1], [1]]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "certificate.json"
            path.write_text(json.dumps(cert))
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["verify-multiwise", str(path), "--moduli", "2", "--k", "2"]), 0)
            self.assertEqual(json.loads(output.getvalue())["lower_bound"], 4)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(["verify-multiwise", str(path), "--moduli", "2", "--k", "3"]), 2)


if __name__ == "__main__":
    unittest.main()
