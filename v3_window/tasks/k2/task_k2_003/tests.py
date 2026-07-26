"""Deterministic unittest suite for seed_003 (count_divisors).

The function under test is imported from ``solution``; whoever runs this
suite first copies the code-under-test to ``solution.py`` in the working
directory. Stdlib ``unittest`` only.
"""

import unittest

from solution import count_divisors


class TestCountDivisors(unittest.TestCase):
    def test_one_boundary(self):
        self.assertEqual(count_divisors(1), 1)

    def test_prime_has_two(self):
        self.assertEqual(count_divisors(7), 2)

    def test_composite(self):
        self.assertEqual(count_divisors(6), 4)

    def test_highly_composite(self):
        self.assertEqual(count_divisors(12), 6)

    def test_perfect_square(self):
        self.assertEqual(count_divisors(9), 3)

    def test_zero_raises(self):
        with self.assertRaises(ValueError):
            count_divisors(0)

    def test_negative_raises(self):
        with self.assertRaises(ValueError):
            count_divisors(-4)


if __name__ == "__main__":
    unittest.main()
