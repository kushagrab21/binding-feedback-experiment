"""Run every per-seed unittest suite against its seed, in isolation.

For each seed listed in ``SEEDS.json`` this script, in a fresh temporary
directory, copies the seed module to ``solution.py`` (the import contract:
the suites do ``from solution import <function_name>``) and its suite
``tests/test_seed_NNN.py`` alongside, then runs the suite in a subprocess.

Output: one line per seed ::

    seed_NNN function_name: PASS (k tests, X.XXs)

followed by a total line (overall test count and wall time). Exit status
is non-zero if any suite fails OR any single suite exceeds 2.00s (the
per-task time budget from TASK_FORMAT.md).

    python3 phase1_tasks/seeds/run_seed_tests.py

Infrastructure only: this runs the suites against the *unmodified* seeds
(the known-good reference implementations); it never solves or mutates them.
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SEED_DIR = Path(__file__).resolve().parent
TESTS_DIR = SEED_DIR / "tests"
MANIFEST = SEED_DIR / "SEEDS.json"

TIME_BUDGET_S = 2.00  # per-suite ceiling (TASK_FORMAT.md: suite < 2 seconds)

_RAN = re.compile(r"^Ran (\d+) tests? in", re.MULTILINE)


def run_one(seed_id, function_name):
    """Run one seed's suite in isolation.

    Returns (ok, n_tests, elapsed_s, raw_output). ``ok`` is True iff the
    suite passed AND stayed within the time budget.
    """
    seed_src = SEED_DIR / f"{seed_id}.py"
    test_src = TESTS_DIR / f"test_{seed_id}.py"
    if not seed_src.exists():
        return False, 0, 0.0, f"missing seed module {seed_src}"
    if not test_src.exists():
        return False, 0, 0.0, f"missing suite {test_src}"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        shutil.copyfile(seed_src, tmp_path / "solution.py")
        shutil.copyfile(test_src, tmp_path / f"test_{seed_id}.py")

        start = time.perf_counter()
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", f"test_{seed_id}", "-v"],
            cwd=tmp_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        elapsed = time.perf_counter() - start

    output = proc.stdout
    match = _RAN.search(output)
    n_tests = int(match.group(1)) if match else 0
    ok = proc.returncode == 0 and elapsed <= TIME_BUDGET_S
    return ok, n_tests, elapsed, output


def main():
    manifest = json.loads(MANIFEST.read_text())

    failures = 0
    total_tests = 0
    overall_start = time.perf_counter()

    for entry in manifest:
        seed_id = entry["seed_id"]
        function_name = entry["function_name"]
        ok, n_tests, elapsed, output = run_one(seed_id, function_name)
        total_tests += n_tests

        if ok:
            print(f"{seed_id} {function_name}: "
                  f"PASS ({n_tests} tests, {elapsed:.2f}s)")
        else:
            failures += 1
            reason = "FAIL"
            if elapsed > TIME_BUDGET_S:
                reason = f"SLOW (> {TIME_BUDGET_S:.2f}s budget)"
            print(f"{seed_id} {function_name}: "
                  f"{reason} ({n_tests} tests, {elapsed:.2f}s)")
            for line in output.rstrip().splitlines():
                print(f"    {line}")

    overall = time.perf_counter() - overall_start

    print("---")
    if failures:
        print(f"SEED TESTS: FAILED ({failures} of {len(manifest)} suites, "
              f"{total_tests} tests, {overall:.2f}s wall)")
        return 1
    print(f"SEED TESTS: OK ({len(manifest)} suites, "
          f"{total_tests} tests, {overall:.2f}s wall)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
