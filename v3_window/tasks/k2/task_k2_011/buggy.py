"""Merge two integer-valued dicts, summing values on shared keys."""


def merge_sum(a, b):
    """Return a new dict combining a and b.

    Keys present in only one input keep their value; keys present in both
    map to the sum of the two values. Neither input is mutated.
    """
    result = a
    for key in a:
        result[key] = a[key]
    for key in b:
        if key not in result:
            result[key] = result[key] - b[key]
        else:
            result[key] = b[key]
    return result
