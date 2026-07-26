"""Deterministic unittest suite for seed_024 (parse_csv_line).

The function under test is imported from ``solution``; whoever runs this
suite first copies the code-under-test to ``solution.py`` in the working
directory. Stdlib ``unittest`` only.
"""

import unittest

from solution import parse_csv_line


class TestParseCsvLine(unittest.TestCase):
    def test_plain_fields(self):
        self.assertEqual(parse_csv_line("a,b,c"), ["a", "b", "c"])

    def test_quoted_field_with_comma(self):
        self.assertEqual(parse_csv_line('"a,b",c'), ["a,b", "c"])

    def test_doubled_quote_escape(self):
        self.assertEqual(parse_csv_line('a,"b""c",d'), ["a", 'b"c', "d"])

    def test_empty_line_single_empty_field(self):
        self.assertEqual(parse_csv_line(""), [""])

    def test_trailing_comma_empty_field(self):
        self.assertEqual(parse_csv_line("a,"), ["a", ""])

    def test_single_field(self):
        self.assertEqual(parse_csv_line("hello"), ["hello"])


if __name__ == "__main__":
    unittest.main()
