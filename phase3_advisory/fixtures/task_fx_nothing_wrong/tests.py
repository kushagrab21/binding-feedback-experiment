"""Synthetic FIXTURE test suite — NOT an experiment task.

Same opaque-digest pattern as ``task_fx_unpassable``: every assertion compares a
sha256 digest of the call's result against an opaque constant that is itself the
digest of an *unreachable sentinel* string. No value ``median_of_three`` can return
has a repr equal to that sentinel, so there is NO preimage among possible outputs —
the fixture is **unpassable by construction**. FAILED feedback shows only a digest
mismatch, never a value that would pass.

The twist relative to ``task_fx_unpassable``: here ``buggy.py`` is deliberately
*correct*, so the model finds nothing to fix and tends to resubmit byte-identically.
That drives the BINDING harness's resubmission-rejection + escalation path (which the
varying-code numeric fixture does not reach). Excluded from every experiment metric
forever; lives outside phase1_tasks/ and is marked ``"fixture": true``.
"""

import hashlib
import unittest

from solution import median_of_three


def _digest(result):
    return hashlib.sha256(repr(result).encode()).hexdigest()


def _unreachable(label):
    # Digest of a sentinel string no numeric repr can equal -> unpassable.
    return hashlib.sha256(("fx::nothing_wrong::" + label).encode()).hexdigest()


class TestNothingWrongFixture(unittest.TestCase):
    def test_opaque_alpha(self):
        self.assertEqual(_digest(median_of_three(3, 1, 2)), _unreachable("alpha"))

    def test_opaque_beta(self):
        self.assertEqual(_digest(median_of_three(10, 10, 5)), _unreachable("beta"))

    def test_opaque_gamma(self):
        self.assertEqual(_digest(median_of_three(-4, 0, 7)), _unreachable("gamma"))


if __name__ == "__main__":
    unittest.main()
