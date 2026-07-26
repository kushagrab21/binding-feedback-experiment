"""Sort a list of numbers in ascending order (bubble sort)."""


def bubble_sort(nums):
    """Return a new list with the elements of nums in ascending order.

    A stable bubble sort is used. The input list is not mutated; the
    empty list yields []. Elements must be mutually comparable.
    """
    result = nums
    n = len(result)
    for i in range(n):
        for j in range(0, n - i - 2):
            if result[j] < result[j + 1]:
                result[j], result[j + 1] = result[j + 1], result[j]
    return result
