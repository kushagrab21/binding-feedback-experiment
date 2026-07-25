"""Validate every generated task against the two TASK_FORMAT.md invariants.

For each task under ``phase1_tasks/tasks/`` this script, in a fresh temporary
directory, uses the ``solution.py`` copy contract (the suites do
``from solution import <fn>``):

  (a) copy ``reference.py`` -> ``solution.py``, run ``tests.py``: it MUST pass
      the ENTIRE suite.
  (b) copy ``buggy.py`` -> ``solution.py``, run ``tests.py``: it MUST fail at
      least one test.

A task satisfying both is *accepted*; violating either is *rejected*.

Output (also written verbatim to ``phase1_tasks/validation/task_validation.txt``):
one line per task ::

    task_NNN seed_id bug_type ref=PASS buggy=FAIL(n_failed/n_total) [first_failing_test]

followed by totals (accepted / rejected, per-bug-type counts) and, for any
rejected task, its reason. Exit status is non-zero if any task violates either
invariant OR fewer than 95 tasks are accepted.

    python3 phase1_tasks/generator/validate_tasks.py

Infrastructure only: it runs suites against generated reference/buggy files; it
never solves a task.
"""

import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

GEN_DIR = Path(__file__).resolve().parent
PHASE1_DIR = GEN_DIR.parent
TASKS_DIR = PHASE1_DIR / "tasks"
VALIDATION_DIR = PHASE1_DIR / "validation"
REPORT_PATH = VALIDATION_DIR / "task_validation.txt"

MIN_ACCEPTED = 95

# Per-suite wall-clock ceiling. TASK_FORMAT.md budgets each suite at < 2s;
# a much larger cap is used here purely as a hang guard so a pathological
# mutant (e.g. one that spins in an infinite loop) is REJECTED rather than
# stalling the whole validation run.
SUITE_TIMEOUT_S = 20

_RAN = re.compile(r"^Ran (\d+) tests? in", re.MULTILINE)
# A verbose per-test result line: "name (mod.Class.name) ... ok|FAIL|ERROR".
_VLINE = re.compile(r"^(\w+) \(.*\) \.\.\. (ok|FAIL|ERROR)\b")


def run_suite(code_path, tests_path):
    """Copy code_path -> solution.py, run tests_path, return a result dict.

    Result keys: ok (bool, whole suite passed), n_total, n_failed,
    first_failing (test method name or None), timed_out (bool), raw output.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        shutil.copyfile(code_path, tmp_path / "solution.py")
        shutil.copyfile(tests_path, tmp_path / "tests.py")
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "unittest", "tests", "-v"],
                cwd=tmp_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=SUITE_TIMEOUT_S,
            )
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "n_total": 0,
                "n_failed": 0,
                "first_failing": None,
                "timed_out": True,
                "raw": f"(suite exceeded {SUITE_TIMEOUT_S}s timeout)",
            }

    output = proc.stdout
    ran = _RAN.search(output)
    n_total = int(ran.group(1)) if ran else 0

    n_failed = 0
    first_failing = None
    for line in output.splitlines():
        m = _VLINE.match(line)
        if m and m.group(2) in ("FAIL", "ERROR"):
            n_failed += 1
            if first_failing is None:
                first_failing = m.group(1)

    ok = proc.returncode == 0
    return {
        "ok": ok,
        "n_total": n_total,
        "n_failed": n_failed,
        "first_failing": first_failing,
        "timed_out": False,
        "raw": output,
    }


def read_meta(task_dir):
    """Return (seed_name, bug_type) from a task's meta.json."""
    import json
    meta = json.loads((task_dir / "meta.json").read_text())
    return meta["seed_name"], meta["bug_type"]


