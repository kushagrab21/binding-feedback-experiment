"""Phase 5.4 — THE FULL RUN: 2 models x 2 modes x 87 test tasks = 348 episodes (D18).

Runs the frozen 87-task TEST split (never the 10 dev tasks, never the fixtures) under
the bare-code presentation (D18: ``show_description=False`` -> withheld notice + buggy
source stripped of docstrings/comments). MODEL_A=gpt-4o-mini-2024-07-18 (cheap/weak),
MODEL_B=gpt-4.1 (frontier/strong); temp 0, cap 8.

For each of the four cells (model x mode) all 87 episodes run in sorted task order.
Transcripts are committed under ``logs/full/<model>__<mode>/task_NNN.jsonl``; one
manifest per cell (``manifests/full_<model>__<mode>.json``) plus a master manifest
(``manifests/full_master_manifest.json``).

Robustness (the P5.1 transient-403 lesson): the OpenAI client retries 429/5xx with
backoff; this driver adds an episode-level retry, and after the full sweep it makes up
to 2 more passes over any ``status="error"`` episodes. Final state must be 0 errors, or
the script exits non-zero for a stop-and-report. No task file is ever opened for reading
beyond what the harness loads programmatically; ``phase1_tasks/`` is never modified.
"""

import datetime
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)

sys.path.append(os.path.join(_REPO, "phase3_advisory"))
from providers import OpenAIChatClient, load_config  # noqa: E402


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ADVISORY = _load_module("adv_harness", os.path.join(_REPO, "phase3_advisory", "harness.py"))
BINDING = _load_module("bind_harness", os.path.join(_REPO, "phase4_binding", "harness.py"))

TASKS_DIR = os.path.join(_REPO, "phase1_tasks", "tasks")
SPLIT_PATH = os.path.join(_REPO, "phase1_tasks", "validation", "split.json")
FULL_LOG_DIR = os.path.join(_HERE, "logs", "full")
MANIFEST_DIR = os.path.join(_HERE, "manifests")

FREEZE_HASH = "dfc14c26ec267b03c2789752cf7e63c34a06fd3b94dc6cebe14f9f70b62f2017"
PRESENTATION = "bare-code"

MODELS = ["gpt-4o-mini-2024-07-18", "gpt-4.1"]
MODES = [("advisory", ADVISORY), ("binding", BINDING)]

SLEEP_BETWEEN = 0.5
EPISODE_RETRIES = 1     # per-episode, on top of the client's own 429/5xx backoff
EXTRA_PASSES = 2        # whole-cell re-runs over still-errored episodes after the sweep


