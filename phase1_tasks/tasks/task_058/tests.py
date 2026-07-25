"""Deterministic unittest suite for seed_016 (is_valid_identifier).

The function under test is imported from ``solution``; whoever runs this
suite first copies the code-under-test to ``solution.py`` in the working
directory. Stdlib ``unittest`` only.
"""

import unittest

from solution import is_valid_identifier


class TestIsValidIdentifier(unittest.TestCase):
    def test_underscore_start_with_digit(self):
        self.assertTrue(is_valid_identifier("_x1"))

    def test_letters_digits_underscore(self):
        self.assertTrue(is_valid_identifier("Abc_9"))

    def test_bare_underscore(self):
        self.assertTrue(is_valid_identifier("_"))

    def test_leading_digit_invalid(self):
        self.assertFalse(is_valid_identifier("1x"))

    def test_empty_invalid(self):
        self.assertFalse(is_valid_identifier(""))

    def test_hyphen_invalid(self):
        self.assertFalse(is_valid_identifier("a-b"))

    def test_single_digit_invalid(self):
        self.assertFalse(is_valid_identifier("9"))


if __name__ == "__main__":
    unittest.main()
