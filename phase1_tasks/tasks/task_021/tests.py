"""Deterministic unittest suite for seed_006 (count_vowels).

The function under test is imported from ``solution``; whoever runs this
suite first copies the code-under-test to ``solution.py`` in the working
directory. Stdlib ``unittest`` only.
"""

import unittest

from solution import count_vowels


class TestCountVowels(unittest.TestCase):
    def test_empty_string(self):
        self.assertEqual(count_vowels(""), 0)

    def test_all_vowels_mixed_case(self):
        self.assertEqual(count_vowels("AeiOux"), 5)

    def test_no_vowels(self):
        self.assertEqual(count_vowels("bcdfg"), 0)

    def test_y_is_not_a_vowel(self):
        self.assertEqual(count_vowels("Yy"), 0)

    def test_single_vowel(self):
        self.assertEqual(count_vowels("a"), 1)

    def test_ignores_non_letters(self):
        self.assertEqual(count_vowels("a1e!o"), 3)


if __name__ == "__main__":
    unittest.main()
