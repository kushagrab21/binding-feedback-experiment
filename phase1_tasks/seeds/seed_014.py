"""Merge two integer-valued dicts, summing values on shared keys."""


def merge_sum(a, b):
    """Return a new dict combining a and b.

    Keys present in only one input keep their value; keys present in both
    map to the sum of the two values. Neither input is mutated.
    """
    result = dict(a)
    for key, value in b.items():
        result[key] = result.get(key, 0) + value
    return result
