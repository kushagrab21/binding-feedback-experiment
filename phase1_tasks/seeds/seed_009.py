"""Find the second largest distinct value in a sequence."""


def second_largest(nums):
    """Return the second largest distinct value in nums.

    Duplicates are collapsed before ranking, so second_largest([5, 5, 3])
    is 3. Raise ValueError if fewer than two distinct values exist.
    """
    distinct = sorted(set(nums))
    if len(distinct) < 2:
        raise ValueError("need at least two distinct values")
    return distinct[-2]
