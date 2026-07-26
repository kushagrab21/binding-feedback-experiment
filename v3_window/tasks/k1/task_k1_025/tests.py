"""Deterministic unittest suite for seed_025 (parse_version).

The function under test is imported from ``solution``; whoever runs this
suite first copies the code-under-test to ``solution.py`` in the working
directory. Stdlib ``unittest`` only.
"""

import unittest

from solution import parse_version


class TestParseVersion(unittest.TestCase):
    def test_three_components(self):
        self.assertEqual(parse_version("1.2.3"), (1, 2, 3))

    def test_two_components(self):
        self.assertEqual(parse_version("10.0"), (10, 0))

    def test_single_component(self):
        self.assertEqual(parse_version("1"), (1,))

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            parse_version("")

    def test_empty_component_raises(self):
        with self.assertRaises(ValueError):
            parse_version("1..2")

    def test_non_numeric_component_raises(self):
        with self.assertRaises(ValueError):
            parse_version("1.a")


if __name__ == "__main__":
    unittest.main()
