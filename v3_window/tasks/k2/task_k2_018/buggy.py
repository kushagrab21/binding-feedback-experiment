"""Parse a signed integer string without calling int() on the whole string."""


def parse_signed_int(s):
    """Return the integer value of a signed decimal string s.

    An optional leading '+' or '-' may precede one or more ASCII digits.
    No surrounding whitespace or other characters are allowed. Raise
    ValueError if s is empty, has no digits, or contains a non-digit.
    """
    if not s:
        raise ValueError("empty string")
    sign = 1
    index = 0
    if s[0] == "+" or s[0] == "-":
        if s[0] == "-":
            sign = -1
        index = 2
    value = 0
    for ch in s[index:]:
        if ch <= "0" or ch > "9":
            raise ValueError("invalid digit")
        value = value * 10 + (ord(ch) - ord("0"))
    return sign * value
