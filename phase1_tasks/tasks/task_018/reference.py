"""Test whether a string is a palindrome (two-pointer scan)."""


def is_palindrome(s):
    """Return True if s reads the same forwards and backwards.

    Characters are compared exactly, with no case-folding or stripping.
    The empty string and single-character strings are palindromes.
    """
    left = 0
    right = len(s) - 1
    while left < right:
        if s[left] != s[right]:
            return False
        left += 1
        right -= 1
    return True
