"""Deterministic unittest suite for seed_021 (parse_signed_int).

The function under test is imported from ``solution``; whoever runs this
suite first copies the code-under-test to ``solution.py`` in the working
directory. Stdlib ``unittest`` only.
"""

import unittest

from solution import parse_signed_int


class TestParseSignedInt(unittest.TestCase):
    def test_unsigned(self):
        self.assertEqual(parse_signed_int("42"), 42)

    def test_negative(self):
        self.assertEqual(parse_signed_int("-7"), -7)

    def test_positive_sign_zero(self):
        self.assertEqual(parse_signed_int("+0"), 0)

    def test_leading_zeros(self):
        self.assertEqual(parse_signed_int("007"), 7)

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            parse_signed_int("")

    def test_sign_only_raises(self):
        with self.assertRaises(ValueError):
            parse_signed_int("-")

    def test_trailing_non_digit_raises(self):
        with self.assertRaises(ValueError):
            parse_signed_int("1a")

    def test_leading_whitespace_raises(self):
        with self.assertRaises(ValueError):
            parse_signed_int(" 5")


if __name__ == "__main__":
    unittest.main()
