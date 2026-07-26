"""Deterministic unittest suite for seed_019 (binary_search).

The function under test is imported from ``solution``; whoever runs this
suite first copies the code-under-test to ``solution.py`` in the working
directory. Stdlib ``unittest`` only.
"""

import unittest

from solution import binary_search


class TestBinarySearch(unittest.TestCase):
    def test_found_in_middle(self):
        self.assertEqual(binary_search([1, 3, 5, 7], 5), 2)

    def test_absent_returns_minus_one(self):
        self.assertEqual(binary_search([1, 3, 5, 7], 4), -1)

    def test_empty_list(self):
        self.assertEqual(binary_search([], 1), -1)

    def test_first_element(self):
        self.assertEqual(binary_search([1, 3, 5, 7], 1), 0)

    def test_last_element(self):
        self.assertEqual(binary_search([1, 3, 5, 7], 7), 3)

    def test_single_element_found(self):
        self.assertEqual(binary_search([5], 5), 0)

    def test_single_element_absent(self):
        self.assertEqual(binary_search([5], 3), -1)


if __name__ == "__main__":
    unittest.main()
