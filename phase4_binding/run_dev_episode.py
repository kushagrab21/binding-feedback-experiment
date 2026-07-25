"""Phase 4.2 — run a single LIVE binding episode on a dev task (or a fixture).

Usage:
    python3 run_dev_episode.py <task_id>
    python3 run_dev_episode.py --task-dir <path-under-a-fixtures/-dir>

Mirrors the advisory runner's CLI shape, but drives the BINDING loop
(``phase4_binding/harness.py``). It builds an ``OpenAIChatClient`` from the shared
``phase3_advisory/config.json`` (gpt-4.1-mini, temperature 0, step cap 8 — identical
to the advisory arm, so the arms differ only structurally), runs one binding episode,
writes the JSONL transcript to ``phase4_binding/dev_logs/``, and prints a one-line
summary::

    <task_id> <status> <final_passed> <steps> <tokens_in> <tokens_out>

The builder never writes task code: the model does all the solving. Only the ten dev
tasks may be run by id; ``--task-dir`` is accepted **only** for synthetic fixtures
under a ``fixtures/`` directory of *either* phase (``phase3_advisory/fixtures/`` or
``phase4_binding/fixtures/``), never a phase1 task — the bright line is enforced by a
``commonpath`` containment check against those fixture roots.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)

# phase4's own dir first so ``import harness`` binds the BINDING harness; the phase3
# providers module is appended so it cannot shadow ``harness``.
sys.path.insert(0, _HERE)
sys.path.append(os.path.join(_REPO_ROOT, "phase3_advisory"))

import harness  # binding harness
from providers import OpenAIChatClient, load_config

TASKS_DIR = os.path.join(_REPO_ROOT, "phase1_tasks", "tasks")

# Fixtures may live under either phase's fixtures/ dir; both are valid --task-dir roots.
FIXTURE_ROOTS = [
    os.path.abspath(os.path.join(_REPO_ROOT, "phase3_advisory", "fixtures")),
    os.path.abspath(os.path.join(_HERE, "fixtures")),
]

# Bright line: only these dev tasks may ever be opened/run.
DEV_TASKS = {
    "task_003", "task_006", "task_009", "task_013", "task_017",
    "task_020", "task_024", "task_026", "task_036", "task_047",
}


def _under_a_fixture_root(path):
    for root in FIXTURE_ROOTS:
        if os.path.isdir(root) and os.path.commonpath([path, root]) == root:
            return True
    return False


def _resolve_task_dir(argv):
    """Return a task_dir path or ``None`` (with an error printed) on refusal."""
    if len(argv) == 3 and argv[1] == "--task-dir":
        path = os.path.abspath(argv[2])
        # Must live strictly under a fixtures/ root of either phase — never a phase1 task.
        if not _under_a_fixture_root(path):
            print("refusing: --task-dir is only allowed under a phase fixtures/ "
                  "directory (bright line)", file=sys.stderr)
            return None
        if not os.path.isdir(path):
            print("no such task dir: %s" % path, file=sys.stderr)
            return None
        return path
    if len(argv) == 2:
        task_id = argv[1]
        if task_id not in DEV_TASKS:
            print("refusing: %r is not a dev task (bright line)" % task_id,
                  file=sys.stderr)
            return None
        task_dir = os.path.join(TASKS_DIR, task_id)
        if not os.path.isdir(task_dir):
            print("no such task dir: %s" % task_dir, file=sys.stderr)
            return None
        return task_dir
    print("usage: python3 run_dev_episode.py <task_id> | --task-dir <path>",
          file=sys.stderr)
    return None


def main(argv):
    task_dir = _resolve_task_dir(argv)
    if task_dir is None:
        return 2

    config = load_config()  # shared phase3_advisory/config.json
    client = OpenAIChatClient(config)
    summary = harness.run_episode(task_dir, client, config)

    print("%s %s %s %s %s %s" % (
        summary["task_id"], summary["status"], summary["final_passed"],
        summary["steps"], summary["tokens_in"], summary["tokens_out"],
    ))
    print("log -> %s" % summary["log_path"], file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
