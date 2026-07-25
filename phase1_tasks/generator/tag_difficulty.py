"""Assign a difficulty label to every task from the validator report.

Reads the per-task rows of ``phase1_tasks/validation/task_validation.txt``
(each row is ``task_NNN seed_XXX bug-type ref=PASS buggy=FAIL(n_failed/n_total)
[test]``) and assigns a difficulty using these exact fixed rules:

    hard    if n_failed == 1
    easy    if n_failed / n_total >= 0.5
    medium  otherwise

The intuition: a bug caught by exactly one test is the hardest to notice (only
one input distinguishes buggy from correct); a bug that breaks at least half the
suite is the easiest (many inputs expose it); everything between is medium.

Writes ``phase1_tasks/generator/difficulty.json`` mapping
``task_id -> {seed_id, bug_type, n_failed, n_total, difficulty}`` and prints the
difficulty distribution overall and per bug type.

    python3 phase1_tasks/generator/tag_difficulty.py

Infrastructure only: this labels tasks from validator output; it never solves a
task or edits task content (difficulty is stamped into meta.json by the
generator, which reads the JSON this writes).
"""

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

GEN_DIR = Path(__file__).resolve().parent
PHASE1_DIR = GEN_DIR.parent
REPORT_PATH = PHASE1_DIR / "validation" / "task_validation.txt"
DIFFICULTY_PATH = GEN_DIR / "difficulty.json"

# task_001 seed_001 inverted-condition ref=PASS buggy=FAIL(4/7) [test_...]
ROW_RE = re.compile(
    r"^(?P<task_id>task_\d+)\s+"
    r"(?P<seed_id>seed_\d+)\s+"
    r"(?P<bug_type>\S+)\s+"
    r"ref=PASS\s+"
    r"buggy=FAIL\((?P<n_failed>\d+)/(?P<n_total>\d+)\)"
)


def die(message):
    print(f"tag_difficulty: ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def classify(n_failed, n_total):
    """Apply the fixed difficulty rules (order matters: hard is checked first)."""
    if n_failed == 1:
        return "hard"
    if n_failed / n_total >= 0.5:
        return "easy"
    return "medium"


def main():
    if not REPORT_PATH.exists():
        die(f"validation report not found: {REPORT_PATH}")

    difficulty = {}
    for line in REPORT_PATH.read_text().splitlines():
        m = ROW_RE.match(line)
        if m is None:
            continue  # totals / separators / non-task rows
        task_id = m.group("task_id")
        n_failed = int(m.group("n_failed"))
        n_total = int(m.group("n_total"))
        difficulty[task_id] = {
            "seed_id": m.group("seed_id"),
            "bug_type": m.group("bug_type"),
            "n_failed": n_failed,
            "n_total": n_total,
            "difficulty": classify(n_failed, n_total),
        }

    if not difficulty:
        die(f"no per-task rows parsed from {REPORT_PATH}")

    # Deterministic key order (task_001, task_002, ...).
    difficulty = dict(sorted(difficulty.items()))
    DIFFICULTY_PATH.write_text(json.dumps(difficulty, indent=2) + "\n")

    overall = Counter(rec["difficulty"] for rec in difficulty.values())
    per_type = defaultdict(Counter)
    for rec in difficulty.values():
        per_type[rec["bug_type"]][rec["difficulty"]] += 1

    order = ["easy", "medium", "hard"]
    print(f"tagged {len(difficulty)} tasks -> {DIFFICULTY_PATH}")
    print("difficulty distribution (overall):")
    for d in order:
        print(f"    {d:<6} {overall[d]}")
    print("difficulty distribution (per bug type):")
    for bug_type in sorted(per_type):
        counts = per_type[bug_type]
        cells = "  ".join(f"{d}={counts[d]}" for d in order)
        total = sum(counts.values())
        print(f"    {bug_type:<20} {cells}   (n={total})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
