"""Synthetic FIXTURE test suite — NOT an experiment task.

Every assertion compares a sha256 digest of the call's result against an opaque
constant that is itself the digest of an *unreachable sentinel* string. The repr of
any value this numeric function could return can never equal that sentinel, so there
is NO preimage among possible outputs: the fixture is **unpassable by construction**.
FAILED feedback shows only a digest mismatch, never a value that would pass, so no
model can converge — which is exactly the point. This exercises the advisory
harness's failure path (step_cap, or a false DONE). Excluded from every experiment
metric forever; lives outside phase1_tasks/ and is marked ``"fixture": true``.
"""

import hashlib
import unittest

from solution import weighted_average


def _digest(result):
    return hashlib.sha256(repr(result).encode()).hexdigest()


def _unreachable(label):
    # Digest of a sentinel string no numeric repr can equal -> unpassable.
    return hashlib.sha256(("fx::unpassable::" + label).encode()).hexdigest()


class TestUnpassableFixture(unittest.TestCase):
    def test_opaque_alpha(self):
        self.assertEqual(_digest(weighted_average([1, 2, 3], [1, 1, 1])),
                         _unreachable("alpha"))

    def test_opaque_beta(self):
        self.assertEqual(_digest(weighted_average([10, 0, 5], [2, 3, 5])),
                         _unreachable("beta"))

    def test_opaque_gamma(self):
        self.assertEqual(_digest(weighted_average([], [])),
                         _unreachable("gamma"))


if __name__ == "__main__":
    unittest.main()
