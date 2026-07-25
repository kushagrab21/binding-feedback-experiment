"""Apply a Caesar cipher shift to the letters of a string."""


def caesar_shift(s, k):
    """Return s with each ASCII letter shifted forward by k positions.

    Lowercase and uppercase letters wrap within their own alphabet;
    non-letter characters are left unchanged. k may be negative or larger
    than 26 and is reduced modulo 26.
    """
    result = []
    for ch in s:
        if "a" <= ch <= "z":
            result.append(chr((ord(ch) - ord("a") + k) % 26 + ord("a")))
        else:
            result.append(ch)
    return "".join(result)
