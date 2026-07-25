"""Deterministic unittest suite for seed_001 (clamp).

The function under test is imported from ``solution``; whoever runs this
suite first copies the code-under-test to ``solution.py`` in the working
directory. Stdlib ``unittest`` only.
"""

import unittest

from solution import clamp


class TestClamp(unittest.TestCase):
    def test_value_within_range_unchanged(self):
        self.assertEqual(clamp(5, 0, 10), 5)

    def test_value_below_low_clamped_up(self):
        self.assertEqual(clamp(-3, 0, 10), 0)

    def test_value_above_high_clamped_down(self):
        self.assertEqual(clamp(99, 0, 10), 10)

    def test_boundary_equal_to_low(self):
        self.assertEqual(clamp(0, 0, 10), 0)

    def test_boundary_equal_to_high(self):
        self.assertEqual(clamp(10, 0, 10), 10)

    def test_degenerate_single_point_range(self):
        self.assertEqual(clamp(7, 3, 3), 3)

    def test_low_greater_than_high_raises(self):
        with self.assertRaises(ValueError):
            clamp(1, 10, 0)


if __name__ == "__main__":
    unittest.main()
