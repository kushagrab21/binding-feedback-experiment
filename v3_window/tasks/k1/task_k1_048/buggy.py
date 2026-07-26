"""Parse a dotted version string into a tuple of integers."""


def parse_version(s):
    """Return a tuple of ints for a dotted version string like "1.2.3".

    The string is one or more '.'-separated components, each a non-empty
    run of digits; "1" yields (1,). Raise ValueError if s is empty, a
    component is empty, or a component is not purely numeric.
    """
    if not s:
        raise ValueError("empty string")
    parts = s.split(".")
    result = []
    for part in parts:
        if part == "":
            raise ValueError("empty component")
        if part.isdigit():
            raise ValueError("non-numeric component")
        result.append(int(s))
    return tuple(result)
