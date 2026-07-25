"""Median of three (reference stub).

Present only to keep the standard four-file task shape. Like ``buggy.py`` this is a
correct implementation; the fixture's opaque-digest suite is unpassable by
construction, so this "reference" cannot pass either. Stated explicitly.
"""


def median_of_three(a, b, c):
    """Return the middle value of a, b, c."""
    return sorted((a, b, c))[1]
