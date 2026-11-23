"""Unit and adversarial tests for exact & odd-modular linear infeasibility certificates."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import tempfile
import time
import unittest

from hypersearch.cli import main as cli_main
from hypersearch.linear_infeasibility import (
    SCHEMA,
    VERIFIER,
    check_certificate_file,
    factor_positive_int,
    is_probable_prime_13,
    make_certificate_bundle,
    make_certificate_entry,
    system_digest,
    verify_bundle,
    verify_entry,
)
from hypersearch.study_json import encode


class LinearInfeasibilityTests(unittest.TestCase):
    def _sample_integer_entry(self, entry_id: str = "sys-int-1") -> dict:
        # x + y = 1, x - y = 1, 2x = 5 -> u = [1, 1, -1]: uM = [0, 0], u.b = -3
        return make_certificate_entry(
            entry_id=entry_id,
            num_rows=3,
            num_cols=2,
            rows=[[[0, 1], [1, 1]], [[0, 1], [1, -1]], [[0, 2]]],
            b=[1, 1, 5],
            u=[1, 1, -1],
            modulus=None,
        )

    def _sample_modular_entry(self, entry_id: str = "sys-mod-7") -> dict:
        # Over F_7: 2x + 3y = 1, 4x + 6y = 5 -> u = [2, -1]: uM = [0, 0] mod 7, u.b = -3 == 4 mod 7
        return make_certificate_entry(
            entry_id=entry_id,
            num_rows=2,
            num_cols=2,
            rows=[[[0, 2], [1, 3]], [[0, 4], [1, 6]]],
            b=[1, 5],
            u=[2, -1],
            modulus=7,
        )

    def test_exact_integer_and_odd_modular_verification(self) -> None:
        e_int = self._sample_integer_entry()
        e_int2 = make_certificate_entry(
            entry_id="sys-int-2",
            num_rows=2,
            num_cols=2,
            rows=[[[0, 3], [1, 6]], [[0, 1], [1, 2]]],
            b=[2, 4],
            u=[1, -3],  # uM = [0, 0], u.b = 2 - 12 = -10 (primes 2, 5)
            modulus=None,
        )
        e_mod = self._sample_modular_entry()
        bundle = make_certificate_bundle([e_int, e_int2, e_mod])
        receipt = verify_bundle(bundle)
        self.assertTrue(receipt["verified"])
        self.assertEqual(receipt["verifier"], VERIFIER)
        self.assertEqual(receipt["schema"], SCHEMA)
        self.assertEqual(receipt["entry_count"], 3)
        self.assertEqual(receipt["verified_count"], 3)
        self.assertEqual(receipt["failed_entries"], [])
        self.assertEqual(receipt["union_exceptional_primes"], [2, 3, 5])
        self.assertTrue(receipt["factorization_complete"])
        self.assertFalse(receipt["formal_proof"])
        self.assertFalse(receipt["novelty_assessed"])
        self.assertEqual(receipt["entries"][2]["mode"], "odd_modular")
        self.assertTrue(receipt["entries"][2]["modulus_is_prime"])
        self.assertEqual(receipt["entries"][2]["g_mod"], 4)

    def test_miller_rabin_13_and_pollard_brent_factorization(self) -> None:
        # Carmichael numbers must be rejected as composite
        for carmichael in (561, 1105, 1729, 2465, 2821, 6601, 8911, 341550071728321):
            self.assertFalse(is_probable_prime_13(carmichael), str(carmichael))
        for prime in (2, 3, 5, 1000003, 1000000007, 2305843009213693951):
            self.assertTrue(is_probable_prime_13(prime), str(prime))

        # Semiprime with large factors beyond trial division (1000003 * 1000033)
        n = 1000003 * 1000033 * 13 * 13
        fac = factor_positive_int(n)
        self.assertTrue(fac["complete"])
        self.assertEqual(fac["primes"], [13, 1000003, 1000033])
        self.assertEqual(fac["prime_powers"], [[13, 2], [1000003, 1], [1000033, 1]])

        # Bounded Pollard-Brent with tiny step budget records unfactored cofactor cleanly
        fac_bounded = factor_positive_int(1000000007 * 1000000009, max_pollard_steps=4)
        self.assertFalse(fac_bounded["complete"])
        self.assertEqual(fac_bounded["unfactored_cofactors"], [1000000007 * 1000000009])

    def test_planted_wrong_certificates_refused(self) -> None:
        # 1. Flipped matrix entry (re-signed digest) -> uM != 0
        flipped = make_certificate_entry(
            entry_id="bad-flip",
            num_rows=3,
            num_cols=2,
            rows=[[[0, 2], [1, 1]], [[0, 1], [1, -1]], [[0, 2]]],
            b=[1, 1, 5],
            u=[1, 1, -1],
        )
        res_flip = verify_entry(flipped)
        self.assertFalse(res_flip["verified"])
        self.assertEqual(res_flip["reason"], "nonzero_left_kernel_product")

        # 2. g == 0 -> u.b == 0
        zero_g = make_certificate_entry(
            entry_id="bad-zero-g",
            num_rows=3,
            num_cols=2,
            rows=[[[0, 1], [1, 1]], [[0, 1], [1, -1]], [[0, 2]]],
            b=[1, 1, 2],
            u=[1, 1, -1],
        )
        res_zero = verify_entry(zero_g)
        self.assertFalse(res_zero["verified"])
        self.assertEqual(res_zero["reason"], "zero_rhs_dot_product")

        # 3. Modular g % m == 0
        zero_mod = make_certificate_entry(
            entry_id="bad-mod-zero",
            num_rows=2,
            num_cols=2,
            rows=[[[0, 2], [1, 3]], [[0, 4], [1, 6]]],
            b=[1, 2],
            u=[2, -1],
            modulus=7,
        )
        self.assertFalse(verify_entry(zero_mod)["verified"])

        # 3b. Composite odd modulus with non-unit gcd(u.b, m) > 1 refused; unit gcd == 1 accepted
        non_unit_mod = make_certificate_entry(
            entry_id="bad-mod-nonunit",
            num_rows=2,
            num_cols=1,
            rows=[[[0, 5]], [[0, 10]]],
            b=[1, 5],
            u=[2, -1],  # uM = 0 mod 15, u.b = -3 = 12 mod 15, gcd(12, 15) = 3 != 1
            modulus=15,
        )
        res_nu = verify_entry(non_unit_mod)
        self.assertFalse(res_nu["verified"])
        self.assertEqual(res_nu["reason"], "non_unit_modular_rhs_dot_product")

        unit_mod = make_certificate_entry(
            entry_id="ok-mod-unit",
            num_rows=2,
            num_cols=1,
            rows=[[[0, 5]], [[0, 10]]],
            b=[1, 4],
            u=[2, -1],  # uM = 0 mod 15, u.b = -2 = 13 mod 15, gcd(13, 15) = 1
            modulus=15,
        )
        self.assertTrue(verify_entry(unit_mod)["verified"])

        # 4. Wrong system_sha256
        wrong_sha = dict(self._sample_integer_entry())
        wrong_sha["system_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "system_sha256"):
            verify_entry(wrong_sha)

        # 5. Expected system digest mismatch
        valid = self._sample_integer_entry()
        with self.assertRaisesRegex(ValueError, "expected task system"):
            verify_entry(valid, expected_system_sha256="f" * 64)

    def test_malformed_noncanonical_and_truncated_files_refused(self) -> None:
        bundle = make_certificate_bundle([self._sample_integer_entry()])
        raw = encode(bundle)
        with tempfile.TemporaryDirectory() as tmp:
            td = Path(tmp)
            good = td / "good.json"
            good.write_bytes(raw + b"\n")
            rec = check_certificate_file(good, expected_bundle_sha256=verify_bundle(bundle)["bundle_sha256"])
            self.assertTrue(rec["verified"])

            # Non-canonical whitespace refused by default
            pretty = td / "pretty.json"
            pretty.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "canonical"):
                check_certificate_file(pretty)

            # Truncated file refused
            trunc = td / "trunc.json"
            trunc.write_bytes(raw[: len(raw) // 2])
            with self.assertRaises(ValueError):
                check_certificate_file(trunc)

            # Even modulus refused
            with self.assertRaisesRegex(ValueError, "odd modulus"):
                system_digest(1, 1, [[[0, 1]]], [1], modulus=4)

            # Out-of-order sparse columns & explicit zero entry refused
            with self.assertRaisesRegex(ValueError, "strictly increasing"):
                system_digest(1, 2, [[[1, 1], [0, 1]]], [1])
            with self.assertRaisesRegex(ValueError, "zero entries"):
                system_digest(1, 2, [[[0, 0]]], [1])

    def test_cli_check_certificates_exit_codes(self) -> None:
        good_entry = self._sample_integer_entry("c1")
        bad_entry = make_certificate_entry(
            entry_id="c_bad", num_rows=2, num_cols=1,
            rows=[[[0, 1]], [[0, 1]]], b=[1, 1], u=[1, -1],
        )
        with tempfile.TemporaryDirectory() as tmp:
            td = Path(tmp)
            p_good = td / "good.json"
            p_good.write_bytes(encode(make_certificate_bundle([good_entry])))
            p_sys = td / "systems.json"
            p_sys.write_bytes(encode({"c1": good_entry["system_sha256"]}))
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = cli_main(["check-certificates", str(p_good), "--expected-systems", str(p_sys)])
            self.assertEqual(rc, 0)
            self.assertTrue(json.loads(out.getvalue())["verified"])

            p_bad = td / "bad.json"
            p_bad.write_bytes(encode(make_certificate_bundle([bad_entry])))
            out2 = io.StringIO()
            with contextlib.redirect_stdout(out2):
                rc2 = cli_main(["check-certificates", str(p_bad)])
            self.assertEqual(rc2, 1)
            self.assertFalse(json.loads(out2.getvalue())["verified"])

            # Malformed file -> exit 2
            p_mal = td / "mal.json"
            p_mal.write_text("{not json", encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()):
                rc3 = cli_main(["check-certificates", str(p_mal)])
            self.assertEqual(rc3, 2)

    def test_no_private_strings_and_fast_check_timing(self) -> None:
        mod_src = (Path(__file__).resolve().parents[1] / "src/hypersearch/linear_infeasibility.py").read_text(encoding="utf-8").lower()
        for forbidden in ("/home/", "c" + "lm-", "ai-math-" + "research"):
            self.assertNotIn(forbidden, mod_src)

        entries = [self._sample_integer_entry(f"e-{i}") for i in range(64)]
        bundle = make_certificate_bundle(entries)
        t0 = time.perf_counter()
        receipt = verify_bundle(bundle)
        elapsed = time.perf_counter() - t0
        self.assertTrue(receipt["verified"])
        self.assertEqual(receipt["verified_count"], 64)
        self.assertLess(elapsed, 2.0)


if __name__ == "__main__":
    unittest.main()
