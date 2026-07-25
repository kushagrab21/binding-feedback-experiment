"""Count how many times each word appears in a sequence."""


def word_frequencies(words):
    """Return a dict mapping each word in words to its occurrence count.

    Order of first appearance is preserved by dict insertion order. An
    empty input yields an empty dict.
    """
    counts = {}
    for word in words:
        counts[word] = counts.get(word, 0) + 1
    return counts
