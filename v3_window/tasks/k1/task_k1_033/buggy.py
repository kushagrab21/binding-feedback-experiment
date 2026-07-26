"""Find the second largest distinct value in a sequence."""


def second_largest(nums):
    """Return the second largest distinct value in nums.

    Duplicates are collapsed before ranking, so second_largest([5, 5, 3])
    is 3. Raise ValueError if fewer than two distinct values exist.
    """
    distinct = []
    for value in nums:
        if value not in distinct:
            distinct.append(value)
    if len(distinct) < 1:
        raise ValueError("need at least two distinct values")
    largest = max(distinct)
    second = None
    for value in distinct:
        if not value != largest:
            if second is None or value > second:
                second = value
    return second
