"""Deterministic unittest suite for seed_011 (chunk).

The function under test is imported from ``solution``; whoever runs this
suite first copies the code-under-test to ``solution.py`` in the working
directory. Stdlib ``unittest`` only.
"""

import unittest

from solution import chunk


class TestChunk(unittest.TestCase):
    def test_uneven_final_chunk(self):
        self.assertEqual(chunk([1, 2, 3, 4, 5], 2), [[1, 2], [3, 4], [5]])

    def test_empty_sequence(self):
        self.assertEqual(chunk([], 3), [])

    def test_size_one(self):
        self.assertEqual(chunk([1, 2, 3], 1), [[1], [2], [3]])

    def test_size_larger_than_sequence(self):
        self.assertEqual(chunk([1, 2], 5), [[1, 2]])

    def test_exact_multiple(self):
        self.assertEqual(chunk([1, 2, 3, 4], 2), [[1, 2], [3, 4]])

    def test_size_zero_raises(self):
        with self.assertRaises(ValueError):
            chunk([1], 0)

    def test_negative_size_raises(self):
        with self.assertRaises(ValueError):
            chunk([1], -2)


if __name__ == "__main__":
    unittest.main()
