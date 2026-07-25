"""Deterministic unittest suite for seed_014 (merge_sum).

The function under test is imported from ``solution``; whoever runs this
suite first copies the code-under-test to ``solution.py`` in the working
directory. Stdlib ``unittest`` only.

seed_014 is input-mutation-eligible: its contract says neither input is
mutated, so one test asserts both arguments are unchanged after the call.
"""

import unittest

from solution import merge_sum


class TestMergeSum(unittest.TestCase):
    def test_shared_keys_summed(self):
        self.assertEqual(
            merge_sum({"a": 1, "b": 2}, {"b": 3, "c": 4}),
            {"a": 1, "b": 5, "c": 4})

    def test_both_empty(self):
        self.assertEqual(merge_sum({}, {}), {})

    def test_second_empty(self):
        self.assertEqual(merge_sum({"x": 1}, {}), {"x": 1})

    def test_first_empty(self):
        self.assertEqual(merge_sum({}, {"y": 2}), {"y": 2})

    def test_colliding_values_cancel(self):
        self.assertEqual(merge_sum({"k": 1}, {"k": -1}), {"k": 0})

    def test_inputs_not_mutated(self):
        a = {"a": 1, "b": 2}
        b = {"b": 3, "c": 4}
        merge_sum(a, b)
        self.assertEqual(a, {"a": 1, "b": 2})
        self.assertEqual(b, {"b": 3, "c": 4})


if __name__ == "__main__":
    unittest.main()