def main():
    task_dirs = sorted(
        d for d in TASKS_DIR.iterdir()
        if d.is_dir() and d.name.startswith("task_"))

    if not task_dirs:
        print("validate_tasks: ERROR: no tasks found (run generate_tasks.py "
              "first)", file=sys.stderr)
        return 1

    lines = []
    accepted = 0
    rejected = 0
    per_type_accepted = Counter()
    rejections = []  # (task_id, seed, bug_type, reason)

    for task_dir in task_dirs:
        task_id = task_dir.name
        seed_name, bug_type = read_meta(task_dir)
        tests_path = task_dir / "tests.py"

        ref = run_suite(task_dir / "reference.py", tests_path)
        buggy = run_suite(task_dir / "buggy.py", tests_path)

        ref_ok = ref["ok"] and not ref["timed_out"]
        # A hanging mutant is NOT a valid kill: a timeout rejects the task.
        buggy_fails = buggy["n_failed"] >= 1 and not buggy["timed_out"]

        if ref_ok and buggy_fails:
            accepted += 1
            per_type_accepted[bug_type] += 1
            lines.append(
                f"{task_id} {seed_name} {bug_type} ref=PASS "
                f"buggy=FAIL({buggy['n_failed']}/{buggy['n_total']}) "
                f"[{buggy['first_failing']}]")
        else:
            rejected += 1
            reasons = []
            if not ref_ok:
                if ref["timed_out"]:
                    reasons.append(
                        f"reference HANGS (exceeded {SUITE_TIMEOUT_S}s)")
                else:
                    reasons.append(
                        f"reference FAILS its own suite "
                        f"({ref['n_failed']}/{ref['n_total']} failed)")
            if not buggy_fails:
                if buggy["timed_out"]:
                    reasons.append(
                        f"buggy HANGS (exceeded {SUITE_TIMEOUT_S}s) "
                        f"(mutant not cleanly killable)")
                else:
                    reasons.append(
                        f"buggy PASSES all {buggy['n_total']} tests "
                        f"(mutant not killed)")
            reason = "; ".join(reasons)
            rejections.append((task_id, seed_name, bug_type, reason))
            if ref_ok:
                ref_str = "PASS"
            elif ref["timed_out"]:
                ref_str = "HANG"
            else:
                ref_str = f"FAIL({ref['n_failed']}/{ref['n_total']})"
            if buggy_fails:
                buggy_str = f"FAIL({buggy['n_failed']}/{buggy['n_total']})"
            elif buggy["timed_out"]:
                buggy_str = "HANG"
            else:
                buggy_str = f"PASS(0/{buggy['n_total']})"
            lines.append(
                f"{task_id} {seed_name} {bug_type} ref={ref_str} "
                f"buggy={buggy_str} REJECTED: {reason}")

    lines.append("---")
    lines.append(f"tasks: {len(task_dirs)}  accepted: {accepted}  "
                 f"rejected: {rejected}")
    lines.append("per-bug-type accepted counts:")
    for bug_type in sorted(per_type_accepted):
        lines.append(f"    {bug_type}: {per_type_accepted[bug_type]}")

    if rejections:
        lines.append("rejected pairs:")
        for task_id, seed_name, bug_type, reason in rejections:
            lines.append(f"    {task_id} {seed_name} {bug_type}: {reason}")

    invariants_ok = rejected == 0
    enough = accepted >= MIN_ACCEPTED

    lines.append("---")
    if invariants_ok and enough:
        lines.append(
            f"TASK VALIDATION: OK ({accepted} accepted, both invariants hold "
            f"for every task, >= {MIN_ACCEPTED} required)")
    else:
        problems = []
        if not invariants_ok:
            problems.append(f"{rejected} task(s) violate an invariant")
        if not enough:
            problems.append(
                f"only {accepted} accepted (< {MIN_ACCEPTED} required)")
        lines.append(f"TASK VALIDATION: FAILED ({'; '.join(problems)})")

    report = "\n".join(lines) + "\n"
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report)
    sys.stdout.write(report)

    return 0 if (invariants_ok and enough) else 1


if __name__ == "__main__":
    sys.exit(main())
