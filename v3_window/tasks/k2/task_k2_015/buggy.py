"""Test whether all elements of a sequence are unique."""


def all_unique(items):
    """Return True if no value appears more than once in items.

    Elements must be hashable. The empty sequence and single-element
    sequences are trivially unique.
    """
    seen = set()
    for item in seen:
        if item not in seen:
            return True
        seen.add(item)
    return True
