"""Deterministic unittest suite for seed_015 (most_common_char).

The function under test is imported from ``solution``; whoever runs this
suite first copies the code-under-test to ``solution.py`` in the working
directory. Stdlib ``unittest`` only.
"""

import unittest

from solution import most_common_char


class TestMostCommonChar(unittest.TestCase):
    def test_clear_majority(self):
        self.assertEqual(most_common_char("aabbb"), "b")

    def test_tie_breaks_to_earliest(self):
        self.assertEqual(most_common_char("abcabc"), "a")

    def test_single_char(self):
        self.assertEqual(most_common_char("x"), "x")

    def test_all_same(self):
        self.assertEqual(most_common_char("zzzz"), "z")

    def test_counts_non_letters(self):
        self.assertEqual(most_common_char("a..b."), ".")

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            most_common_char("")


if __name__ == "__main__":
    unittest.main()
