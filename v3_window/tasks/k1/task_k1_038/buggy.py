"""Find the most frequent character in a string."""


def most_common_char(s):
    """Return the character occurring most often in s.

    Ties are broken in favour of the character whose first occurrence is
    earliest. Raise ValueError if s is empty.
    """
    if not s:
        raise ValueError("string must be non-empty")
    counts = {}
    for ch in s:
        counts[ch] = counts.get(ch, 0) + 1
    best_char = s[0]
    best_count = counts[s[0]]
    for ch in s:
        if not counts[ch] > best_count:
            best_char = ch
            best_count = counts[ch]
    return best_count
