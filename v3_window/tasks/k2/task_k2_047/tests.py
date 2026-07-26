"""Deterministic unittest suite for seed_004 (gcd_two).

The function under test is imported from ``solution``; whoever runs this
suite first copies the code-under-test to ``solution.py`` in the working
directory. Stdlib ``unittest`` only.
"""

import unittest

from solution import gcd_two


class TestGcdTwo(unittest.TestCase):
    def test_typical(self):
        self.assertEqual(gcd_two(12, 18), 6)

    def test_one_argument_zero(self):
        self.assertEqual(gcd_two(0, 5), 5)

    def test_signs_ignored(self):
        self.assertEqual(gcd_two(-8, 12), 4)

    def test_equal_arguments(self):
        self.assertEqual(gcd_two(7, 7), 7)

    def test_order_independent(self):
        self.assertEqual(gcd_two(18, 12), 6)

    def test_coprime(self):
        self.assertEqual(gcd_two(9, 28), 1)

    def test_both_zero_raises(self):
        with self.assertRaises(ValueError):
            gcd_two(0, 0)


if __name__ == "__main__":
    unittest.main()
