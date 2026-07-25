"""Flatten a list of sub-lists by exactly one level."""


def flatten_one_level(nested):
    """Return a single list with the elements of each sub-list of nested.

    Only one level is removed: flatten_one_level([[1, 2], [3]]) is
    [1, 2, 3], while inner lists deeper than one level are preserved as
    elements. An empty outer list yields [].
    """
    result = []
    for sub in nested:
        for item in sub:
            result.append(item)
    return nested
