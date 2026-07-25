"""Deterministic unittest suite for seed_010 (flatten_one_level).

The function under test is imported from ``solution``; whoever runs this
suite first copies the code-under-test to ``solution.py`` in the working
directory. Stdlib ``unittest`` only.

seed_010 is input-mutation-eligible: its contract implies the nested input
is only read, so one test asserts the argument is unchanged after the call.
"""

import unittest

from solution import flatten_one_level


class TestFlattenOneLevel(unittest.TestCase):
    def test_typical(self):
        self.assertEqual(flatten_one_level([[1, 2], [3]]), [1, 2, 3])

    def test_empty_outer(self):
        self.assertEqual(flatten_one_level([]), [])

    def test_empty_inner(self):
        self.assertEqual(flatten_one_level([[], [1]]), [1])

    def test_singleton_sublists(self):
        self.assertEqual(flatten_one_level([[1], [2], [3]]), [1, 2, 3])

    def test_only_one_level_removed(self):
        self.assertEqual(flatten_one_level([[1, [2]], [3]]), [1, [2], 3])

    def test_input_not_mutated(self):
        arg = [[1, 2], [3]]
        flatten_one_level(arg)
        self.assertEqual(arg, [[1, 2], [3]])


if __name__ == "__main__":
    unittest.main()
