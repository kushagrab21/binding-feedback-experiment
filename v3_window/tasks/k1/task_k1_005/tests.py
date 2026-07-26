"""Deterministic unittest suite for seed_005 (is_palindrome).

The function under test is imported from ``solution``; whoever runs this
suite first copies the code-under-test to ``solution.py`` in the working
directory. Stdlib ``unittest`` only.
"""

import unittest

from solution import is_palindrome


class TestIsPalindrome(unittest.TestCase):
    def test_empty_is_palindrome(self):
        self.assertTrue(is_palindrome(""))

    def test_single_char_is_palindrome(self):
        self.assertTrue(is_palindrome("a"))

    def test_odd_length_palindrome(self):
        self.assertTrue(is_palindrome("aba"))

    def test_even_length_palindrome(self):
        self.assertTrue(is_palindrome("abba"))

    def test_non_palindrome(self):
        self.assertFalse(is_palindrome("ab"))

    def test_case_sensitive(self):
        self.assertFalse(is_palindrome("Aa"))


if __name__ == "__main__":
    unittest.main()
