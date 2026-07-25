"""Deterministic, rule-based dev/test split of the 97 tasks (10 dev, 87 test).

No randomness. The dev set is a small, hand-designed-but-mechanically-selected
holdout used while building the harness (phases 2+); the 87 test tasks are the
held-out evaluation corpus. The selection is a fixed procedure so the split is
exactly reproducible from the task metadata.

Constraints the dev set must satisfy (all asserted at the end):
  (a) no input-mutation task in dev  — all 3 input-mutation tasks stay in test;
  (b) dev covers each of the 7 remaining bug types at least once;
  (c) dev has >= 2 easy, >= 2 medium, >= 2 hard;
  (d) dev uses 10 distinct seeds.

Selection procedure (deterministic; see RULE below for the prose version):

  Pool = the eligible tasks = every task whose bug_type != "input-mutation".

  Pass 1 — bug-type coverage with a fixed difficulty cycle (7 picks).
    Iterate the 7 eligible bug types in alphabetical order. Slot i is given a
    target difficulty from the cycle [hard, medium, easy] (i.e. slot 0->hard,
    1->medium, 2->easy, 3->hard, ...). For that bug type, pick the
    lexicographically-first task (by task_id) that has the target difficulty and
    whose seed is not already used; if the bug type has no such task, fall back
    to the lexicographically-first task of that bug type whose seed is unused
    (any difficulty). Slots 0-5 hit targets hard,medium,easy,hard,medium,easy,
    which already guarantees >= 2 of each difficulty independently of the data.

  Pass 2 — fill to 10 with distinct seeds (3 picks).
    Repeatedly add the lexicographically-first eligible task (by task_id) whose
    seed is not yet used, until dev holds 10 tasks. Difficulty is already
    balanced by Pass 1, so Pass 2 only needs to preserve seed-distinctness.

  test = the other 87 tasks.

    python3 phase1_tasks/generator/split_dev_test.py

Infrastructure only: this partitions task ids; it never inspects or solves task
contents beyond their metadata.
"""

import json
import sys
from collections import Counter
from pathlib import Path

GEN_DIR = Path(__file__).resolve().parent
PHASE1_DIR = GEN_DIR.parent
TASKS_DIR = PHASE1_DIR / "tasks"
SPLIT_PATH = PHASE1_DIR / "validation" / "split.json"

EXCLUDED_BUG_TYPE = "input-mutation"
DIFFICULTY_CYCLE = ["hard", "medium", "easy"]
DEV_SIZE = 10

RULE = (
    "Deterministic, no randomness. Pool = tasks with bug_type != "
    "'input-mutation'. Pass 1 (bug-type coverage): iterate the 7 eligible bug "
    "types alphabetically; slot i targets difficulty cycle[i % 3] where cycle = "
    "[hard, medium, easy]; pick the lexicographically-first task (by task_id) of "
    "that bug type with the target difficulty and an unused seed, else the "
    "lexicographically-first task of that bug type with an unused seed. Pass 2 "
    "(fill to 10): repeatedly add the lexicographically-first eligible task by "
    "task_id whose seed is not yet used until dev has 10 tasks. The other 87 "
    "tasks are test. Slots 0-5 of Pass 1 hit hard,medium,easy,hard,medium,easy, "
    "guaranteeing >= 2 of each difficulty; all 7 eligible bug types are covered "
    "by construction; seeds are kept distinct throughout."
)


def die(message):
    print(f"split_dev_test: ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def load_tasks():
    tasks = {}
    for meta_path in sorted(TASKS_DIR.glob("task_*/meta.json")):
        m = json.loads(meta_path.read_text())
        tasks[m["task_id"]] = {
            "task_id": m["task_id"],
            "seed": m["seed_name"],
            "bug_type": m["bug_type"],
            "difficulty": m["difficulty"],
        }
    return tasks


def main():
    tasks = load_tasks()
    if len(tasks) != 97:
        die(f"expected 97 tasks, found {len(tasks)}")
    if any(t["difficulty"] is None for t in tasks.values()):
        die("some tasks have difficulty=null; run tag_difficulty.py + "
            "generate_tasks.py first")

    eligible = sorted(
        (t for t in tasks.values() if t["bug_type"] != EXCLUDED_BUG_TYPE),
        key=lambda t: t["task_id"],
    )
    bug_types = sorted({t["bug_type"] for t in eligible})

    dev_ids = []
    used_seeds = set()

    def take(task):
        dev_ids.append(task["task_id"])
        used_seeds.add(task["seed"])

    # Pass 1 — one task per bug type, following the difficulty cycle.
    for i, bug_type in enumerate(bug_types):
        target = DIFFICULTY_CYCLE[i % len(DIFFICULTY_CYCLE)]
        of_type = [t for t in eligible if t["bug_type"] == bug_type
                   and t["seed"] not in used_seeds]
        preferred = [t for t in of_type if t["difficulty"] == target]
        pick = preferred[0] if preferred else (of_type[0] if of_type else None)
        if pick is None:
            die(f"pass 1: no unused-seed task available for bug type {bug_type}")
        take(pick)

    # Pass 2 — fill to DEV_SIZE with distinct seeds.
    for t in eligible:
        if len(dev_ids) >= DEV_SIZE:
            break
        if t["task_id"] in dev_ids or t["seed"] in used_seeds:
            continue
        take(t)

    if len(dev_ids) != DEV_SIZE:
        die(f"could not select {DEV_SIZE} dev tasks (got {len(dev_ids)})")

    dev_ids = sorted(dev_ids)
    test_ids = sorted(tid for tid in tasks if tid not in set(dev_ids))

    # --- assertions -------------------------------------------------------
    dev_set, test_set = set(dev_ids), set(test_ids)
    assert len(dev_ids) == 10, f"|dev|={len(dev_ids)}"
    assert len(test_ids) == 87, f"|test|={len(test_ids)}"
    assert dev_set.isdisjoint(test_set), "dev/test overlap"
    assert dev_set | test_set == set(tasks), "union != all 97"
    devmeta = [tasks[tid] for tid in dev_ids]
    assert all(t["bug_type"] != EXCLUDED_BUG_TYPE for t in devmeta), \
        "input-mutation leaked into dev"
    covered = {t["bug_type"] for t in devmeta}
    assert covered == set(bug_types), \
        f"dev misses bug types {set(bug_types) - covered}"
    diff_counts = Counter(t["difficulty"] for t in devmeta)
    for d in ("easy", "medium", "hard"):
        assert diff_counts[d] >= 2, f"dev has < 2 {d} ({diff_counts[d]})"
    assert len({t["seed"] for t in devmeta}) == 10, "dev seeds not distinct"

    SPLIT_PATH.write_text(json.dumps(
        {"dev": dev_ids, "test": test_ids, "rule": RULE}, indent=2) + "\n")

    # --- report -----------------------------------------------------------
    print(f"wrote split -> {SPLIT_PATH}")
    print(f"dev={len(dev_ids)}  test={len(test_ids)}  (disjoint, union=97)")
    print("dev tasks:")
    print(f"    {'task_id':<9} {'seed':<9} {'bug_type':<20} difficulty")
    for t in devmeta:
        print(f"    {t['task_id']:<9} {t['seed']:<9} "
              f"{t['bug_type']:<20} {t['difficulty']}")
    print(f"dev bug types ({len(covered)}): {sorted(covered)}")
    print(f"dev difficulties: easy={diff_counts['easy']} "
          f"medium={diff_counts['medium']} hard={diff_counts['hard']}")
    print(f"dev distinct seeds: {len({t['seed'] for t in devmeta})}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