def _sha256_file(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _resolved_model(log_path):
    try:
        with open(log_path, "r", encoding="utf-8") as fh:
            for line in fh:
                e = json.loads(line)
                if e.get("event") == "model_response":
                    return e.get("model")
    except Exception:
        pass
    return None


def _success(mode, status, final_passed):
    return bool(final_passed) if mode == "advisory" else (status == "solved")


def _run_one(mod, mode_name, task_id, config, cell_dir):
    """Run one episode; return a row dict (status='error' with a scrubbed message on
    failure). Copies the transcript to ``cell_dir/task_NNN.jsonl`` on success."""
    task_dir = os.path.join(TASKS_DIR, task_id)
    dest = os.path.join(cell_dir, task_id + ".jsonl")
    row = {"task_id": task_id, "mode": mode_name, "model": config["model"]}
    last_err = None
    for attempt in range(1, EPISODE_RETRIES + 2):
        try:
            client = OpenAIChatClient(config)
            summary = mod.run_episode(task_dir, client, config)
            shutil.copyfile(summary["log_path"], dest)
            row.update({
                "status": summary["status"],
                "success": _success(mode_name, summary["status"], summary["final_passed"]),
                "final_passed": summary["final_passed"],
                "steps": summary["steps"],
                "tokens_in": summary["tokens_in"],
                "tokens_out": summary["tokens_out"],
                "model_resolved": _resolved_model(dest),
                "log": os.path.relpath(dest, _REPO),
            })
            return row
        except Exception as exc:  # noqa: BLE001 — record, never skip
            last_err = str(exc).replace("\n", " ")[:300]
            if attempt < EPISODE_RETRIES + 1:
                time.sleep(2.0 * attempt)
    row.update({"status": "error", "error": last_err})
    return row


def _load_test_tasks():
    with open(SPLIT_PATH, "r", encoding="utf-8") as fh:
        split = json.load(fh)
    dev = set(split["dev"])
    test = sorted(split["test"])
    assert len(test) == 87, "expected 87 test tasks, got %d" % len(test)
    assert not (dev & set(test)), "dev/test overlap!"
    assert not any(t in dev for t in test), "a dev id appears in the test list!"
    return test, dev


def run_full():
    test_tasks, dev = _load_test_tasks()
    split_sha = _sha256_file(SPLIT_PATH)
    os.makedirs(MANIFEST_DIR, exist_ok=True)
    date = datetime.datetime.now().astimezone().isoformat()

    cell_manifest_names = []
    grand_errors = 0

    for model in MODELS:
        config = dict(load_config())
        config["model"] = model
        config["show_description"] = False   # D18 bare-code
        for mode_name, mod in MODES:
            cell = "%s__%s" % (model, mode_name)
            cell_dir = os.path.join(FULL_LOG_DIR, cell)
            if os.path.isdir(cell_dir):
                shutil.rmtree(cell_dir)
            os.makedirs(cell_dir, exist_ok=True)

            print("\n=== CELL %s : %d episodes ===" % (cell, len(test_tasks)),
                  file=sys.stderr)
            rows = []
            for i, task_id in enumerate(test_tasks, 1):
                row = _run_one(mod, mode_name, task_id, config, cell_dir)
                rows.append(row)
                tag = row.get("status")
                print("  [%s %d/87] %s -> %s" % (cell, i, task_id, tag),
                      file=sys.stderr)
                time.sleep(SLEEP_BETWEEN)

            # Extra passes over any errored episodes (transient-403 tolerance).
            for p in range(1, EXTRA_PASSES + 1):
                errored = [r for r in rows if r.get("status") == "error"]
                if not errored:
                    break
                print("  [%s] retry pass %d over %d errored episodes"
                      % (cell, p, len(errored)), file=sys.stderr)
                time.sleep(3.0)
                for idx, r in enumerate(rows):
                    if r.get("status") != "error":
                        continue
                    rows[idx] = _run_one(mod, mode_name, r["task_id"], config, cell_dir)
                    time.sleep(SLEEP_BETWEEN)

            errs = [r for r in rows if r.get("status") == "error"]
            grand_errors += len(errs)
            resolved = next((r.get("model_resolved") for r in rows
                             if r.get("model_resolved")), None)

            manifest = {
                "phase": "5.4 full run",
                "cell": cell,
                "model": model,
                "model_resolved": resolved,
                "mode": mode_name,
                "presentation": PRESENTATION,
                "date": date,
                "task_set_freeze_hash": FREEZE_HASH,
                "split_sha256": split_sha,
                "config": config,
                "n_episodes": len(rows),
                "n_errors": len(errs),
                "episodes": rows,
            }
            name = "full_%s.json" % cell
            with open(os.path.join(MANIFEST_DIR, name), "w", encoding="utf-8") as fh:
                json.dump(manifest, fh, indent=2)
                fh.write("\n")
            cell_manifest_names.append(name)
            print("  [%s] done: %d episodes, %d errors -> %s"
                  % (cell, len(rows), len(errs), name), file=sys.stderr)

    master = {
        "phase": "5.4 full run (master)",
        "date": date,
        "presentation": PRESENTATION,
        "models": MODELS,
        "modes": [m[0] for m in MODES],
        "n_test_tasks": len(test_tasks),
        "task_set_freeze_hash": FREEZE_HASH,
        "split_sha256": split_sha,
        "cell_manifests": cell_manifest_names,
        "total_episodes": len(MODELS) * len(MODES) * len(test_tasks),
        "total_errors": grand_errors,
    }
    with open(os.path.join(MANIFEST_DIR, "full_master_manifest.json"), "w",
              encoding="utf-8") as fh:
        json.dump(master, fh, indent=2)
        fh.write("\n")

    print("\nFULL RUN COMPLETE: %d episodes, %d errors"
          % (master["total_episodes"], grand_errors), file=sys.stderr)
    if grand_errors:
        print("STOP-AND-REPORT: %d episodes still errored after %d retry passes"
              % (grand_errors, EXTRA_PASSES), file=sys.stderr)
    return 0 if grand_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(run_full())
