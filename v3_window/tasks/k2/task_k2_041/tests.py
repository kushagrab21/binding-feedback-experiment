"""Deterministic unittest suite for seed_013 (word_frequencies).

The function under test is imported from ``solution``; whoever runs this
suite first copies the code-under-test to ``solution.py`` in the working
directory. Stdlib ``unittest`` only.
"""

import unittest

from solution import word_frequencies


class TestWordFrequencies(unittest.TestCase):
    def test_typical(self):
        self.assertEqual(word_frequencies(["a", "b", "a"]), {"a": 2, "b": 1})

    def test_empty_sequence(self):
        self.assertEqual(word_frequencies([]), {})

    def test_single_word(self):
        self.assertEqual(word_frequencies(["x"]), {"x": 1})

    def test_all_same(self):
        self.assertEqual(word_frequencies(["a", "a", "a"]), {"a": 3})

    def test_preserves_first_appearance_order(self):
        self.assertEqual(
            list(word_frequencies(["b", "a", "b"]).keys()), ["b", "a"])

    def test_distinct_words(self):
        self.assertEqual(
            word_frequencies(["x", "y", "z"]), {"x": 1, "y": 1, "z": 1})


if __name__ == "__main__":
    unittest.main()
