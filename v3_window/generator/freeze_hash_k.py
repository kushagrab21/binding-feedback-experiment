"""Compute a per-tier freeze hash over git-tracked composition-task content.

This is the frozen v1 ``freeze_hash.py`` METHOD, parameterized by tier — the v1
tool is NOT modified. For tier k it fingerprints the exact byte content of every
git-tracked file living inside a ``task_*/`` directory under
``v3_window/tasks/k{tier}`` (dropping any non-task siblings such as split.json,
rejected_combos.json, validation_report.txt, or a .gitkeep). Content is read via
``git show :path`` (the index), so untracked noise — iCloud conflict copies,
__pycache__ — cannot perturb the hash.

Algorithm (identical to v1):
  paths = git ls-files v3_window/tasks/k{tier}, kept only if inside task_*/;
  per_file = sha256(path + '\\0' + tracked-blob-bytes);
  FREEZE_HASH = sha256(concat of per-file hex digests, in sorted path order).

Every task dir must hold exactly 4 files (buggy.py, reference.py, tests.py,
meta.json); the task count is whatever the tier emitted (not hardcoded, since k=2
supply may fall short of 70). Run twice: the FREEZE line is identical.

    python3 v3_window/generator/freeze_hash_k.py --tier 1
    python3 v3_window/generator/freeze_hash_k.py --tier 2
"""

import argparse
import hashlib
import subprocess
import sys
from collections import Counter
from pathlib import Path

GEN_DIR = Path(__file__).resolve().parent
REPO_ROOT = GEN_DIR.parent.parent
FILES_PER_TASK = 4  # buggy.py, reference.py, tests.py, meta.json


def die(message):
    print(f"freeze_hash_k: ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def git(*args):
    return subprocess.run(["git", *args], cwd=REPO_ROOT,
                          check=True, capture_output=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", type=int, choices=(1, 2), required=True)
    args = ap.parse_args()
    rel = f"v3_window/tasks/k{args.tier}"

    listed = git("ls-files", "-z", rel).stdout
    paths = sorted(p for p in listed.decode().split("\0")
                   if p and Path(p).parent.name.startswith("task_"))
    if not paths:
        die(f"no git-tracked task files under {rel} "
            f"(stage/commit the tier first)")

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

    dir_counts = Counter(str(Path(p).parent) for p in paths)
    task_dirs = sorted(dir_counts)
    bad = {d: dir_counts[d] for d in task_dirs
           if dir_counts[d] != FILES_PER_TASK}

    print(f"tracked task files under {rel}: {len(paths)}")
    print(f"task directories: {len(task_dirs)}  "
          f"(files/dir: expected {FILES_PER_TASK})")
    if bad:
        for d, c in sorted(bad.items()):
            print(f"  WRONG FILE COUNT: {d} has {c} files")
        die(f"{len(bad)} task dir(s) do not have exactly {FILES_PER_TASK} files")
    if len(paths) != len(task_dirs) * FILES_PER_TASK:
        die("file/dir count mismatch")

    print(f"counts OK: {len(task_dirs)} tasks x {FILES_PER_TASK} files = "
          f"{len(paths)}")
    print(f"FREEZE_HASH_K{args.tier} sha256 {freeze}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
