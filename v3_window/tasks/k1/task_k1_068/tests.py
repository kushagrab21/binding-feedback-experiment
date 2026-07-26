"""Deterministic unittest suite for seed_023 (parse_roman).

The function under test is imported from ``solution``; whoever runs this
suite first copies the code-under-test to ``solution.py`` in the working
directory. Stdlib ``unittest`` only.
"""

import unittest

from solution import parse_roman


class TestParseRoman(unittest.TestCase):
    def test_additive(self):
        self.assertEqual(parse_roman("III"), 3)

    def test_simple_subtractive(self):
        self.assertEqual(parse_roman("IV"), 4)

    def test_subtractive_nine(self):
        self.assertEqual(parse_roman("IX"), 9)

    def test_mixed(self):
        self.assertEqual(parse_roman("LVIII"), 58)

    def test_large_compound(self):
        self.assertEqual(parse_roman("MCMXCIV"), 1994)

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            parse_roman("")

    def test_unknown_symbol_raises(self):
        with self.assertRaises(ValueError):
            parse_roman("IIU")


if __name__ == "__main__":
    unittest.main()
