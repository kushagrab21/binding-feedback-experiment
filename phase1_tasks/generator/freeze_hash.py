"""Compute the Phase 1 freeze hash over git-tracked task content only.

The freeze hash is a single sha256 that pins the exact byte content of every
git-tracked file under ``phase1_tasks/tasks/``. It is computed over *tracked*
files only (``git ls-files``), so untracked noise — iCloud sync conflict copies
(``buggy 2.py``), ``__pycache__``, stray ``acceptance_*.txt`` — can never perturb
it. It is fully deterministic: same commit content -> same hash, every run.

Algorithm:
  1. paths = ``git ls-files phase1_tasks/tasks``, restricted to files that live
     inside a ``task_*/`` directory (this drops the tracked ``tasks/.gitkeep``
     scaffold, which is not task content), sorted (git already emits sorted
     paths; we sort again to be explicit and order-independent).
  2. For each path, per_file = sha256( path.encode() + b'\\0' + blob_bytes ),
     where blob_bytes is the tracked content of that path (read via
     ``git show :path`` so the hash reflects the index/commit, not any unstaged
     working-tree drift).
  3. FREEZE_HASH = sha256( concatenation of the per-file hex digests, in path
     order ).

Prints the task-dir count and total file count (must be 97 dirs x 4 files = 388)
and the final ``FREEZE_HASH`` line. Run it twice: the ``FREEZE_HASH`` line is
identical — that is the determinism guard.

    python3 phase1_tasks/generator/freeze_hash.py

Infrastructure only: this fingerprints the frozen task set; it never edits tasks.
"""

import hashlib
import subprocess
import sys
from collections import Counter
from pathlib import Path

GEN_DIR = Path(__file__).resolve().parent
PHASE1_DIR = GEN_DIR.parent
REPO_ROOT = PHASE1_DIR.parent
TASKS_REL = "phase1_tasks/tasks"

EXPECTED_TASKS = 97
FILES_PER_TASK = 4  # buggy.py, reference.py, tests.py, meta.json
EXPECTED_FILES = EXPECTED_TASKS * FILES_PER_TASK  # 388


def die(message):
    print(f"freeze_hash: ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def git(*args):
    return subprocess.run(
        ["git", *args], cwd=REPO_ROOT,
        check=True, capture_output=True)


def main():
    listed = git("ls-files", "-z", TASKS_REL).stdout
    # Task-content files only: those inside a task_*/ directory. This excludes
    # the tracked tasks/.gitkeep scaffold (not task content).
    paths = sorted(p for p in listed.decode().split("\0")
                   if p and Path(p).parent.name.startswith("task_"))
    if not paths:
        die(f"no git-tracked task files under {TASKS_REL}")

    per_file_digests = []
    for path in paths:
        blob = git("show", f":{path}").stdout
        h = hashlib.sha256()
        h.update(path.encode("utf-8"))
        h.update(b"\0")
        h.update(blob)
        per_file_digests.append(h.hexdigest())

    freeze = hashlib.sha256(
        "".join(per_file_digests).encode("ascii")).hexdigest()

    # Per-directory accounting.
    dir_counts = Counter(str(Path(p).parent) for p in paths)
    task_dirs = sorted(d for d in dir_counts
                       if Path(d).name.startswith("task_"))
    bad_dirs = {d: dir_counts[d] for d in task_dirs
                if dir_counts[d] != FILES_PER_TASK}

    print(f"tracked files under {TASKS_REL}: {len(paths)}")
    print(f"task directories: {len(task_dirs)}  "
          f"(files/dir: expected {FILES_PER_TASK})")
    if bad_dirs:
        for d, c in sorted(bad_dirs.items()):
            print(f"  WRONG FILE COUNT: {d} has {c} files")
        die(f"{len(bad_dirs)} task dir(s) do not have exactly "
            f"{FILES_PER_TASK} files")
    if len(task_dirs) != EXPECTED_TASKS or len(paths) != EXPECTED_FILES:
        die(f"expected {EXPECTED_TASKS} dirs x {FILES_PER_TASK} = "
            f"{EXPECTED_FILES} files; got {len(task_dirs)} dirs / "
            f"{len(paths)} files")

    print(f"counts OK: {len(task_dirs)} tasks x {FILES_PER_TASK} files = "
          f"{len(paths)}")
    print(f"FREEZE_HASH sha256 {freeze}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
