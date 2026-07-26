"""Deterministic unittest suite for seed_002 (digit_sum).

The function under test is imported from ``solution``; whoever runs this
suite first copies the code-under-test to ``solution.py`` in the working
directory. Stdlib ``unittest`` only.
"""

import unittest

from solution import digit_sum


class TestDigitSum(unittest.TestCase):
    def test_multi_digit(self):
        self.assertEqual(digit_sum(1234), 10)

    def test_zero_boundary(self):
        self.assertEqual(digit_sum(0), 0)

    def test_single_digit(self):
        self.assertEqual(digit_sum(9), 9)

    def test_trailing_zeros(self):
        self.assertEqual(digit_sum(100), 1)

    def test_large_value(self):
        self.assertEqual(digit_sum(999999), 54)

    def test_negative_raises(self):
        with self.assertRaises(ValueError):
            digit_sum(-1)


if __name__ == "__main__":
    unittest.main()
