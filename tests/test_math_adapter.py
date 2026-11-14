import copy
import unittest

from hypersearch.math_adapter import _digest, search, verify_certificate


class MathAdapterTests(unittest.TestCase):
    def changed(self, sequence, moduli):
        cert = search(moduli, max_steps=1)
        cert["sequence"] = sequence
        cert["lower_bound"] = len(sequence) + 1
        cert["sha256"] = _digest(cert)
        return cert

    def test_rank_three_regression(self):
        cert = search([2, 2, 2])
        result = verify_certificate(cert)
        self.assertTrue(result["verified"])
        self.assertEqual(result["lower_bound"], 4)
        self.assertEqual(result["subsets_checked"], 7)
        self.assertFalse(result["formal_proof"])
        self.assertFalse(result["novelty_assessed"])

    def test_search_deterministic_and_budget_bounded(self):
        a = search([2, 3, 4], max_steps=7)
        self.assertEqual(a, search([2, 3, 4], max_steps=7))
        self.assertEqual(a["search"]["steps"], 7)
        self.assertTrue(a["search"]["step_cap_reached"])
        self.assertTrue(verify_certificate(a)["verified"])
        self.assertEqual(verify_certificate(a)["scope"], "finite_group_lower_bound")

    def test_zero_singleton_rejected(self):
        self.assertFalse(verify_certificate(self.changed([[0]], [3]))["verified"])

    def test_repeated_positions_are_not_deduplicated(self):
        result = verify_certificate(self.changed([[1], [1], [1]], [3]))
        self.assertFalse(result["verified"])
        self.assertEqual(result["counterexample_indices"], [0, 1, 2])

    def test_sum_of_four_rejected(self):
        cert = self.changed([[1, 0, 0], [0, 1, 0], [0, 0, 1], [1, 1, 1]], [2, 2, 2])
        self.assertFalse(verify_certificate(cert)["verified"])

    def test_tampering_rejected(self):
        cert = search([3])
        cert["sequence"][0][0] = 0
        with self.assertRaises(ValueError):
            verify_certificate(cert)

    def test_frozen_task_group_binding(self):
        cert = search([2, 2, 2])
        self.assertTrue(verify_certificate(cert, expected_moduli=[2, 2, 2])["verified"])
        with self.assertRaises(ValueError):
            verify_certificate(cert, expected_moduli=[3, 3, 3])

    def test_malformed_inputs_and_caps(self):
        for moduli in ([], [True], [1], [2.0], [2, 2, 2, 2], [65], [8, 9]):
            with self.subTest(moduli=moduli), self.assertRaises(ValueError):
                search(moduli)
        for budget in (True, 0, -1, 100001, 1.5):
            with self.subTest(budget=budget), self.assertRaises(ValueError):
                search([2], budget)
        for sequence in ([[True]], [[-1]], [[3]], [[1, 2]], [[1]] * 17):
            cert = self.changed(sequence, [3])
            with self.subTest(sequence=sequence), self.assertRaises(ValueError):
                verify_certificate(cert)

    def test_no_false_bound_or_unknown_fields(self):
        original = search([3])
        for key, value in (("lower_bound", 99), ("version", True), ("kind", "theorem"), ("extra", 1)):
            cert = copy.deepcopy(original)
            cert[key] = value
            cert["sha256"] = _digest(cert)
            with self.subTest(key=key), self.assertRaises(ValueError):
                verify_certificate(cert)


if __name__ == "__main__":
    unittest.main()
