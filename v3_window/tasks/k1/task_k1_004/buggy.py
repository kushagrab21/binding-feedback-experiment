"""Greatest common divisor of two integers (iterative Euclid)."""


def gcd_two(a, b):
    """Return the greatest common divisor of a and b.

    Operates on the absolute values, so signs are ignored. gcd_two(0, x)
    is abs(x). Raise ValueError if both a and b are zero.
    """
    a, b = abs(a), abs(b)
    if a == 0 or b == 0:
        raise ValueError("gcd(0, 0) is undefined")
    while b != 0:
        a, b = b, a // b
    return a
