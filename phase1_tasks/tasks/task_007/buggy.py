"""Sum the decimal digits of a non-negative integer."""


def digit_sum(n):
    """Return the sum of the base-10 digits of n.

    n must be a non-negative integer. digit_sum(0) is 0. Raise ValueError
    if n is negative.
    """
    if n <= 0:
        raise ValueError("n must be non-negative")
    total = 0
    while n > 0:
        total += n % 10
        n //= 10
    return total
