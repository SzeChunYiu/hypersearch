from itertools import product
import unittest

from hypersearch.multiwise import SCHEMA, verify_certificate


def cert(moduli, k, sequence):
    return {"schema": SCHEMA, "moduli": moduli, "k": k, "sequence": sequence}


def oracle(ns, sequence):
    # Independent exhaustive assignment: every indexed term is omitted or
    # assigned to one of n labelled blocks; count nonempty zero-sum blocks.
    n = len(sequence)
    maximum = 0
    for labels in product(range(n + 1), repeat=n):
        count = 0
        for label in range(1, n + 1):
            indices = [i for i, value in enumerate(labels) if value == label]
            if indices and all(sum(sequence[i][j] for i in indices) % m == 0
                               for j, m in enumerate(ns)):
                count += 1
        maximum = max(maximum, count)
    return maximum


class MultiwiseTests(unittest.TestCase):
    def test_exhaustive_tiny_against_assignment_oracle(self):
        for n in range(5):
            for sequence in product(range(2), repeat=n):
                terms = [[x] for x in sequence]
                receipt = verify_certificate(cert([2], 2, terms))
                self.assertEqual(receipt["maximum_disjoint_zero_sum_subsequences"], oracle([2], terms))

    def test_multiplicity_and_counterexample(self):
        receipt = verify_certificate(cert([2], 2, [[1]] * 4))
        self.assertFalse(receipt["verified"])
        self.assertNotIn("lower_bound", receipt)
        blocks = receipt["counterexample_indices"]
        self.assertEqual(len(blocks), 2)
        self.assertFalse(set(blocks[0]) & set(blocks[1]))
        self.assertEqual(sorted(blocks[0] + blocks[1]), list(range(4)))
        receipt = verify_certificate(cert([2], 2, [[1]] * 3))
        self.assertTrue(receipt["verified"])
        self.assertEqual(receipt["lower_bound"], 4)

    def test_k_one_and_rank_three_large_ambient_groups(self):
        for modulus in (5, 7, 11):
            receipt = verify_certificate(cert([modulus] * 3, 1, [[1, 0, 0]] * (modulus - 1)))
            self.assertTrue(receipt["verified"])
            self.assertEqual(receipt["lower_bound"], modulus)
            self.assertFalse(receipt["formal_proof"])
            self.assertFalse(receipt["novelty_assessed"])

    def test_empty_and_zero_terms(self):
        self.assertEqual(verify_certificate(cert([2], 1, []))["lower_bound"], 1)
        receipt = verify_certificate(cert([3], 3, [[0], [0], [0]]))
        self.assertFalse(receipt["verified"])
        self.assertEqual(receipt["maximum_disjoint_zero_sum_subsequences"], 3)

    def test_task_binding(self):
        candidate = cert([5, 5, 5], 2, [[1, 0, 0]])
        self.assertTrue(verify_certificate(candidate, expected_moduli=[5, 5, 5], expected_k=2)["verified"])
        with self.assertRaises(ValueError):
            verify_certificate(candidate, expected_moduli=[7, 7, 7])
        with self.assertRaises(ValueError):
            verify_certificate(candidate, expected_k=1)

    def test_invalid_and_over_cap_fail_closed(self):
        invalid = [cert([2], True, []), cert([2], 17, []), cert([True], 1, []),
                   cert([1000000, 2], 1, []), cert([2], 1, [[1]] * 17),
                   cert([2], 1, [[2]]), cert([2], 1, [[True]]), cert([2], 1, [[0, 0]])]
        extra = cert([2], 1, [])
        extra["verified"] = True
        invalid.append(extra)
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                verify_certificate(value)


if __name__ == "__main__":
    unittest.main()
