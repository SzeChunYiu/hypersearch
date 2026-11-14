import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hypersearch.cli import execute_spec, main, VERIFIER
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


if __name__ == "__main__":
    unittest.main()

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
