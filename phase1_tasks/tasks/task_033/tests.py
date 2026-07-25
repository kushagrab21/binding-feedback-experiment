"""Deterministic unittest suite for seed_009 (second_largest).

The function under test is imported from ``solution``; whoever runs this
suite first copies the code-under-test to ``solution.py`` in the working
directory. Stdlib ``unittest`` only.
"""

import unittest

from solution import second_largest


class TestSecondLargest(unittest.TestCase):
    def test_duplicates_collapsed(self):
        self.assertEqual(second_largest([5, 5, 3]), 3)

    def test_sorted_ascending(self):
        self.assertEqual(second_largest([1, 2, 3]), 2)

    def test_unordered_with_repeats(self):
        self.assertEqual(second_largest([3, 1, 2, 3, 1]), 2)

    def test_negatives(self):
        self.assertEqual(second_largest([-1, -2]), -2)

    def test_single_value_raises(self):
        with self.assertRaises(ValueError):
            second_largest([1])

    def test_all_equal_raises(self):
        with self.assertRaises(ValueError):
            second_largest([7, 7, 7])


if __name__ == "__main__":
    unittest.main()
