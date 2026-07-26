"""Deterministic unittest suite for seed_017 (is_leap_year).

The function under test is imported from ``solution``; whoever runs this
suite first copies the code-under-test to ``solution.py`` in the working
directory. Stdlib ``unittest`` only.
"""

import unittest

from solution import is_leap_year


class TestIsLeapYear(unittest.TestCase):
    def test_divisible_by_400(self):
        self.assertTrue(is_leap_year(2000))

    def test_century_not_divisible_by_400(self):
        self.assertFalse(is_leap_year(1900))

    def test_divisible_by_4(self):
        self.assertTrue(is_leap_year(2024))

    def test_not_divisible_by_4(self):
        self.assertFalse(is_leap_year(2023))

    def test_another_non_leap_century(self):
        self.assertFalse(is_leap_year(2100))

    def test_another_leap_century(self):
        self.assertTrue(is_leap_year(2400))


if __name__ == "__main__":
    unittest.main()
