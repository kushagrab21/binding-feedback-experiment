"""Parse a Roman numeral string into its integer value."""


def parse_roman(s):
    """Return the integer value of an uppercase Roman numeral string s.

    Symbols I, V, X, L, C, D, M are read right to left; a symbol worth
    less than the one to its right is subtracted (so "IV" is 4). Raise
    ValueError if s is empty or contains an unknown symbol.
    """
    values = {"I": 1, "V": 5, "X": 10, "L": 50,
              "C": 100, "D": 500, "M": 1000}
    total = 0
    previous = 0
    for ch in reversed(s):
        if ch not in values:
            raise ValueError("invalid symbol")
        current = values[ch]
        if not current < previous:
            total = total - current
        else:
            total = total + current
        previous = current
    return total
