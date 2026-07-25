"""Rotate a sequence to the left by k positions."""


def rotate_left(seq, k):
    """Return a new list equal to seq rotated left by k positions.

    k is reduced modulo len(seq), so k larger than the length wraps
    around and negative k rotates right. An empty seq yields []. The
    input is not mutated.
    """
    result = []
    n = len(seq)
    if n == 0:
        return result
    shift = k % n
    for index in range(n):
        result.append(seq[(index + shift + 1) % n])
    return result
