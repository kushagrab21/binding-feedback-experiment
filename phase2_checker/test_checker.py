"""The judge's own test suite (stdlib ``unittest`` only).

Everything in Phases 3–5 trusts ``checker.run_checks``; this suite is what earns
that trust. It exercises ``run_checks`` using ONLY the ten Phase-2 dev tasks
(here: ``task_003`` and ``task_006``) — never any held-out task.

Covers: reference accepted; buggy rejected with the frozen first-failing test;
syntax error / wrong function name / empty submission collapse to a graceful
``__collection__`` verdict; an infinite loop is caught by timeout in bounded time;
the verdict is deterministic; and the reported first failing test agrees with
``phase1_tasks/validation/task_validation.txt``.
"""

import json
import os
import re
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from checker import run_checks  # noqa: E402

TASKS_DIR = os.path.join(REPO, "phase1_tasks", "tasks")
VALIDATION_TXT = os.path.join(
    REPO, "phase1_tasks", "validation", "task_validation.txt")

# The two dev tasks used throughout. Both are on the Phase-2 dev whitelist.
DEV_A = "task_006"   # seed_002 digit_sum, off-by-one, buggy fails 5/6
DEV_B = "task_003"   # seed_001 clamp,     wrong-comparison, buggy fails 1/7


def task_path(task_id):
    return os.path.join(TASKS_DIR, task_id)


def read_task_file(task_id, name):
    with open(os.path.join(task_path(task_id), name)) as fh:
        return fh.read()


def frozen_first_failing(task_id):
    """Return the ``[test_name]`` recorded for ``task_id`` in the frozen table.

    Reads only the single row for ``task_id`` (a validation summary, not any
    task's source files).
    """
    row_re = re.compile(
        r"^" + re.escape(task_id) + r"\b.*\[([^\]]+)\]\s*$")
    with open(VALIDATION_TXT) as fh:
        for line in fh:
            m = row_re.match(line)
            if m:
                return m.group(1)
    raise AssertionError(f"no row for {task_id} in {VALIDATION_TXT}")


def normalise_verdict(verdict):
    """Canonical JSON string of a verdict, with volatile substrings removed.

    Two things vary run-to-run inside ``raw_output`` (which is preserved verbatim
    by design): the random temp-dir path and unittest's timing line. Both are
    scrubbed here so a determinism check can compare byte-for-byte. The contract
    fields (``passed``/``failures``) are already deterministic; this only has to
    neutralise the advisory ``raw_output``.
    """
    d = dict(verdict)
    raw = d.get("raw_output", "")
    raw = re.sub(r"/[^\s\"']*checker_[^\s\"']*", "<sandbox>", raw)
    raw = re.sub(r"Ran (\d+) tests? in [0-9.]+s", r"Ran \1 tests in <t>s", raw)
    d["raw_output"] = raw
    return json.dumps(d, sort_keys=True)


class TestReferenceAccepted(unittest.TestCase):
    """(a) reference code of two different dev tasks -> passed, no failures."""

    def test_reference_task_006_passes(self):
        v = run_checks(task_path(DEV_A), read_task_file(DEV_A, "reference.py"))
        self.assertTrue(v["passed"])
        self.assertEqual(v["failures"], [])

    def test_reference_task_003_passes(self):
        v = run_checks(task_path(DEV_B), read_task_file(DEV_B, "reference.py"))
        self.assertTrue(v["passed"])
        self.assertEqual(v["failures"], [])


class TestBuggyRejected(unittest.TestCase):
    """(b) buggy code of the same two -> rejected, first-failing matches table."""

    def test_buggy_task_006_fails(self):
        v = run_checks(task_path(DEV_A), read_task_file(DEV_A, "buggy.py"))
        self.assertFalse(v["passed"])
        self.assertTrue(v["failures"])
        self.assertEqual(v["failures"][0]["test"], "test_large_value")

    def test_buggy_task_003_fails(self):
        v = run_checks(task_path(DEV_B), read_task_file(DEV_B, "buggy.py"))
        self.assertFalse(v["passed"])
        self.assertTrue(v["failures"])
        self.assertEqual(
            v["failures"][0]["test"], "test_degenerate_single_point_range")


class TestMalformedSubmissions(unittest.TestCase):
    """(c)/(d)/(e) syntax error, wrong name, and empty all collapse gracefully."""

    def test_syntax_error_is_collection_failure(self):
        v = run_checks(task_path(DEV_A), "def digit_sum(n)  return n")
        self.assertFalse(v["passed"])
        self.assertEqual(v["failures"][0]["test"], "__collection__")
        self.assertIn("SyntaxError", v["failures"][0]["error"])

    def test_wrong_function_name_handled(self):
        v = run_checks(task_path(DEV_A), "def not_digit_sum(n):\n    return 0\n")
        self.assertFalse(v["passed"])
        self.assertEqual(v["failures"][0]["test"], "__collection__")
        self.assertIn("cannot import name", v["failures"][0]["error"])

    def test_empty_submission_handled(self):
        v = run_checks(task_path(DEV_A), "")
        self.assertFalse(v["passed"])
        self.assertTrue(v["failures"])
        self.assertEqual(v["failures"][0]["test"], "__collection__")


class TestTimeout(unittest.TestCase):
    """(f) an infinite loop is rejected via timeout, in bounded time."""

    def test_infinite_loop_times_out(self):
        code = "def digit_sum(n):\n    while True:\n        pass\n"
        start = time.monotonic()
        v = run_checks(task_path(DEV_A), code, timeout=2.0)
        elapsed = time.monotonic() - start
        self.assertFalse(v["passed"])
        self.assertTrue(v.get("timed_out"))
        self.assertEqual(v["failures"][0]["test"], "__timeout__")
        # Bounded: the 2s ceiling plus subprocess teardown, comfortably < 9s.
        self.assertLess(elapsed, 9.0)


class TestDeterminism(unittest.TestCase):
    """(g) the same buggy submission yields a byte-identical (normalised) verdict."""

    def test_buggy_verdict_is_reproducible(self):
        code = read_task_file(DEV_A, "buggy.py")
        v1 = run_checks(task_path(DEV_A), code)
        v2 = run_checks(task_path(DEV_A), code)
        # Contract fields are deterministic outright.
        self.assertEqual(v1["passed"], v2["passed"])
        self.assertEqual(v1["failures"], v2["failures"])
        # Whole verdict is byte-identical once volatile raw_output text is normalised.
        self.assertEqual(normalise_verdict(v1), normalise_verdict(v2))


class TestAgreesWithFrozenTable(unittest.TestCase):
    """(h) first failing test agrees with task_validation.txt for a buggy dev task."""

    def test_first_failing_matches_validation_table(self):
        for task_id in (DEV_A, DEV_B):
            with self.subTest(task=task_id):
                v = run_checks(
                    task_path(task_id), read_task_file(task_id, "buggy.py"))
                self.assertFalse(v["passed"])
                self.assertEqual(
                    v["failures"][0]["test"], frozen_first_failing(task_id))


if __name__ == "__main__":
    unittest.main()
