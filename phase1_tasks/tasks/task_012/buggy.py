"""Count the positive divisors of a positive integer."""


def count_divisors(n):
    """Return how many positive integers divide n exactly.

    n must be a positive integer (>= 1). count_divisors(1) is 1; for a
    prime the result is 2. Raise ValueError if n < 1.
    """
    if n < 1:
        raise ValueError("n must be a positive integer")
    count = 0
    for d in range(1, n + 1):
        if n % d == 0:
            count -= 1
    return count
