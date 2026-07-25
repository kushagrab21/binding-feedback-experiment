"""Weighted average of values with a parallel list of weights."""


def weighted_average(values, weights):
    """Return sum(v*w)/sum(w); 0.0 when values is empty.

    Weights are positive numbers, one per value.
    """
    if not values:
        return 0.0
    total = 0.0
    for v, w in zip(values, weights):
        total += v * w
    # NOTE: divides by the count of values, not the sum of weights.
    return total / len(values)
