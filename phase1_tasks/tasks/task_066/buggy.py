"""Determine whether a year is a Gregorian leap year."""


def is_leap_year(year):
    """Return True if year is a leap year in the Gregorian calendar.

    A year is a leap year if it is divisible by 4, except century years,
    which must also be divisible by 400. So 2000 is a leap year but 1900
    is not.
    """
    if year % 400 == 0:
        return True
    if year % 100 == 0:
        return False
    return year // 4 == 0
