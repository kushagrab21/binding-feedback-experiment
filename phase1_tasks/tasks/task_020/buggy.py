"""Count vowels in a string, case-insensitively."""


def count_vowels(s):
    """Return the number of vowel characters in s.

    Vowels are a, e, i, o, u in either case; 'y' is not counted.
    Non-letter characters are ignored. The empty string yields 0.
    """
    vowels = "aeiou"
    count = 0
    for ch in s.lower():
        if ch not in vowels:
            count += 1
    return count
