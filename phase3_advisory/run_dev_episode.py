"""Phase 3.2 — run a single LIVE advisory episode on a dev task (or a fixture).

Usage:
    python3 run_dev_episode.py <task_id>
    python3 run_dev_episode.py --task-dir <path-under-fixtures/>

Builds an ``OpenAIChatClient`` from ``config.json`` (gpt-4.1-mini, temperature 0,
step cap 8), runs one advisory episode, writes the JSONL transcript to ``dev_logs/``,
and prints a one-line summary::

    <task_id> <status> <final_passed> <steps> <tokens_in> <tokens_out>

The builder never writes task code: the model does all the solving. Only the ten dev
tasks may be run by id; ``--task-dir`` is accepted **only** for synthetic fixtures
under ``phase3_advisory/fixtures/`` (never a phase1 task), preserving the bright line.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import harness
from providers import OpenAIChatClient, load_config

_REPO_ROOT = os.path.dirname(_HERE)
TASKS_DIR = os.path.join(_REPO_ROOT, "phase1_tasks", "tasks")
FIXTURES_DIR = os.path.join(_HERE, "fixtures")

# Bright line: only these dev tasks may ever be opened/run.
DEV_TASKS = {
    "task_003", "task_006", "task_009", "task_013", "task_017",
    "task_020", "task_024", "task_026", "task_036", "task_047",
}


def _resolve_task_dir(argv):
    """Return a task_dir path or ``None`` (with an error printed) on refusal."""
    if len(argv) == 3 and argv[1] == "--task-dir":
        path = os.path.abspath(argv[2])
        fixtures_root = os.path.abspath(FIXTURES_DIR)
        # Must live strictly under fixtures/ — never a phase1 task.
        if os.path.commonpath([path, fixtures_root]) != fixtures_root:
            print("refusing: --task-dir is only allowed under phase3_advisory/"
                  "fixtures/ (bright line)", file=sys.stderr)
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

    config = load_config()
    client = OpenAIChatClient(config)
    summary = harness.run_episode(task_dir, client, config)

    print("%s %s %s %s %s %s" % (
        summary["task_id"], summary["status"], summary["final_passed"],
        summary["steps"], summary["tokens_in"], summary["tokens_out"],
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
