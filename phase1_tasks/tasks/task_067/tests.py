"""Deterministic unittest suite for seed_018 (all_unique).

The function under test is imported from ``solution``; whoever runs this
suite first copies the code-under-test to ``solution.py`` in the working
directory. Stdlib ``unittest`` only.
"""

import unittest

from solution import all_unique


class TestAllUnique(unittest.TestCase):
    def test_all_distinct(self):
        self.assertTrue(all_unique([1, 2, 3]))

    def test_duplicate_present(self):
        self.assertFalse(all_unique([1, 1]))

    def test_empty_is_unique(self):
        self.assertTrue(all_unique([]))

    def test_single_is_unique(self):
        self.assertTrue(all_unique([1]))

    def test_duplicate_strings(self):
        self.assertFalse(all_unique(["a", "b", "a"]))

    def test_distinct_strings(self):
        self.assertTrue(all_unique(["a", "b", "c"]))


if __name__ == "__main__":
    unittest.main()
