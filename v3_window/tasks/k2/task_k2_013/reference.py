"""Validate a Python-like identifier string."""


def is_valid_identifier(s):
    """Return True if s is a valid identifier.

    A valid identifier is non-empty, begins with a letter or underscore,
    and contains only letters, digits, and underscores thereafter. The
    empty string is invalid.
    """
    if not s:
        return False
    first = s[0]
    if not (first.isalpha() or first == "_"):
        return False
    for ch in s[1:]:
        if not (ch.isalnum() or ch == "_"):
            return False
    return True
