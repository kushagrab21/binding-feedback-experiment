"""Deterministic unittest suite for seed_008 (caesar_shift).

The function under test is imported from ``solution``; whoever runs this
suite first copies the code-under-test to ``solution.py`` in the working
directory. Stdlib ``unittest`` only.
"""

import unittest

from solution import caesar_shift


class TestCaesarShift(unittest.TestCase):
    def test_mixed_case_shift(self):
        self.assertEqual(caesar_shift("abcXYZ", 1), "bcdYZA")

    def test_zero_shift_identity(self):
        self.assertEqual(caesar_shift("abc", 0), "abc")

    def test_lowercase_wraps(self):
        self.assertEqual(caesar_shift("xyz", 3), "abc")

    def test_negative_shift(self):
        self.assertEqual(caesar_shift("Hi!", -1), "Gh!")

    def test_non_letters_unchanged(self):
        self.assertEqual(caesar_shift("a b!", 1), "b c!")

    def test_shift_reduced_modulo_26(self):
        self.assertEqual(caesar_shift("abc", 27), "bcd")

    def test_empty_string(self):
        self.assertEqual(caesar_shift("", 5), "")


if __name__ == "__main__":
    unittest.main()
