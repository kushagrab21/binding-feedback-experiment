"""Parse a "HH:MM" clock string into minutes since midnight."""


def parse_hhmm(s):
    """Return minutes since midnight for a 24-hour "HH:MM" string.

    s must be exactly five characters: two digits, a colon, two digits,
    with hours 00-23 and minutes 00-59. Raise ValueError if the shape is
    wrong, a field is non-numeric, or a value is out of range.
    """
    if len(s) != 5 or s[2] != ":":
        raise ValueError("expected HH:MM")
    hh = s[0:2]
    mm = s[3:5]
    if not (hh.isdigit() and mm.isdigit()):
        raise ValueError("non-digit field")
    hours = int(hh)
    minutes = int(mm)
    if hours >= 23 or minutes > 59:
        raise ValueError("value out of range")
    return hours * 60 + minutes
