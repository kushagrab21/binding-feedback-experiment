"""Reverse the order of whitespace-separated words in a string."""


def reverse_words(s):
    """Return s with its words in reverse order.

    Words are maximal runs of non-whitespace; runs of whitespace are
    treated as a single separator and the result is joined with single
    spaces. Leading/trailing whitespace is dropped. "" yields "".
    """
    words = s.split(" ")
    reversed_words = []
    for index in range(len(words) - 1, -1, -1):
        reversed_words.append(words[index])
    return " ".join(words)
