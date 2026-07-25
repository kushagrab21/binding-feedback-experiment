"""Deterministic unittest suite for seed_007 (reverse_words).

The function under test is imported from ``solution``; whoever runs this
suite first copies the code-under-test to ``solution.py`` in the working
directory. Stdlib ``unittest`` only.
"""

import unittest

from solution import reverse_words


class TestReverseWords(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(reverse_words("a b c"), "c b a")

    def test_empty_string(self):
        self.assertEqual(reverse_words(""), "")

    def test_single_word(self):
        self.assertEqual(reverse_words("single"), "single")

    def test_collapses_internal_whitespace(self):
        self.assertEqual(reverse_words("x  y"), "y x")

    def test_strips_leading_and_trailing(self):
        self.assertEqual(reverse_words("  a  b c "), "c b a")

    def test_whitespace_only_is_empty(self):
        self.assertEqual(reverse_words("   "), "")


if __name__ == "__main__":
    unittest.main()
