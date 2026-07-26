"""Deterministic unittest suite for seed_020 (bubble_sort).

The function under test is imported from ``solution``; whoever runs this
suite first copies the code-under-test to ``solution.py`` in the working
directory. Stdlib ``unittest`` only.

seed_020 is input-mutation-eligible: its contract says the input list is
not mutated, so one test asserts the argument is unchanged after the call.
"""

import unittest

from solution import bubble_sort


class TestBubbleSort(unittest.TestCase):
    def test_typical(self):
        self.assertEqual(bubble_sort([3, 1, 2]), [1, 2, 3])

    def test_empty_list(self):
        self.assertEqual(bubble_sort([]), [])

    def test_single_element(self):
        self.assertEqual(bubble_sort([1]), [1])

    def test_reverse_sorted(self):
        self.assertEqual(bubble_sort([5, 4, 3, 2, 1]), [1, 2, 3, 4, 5])

    def test_with_duplicates(self):
        self.assertEqual(bubble_sort([2, 2, 1]), [1, 2, 2])

    def test_input_not_mutated(self):
        arg = [3, 1, 2]
        bubble_sort(arg)
        self.assertEqual(arg, [3, 1, 2])


if __name__ == "__main__":
    unittest.main()
