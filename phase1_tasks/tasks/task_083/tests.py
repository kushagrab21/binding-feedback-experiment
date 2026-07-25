"""Deterministic unittest suite for seed_022 (parse_hhmm).

The function under test is imported from ``solution``; whoever runs this
suite first copies the code-under-test to ``solution.py`` in the working
directory. Stdlib ``unittest`` only.
"""

import unittest

from solution import parse_hhmm


class TestParseHhmm(unittest.TestCase):
    def test_midnight(self):
        self.assertEqual(parse_hhmm("00:00"), 0)

    def test_end_of_day(self):
        self.assertEqual(parse_hhmm("23:59"), 1439)

    def test_typical(self):
        self.assertEqual(parse_hhmm("13:45"), 825)

    def test_hour_out_of_range_raises(self):
        with self.assertRaises(ValueError):
            parse_hhmm("24:00")

    def test_wrong_shape_raises(self):
        with self.assertRaises(ValueError):
            parse_hhmm("1:00")

    def test_non_digit_field_raises(self):
        with self.assertRaises(ValueError):
            parse_hhmm("aa:bb")

    def test_minute_out_of_range_raises(self):
        with self.assertRaises(ValueError):
            parse_hhmm("12:60")


if __name__ == "__main__":
    unittest.main()
