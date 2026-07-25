"""Deterministically generate bug-fix tasks from the mutation manifest.

Reads ``phase1_tasks/generator/mutations.json`` (hand-authored single-edit
mutations, one per (seed, bug_type) pair) and ``phase1_tasks/seeds/SEEDS.json``
(function name + description per seed). For each mutation, in a fixed order,
it emits one task directory under ``phase1_tasks/tasks/`` per TASK_FORMAT.md:

    task_NNN/
        buggy.py       # seed source with the single mutation applied
        reference.py   # seed source verbatim (correct implementation)
        tests.py       # the seed's 1.4 unittest suite verbatim
        meta.json      # task_id, seed_name, bug_type, difficulty=null,
                       # function_name, description

Ordering is deterministic: mutations are sorted by (seed_id, bug_type) and
numbered task_001, task_002, ... in that order. There is no randomness and no
timestamp. ``phase1_tasks/tasks/`` is wiped (all task_* dirs removed) and
regenerated on every run — tasks are never hand-edited.

If a mutation's ``old`` snippet does not occur in its seed source *exactly
once*, the run aborts loudly (that mutation cannot be applied unambiguously).

    python3 phase1_tasks/generator/generate_tasks.py

Infrastructure only: this wires seeds + suites + manifest into task dirs; it
never solves a task.
"""

import json
import shutil
import sys
from pathlib import Path

GEN_DIR = Path(__file__).resolve().parent
PHASE1_DIR = GEN_DIR.parent
SEEDS_DIR = PHASE1_DIR / "seeds"
TESTS_DIR = SEEDS_DIR / "tests"
TASKS_DIR = PHASE1_DIR / "tasks"

MUTATIONS_PATH = GEN_DIR / "mutations.json"
SEEDS_PATH = SEEDS_DIR / "SEEDS.json"


def die(message):
    """Abort loudly: print to stderr and exit non-zero."""
    print(f"generate_tasks: ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def apply_mutation(source, old, new, seed_id, bug_type):
    """Return source with the single ``old`` -> ``new`` edit applied.

    ``old`` MUST occur exactly once in source, else abort loudly.
    """
    occurrences = source.count(old)
    if occurrences != 1:
        die(f"{seed_id}/{bug_type}: 'old' snippet occurs {occurrences} times "
            f"in {seed_id}.py (must be exactly 1). Snippet:\n{old!r}")
    return source.replace(old, new)


def wipe_tasks_dir():
    """Remove every generated task_* directory, preserving .gitkeep."""
    if not TASKS_DIR.exists():
        die(f"tasks directory {TASKS_DIR} does not exist")
    for child in TASKS_DIR.iterdir():
        if child.is_dir() and child.name.startswith("task_"):
            shutil.rmtree(child)
        elif child.name == ".gitkeep":
            continue
        elif child.is_dir():
            shutil.rmtree(child)
        # leave any other stray top-level files (e.g. .gitkeep) in place


def main():
    manifest = json.loads(MUTATIONS_PATH.read_text())
    mutations = manifest["mutations"]

    seeds = {entry["seed_id"]: entry
             for entry in json.loads(SEEDS_PATH.read_text())}

    # Deterministic ordering: sort by (seed_id, bug_type).
    mutations = sorted(mutations, key=lambda m: (m["seed_id"], m["bug_type"]))

    wipe_tasks_dir()

    for i, mut in enumerate(mutations, start=1):
        seed_id = mut["seed_id"]
        bug_type = mut["bug_type"]

        seed = seeds.get(seed_id)
        if seed is None:
            die(f"mutation references unknown seed_id {seed_id}")

        function_name = seed["function_name"]
        description = seed["description"]

        seed_src_path = SEEDS_DIR / f"{seed_id}.py"
        suite_src_path = TESTS_DIR / f"test_{seed_id}.py"
        if not seed_src_path.exists():
            die(f"missing seed source {seed_src_path}")
        if not suite_src_path.exists():
            die(f"missing suite {suite_src_path}")

        reference_src = seed_src_path.read_text()
        tests_src = suite_src_path.read_text()
        buggy_src = apply_mutation(
            reference_src, mut["old"], mut["new"], seed_id, bug_type)

        if buggy_src == reference_src:
            die(f"{seed_id}/{bug_type}: mutation produced no change "
                f"(old == new?)")

        task_id = f"task_{i:03d}"
        task_dir = TASKS_DIR / task_id
        task_dir.mkdir(parents=True)

        (task_dir / "reference.py").write_text(reference_src)
        (task_dir / "buggy.py").write_text(buggy_src)
        (task_dir / "tests.py").write_text(tests_src)

        meta = {
            "task_id": task_id,
            "seed_name": seed_id,
            "bug_type": bug_type,
            "difficulty": None,
            "function_name": function_name,
            "description": description,
        }
        (task_dir / "meta.json").write_text(
            json.dumps(meta, indent=2) + "\n")

    print(f"generate_tasks: wrote {len(mutations)} tasks to {TASKS_DIR}")
    dropped = manifest.get("dropped_pairs", [])
    if dropped:
        print(f"generate_tasks: {len(dropped)} (seed, bug_type) pairs "
              f"dropped as un-injectable (see mutations.json dropped_pairs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
