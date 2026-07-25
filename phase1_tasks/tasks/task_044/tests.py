"""Deterministic unittest suite for seed_012 (rotate_left).

The function under test is imported from ``solution``; whoever runs this
suite first copies the code-under-test to ``solution.py`` in the working
directory. Stdlib ``unittest`` only.

seed_012 is input-mutation-eligible: its contract says the input is not
mutated, so one test asserts the argument is unchanged after the call.
"""

import unittest

from solution import rotate_left


class TestRotateLeft(unittest.TestCase):
    def test_typical(self):
        self.assertEqual(rotate_left([1, 2, 3, 4], 1), [2, 3, 4, 1])

    def test_negative_rotates_right(self):
        self.assertEqual(rotate_left([1, 2, 3], -1), [3, 1, 2])

    def test_empty_sequence(self):
        self.assertEqual(rotate_left([], 2), [])

    def test_k_equal_length_is_identity(self):
        self.assertEqual(rotate_left([1, 2, 3], 3), [1, 2, 3])

    def test_k_larger_than_length_wraps(self):
        self.assertEqual(rotate_left([1, 2, 3], 5), [3, 1, 2])

    def test_input_not_mutated(self):
        arg = [1, 2, 3, 4]
        rotate_left(arg, 1)
        self.assertEqual(arg, [1, 2, 3, 4])


if __name__ == "__main__":
    unittest.main()
