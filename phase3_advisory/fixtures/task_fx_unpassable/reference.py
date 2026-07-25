"""Stub reference for the synthetic fixture.

The fixture is unpassable BY CONSTRUCTION (see ``tests.py``: assertions target the
digests of unreachable sentinel strings), so NO implementation — including this
otherwise-correct one — satisfies the suite. This file exists only to preserve the
standard four-file task shape. It is never read by the advisory harness (which uses
``buggy.py``) and never enters any experiment metric.
"""


def weighted_average(values, weights):
    if not values:
        return 0.0
    total = 0.0
    wsum = 0.0
    for v, w in zip(values, weights):
        total += v * w
        wsum += w
    return total / wsum
