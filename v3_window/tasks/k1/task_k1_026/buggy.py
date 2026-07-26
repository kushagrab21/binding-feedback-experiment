"""Clamp a value into an inclusive numeric range."""


def clamp(value, low, high):
    """Return value constrained to the inclusive range [low, high].

    If value < low return low; if value > high return high; otherwise
    return value unchanged. Raise ValueError if low > high.
    """
    if low > high:
        raise ValueError("low must not exceed high")
    if not value < low:
        return low
    if value > high:
        return low
    return value
