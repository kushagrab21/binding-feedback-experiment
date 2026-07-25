"""Phase 5.1 — the dev-set pilot.

Runs 2 models x 2 modes x 10 dev tasks = 40 live episodes:

    MODEL_A = gpt-4o-mini-2024-07-18   (cheap / weak arm)
    MODEL_B = gpt-4.1                   (frontier / strong arm)
    modes   = advisory, binding
    tasks   = the ten frozen dev tasks (bright line: dev tasks only)

Each episode's JSONL transcript is copied under ``phase5_runs/logs/pilot/`` (this
directory IS committed, unlike the per-harness ``dev_logs/``), and a manifest is
written to ``phase5_runs/manifests/pilot_manifest.json`` recording the models, modes,
task ids, the Phase-1 task-set FREEZE_HASH, the config, the date, and one summary row
per episode.

Politeness / robustness: a short sleep between calls; the OpenAI client already
retries 429/5xx with backoff, and this driver adds one episode-level retry on top.
An episode that still fails is recorded with ``status="error"`` (scrubbed message) —
never silently skipped.

Bright lines: only the ten dev tasks and the frozen config are touched; the 87 test
tasks are neither opened nor run here. The API key is never printed.
"""

import datetime
import importlib.util
import json
import os
import shutil
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)

# providers (OpenAIChatClient, load_config) live in phase3_advisory.
sys.path.append(os.path.join(_REPO, "phase3_advisory"))
from providers import OpenAIChatClient, load_config  # noqa: E402


def _load_module(name, path):
    """Load a harness module by absolute path (both are named ``harness.py``)."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ADVISORY = _load_module("adv_harness", os.path.join(_REPO, "phase3_advisory", "harness.py"))
BINDING = _load_module("bind_harness", os.path.join(_REPO, "phase4_binding", "harness.py"))

TASKS_DIR = os.path.join(_REPO, "phase1_tasks", "tasks")

FREEZE_HASH = "dfc14c26ec267b03c2789752cf7e63c34a06fd3b94dc6cebe14f9f70b62f2017"

MODELS = ["gpt-4o-mini-2024-07-18", "gpt-4.1"]
MODES = [("advisory", ADVISORY), ("binding", BINDING)]
DEV_TASKS = [
    "task_003", "task_006", "task_009", "task_013", "task_017",
    "task_020", "task_024", "task_026", "task_036", "task_047",
]

SLEEP_BETWEEN = 1.0     # polite pause between live calls
EPISODE_RETRIES = 1     # driver-level retries on top of the client's own backoff


def _resolved_model(log_path):
    """Pull the API's resolved snapshot id from the first model_response event."""
    try:
        with open(log_path, "r", encoding="utf-8") as fh:
            for line in fh:
                e = json.loads(line)
                if e.get("event") == "model_response":
                    return e.get("model")
    except Exception:
        pass
    return None


def _slug(model):
    return model.replace("/", "_")


def _success(mode, status, final_passed):
    """Mode-specific success: advisory = final verdict passed; binding = status solved."""
    return bool(final_passed) if mode == "advisory" else (status == "solved")


def run_pilot(hide_description=False, tag=None, presentation=None):
    # When hiding the description the shared builder applies D17 (withheld spec) and,
    # post-D18, also strips docstrings/comments (bare-code). ``tag``/``presentation`` let
    # a caller name the run (e.g. the D18 sweep is tag="pilot3", presentation="bare-code").
    if tag is None:
        tag = "pilot2" if hide_description else "pilot"
    if presentation is None:
        presentation = "hidden-description" if hide_description else "description-shown"
    show_description = not hide_description
    pilot_log_dir = os.path.join(_HERE, "logs", tag)
    manifest_path = os.path.join(_HERE, "manifests", "%s_manifest.json" % tag)

    # Fresh pilot dir every run -> exactly 40 committed transcripts, no stale files.
    if os.path.isdir(pilot_log_dir):
        shutil.rmtree(pilot_log_dir)
    os.makedirs(pilot_log_dir, exist_ok=True)
    os.makedirs(os.path.dirname(manifest_path), exist_ok=True)

    base_config = dict(load_config())
    base_config["show_description"] = show_description
    episodes = []
    n = 0
    total = len(MODELS) * len(MODES) * len(DEV_TASKS)

    for model in MODELS:
        config = dict(base_config)
        config["model"] = model
        for mode_name, mod in MODES:
            for task_id in DEV_TASKS:
                n += 1
                task_dir = os.path.join(TASKS_DIR, task_id)
                client = OpenAIChatClient(config)
                dest_name = "%s__%s__%s__%s.jsonl" % (tag, _slug(model), mode_name, task_id)
                dest = os.path.join(pilot_log_dir, dest_name)

                row = {"model": model, "mode": mode_name, "task_id": task_id}
                last_err = None
                for attempt in range(1, EPISODE_RETRIES + 2):
                    try:
                        summary = mod.run_episode(task_dir, client, config)
                        shutil.copyfile(summary["log_path"], dest)
                        row.update({
                            "status": summary["status"],
                            "success": _success(mode_name, summary["status"],
                                                 summary["final_passed"]),
                            "final_passed": summary["final_passed"],
                            "steps": summary["steps"],
                            "tokens_in": summary["tokens_in"],
                            "tokens_out": summary["tokens_out"],
                            "model_resolved": _resolved_model(dest),
                            "log": os.path.relpath(dest, _REPO),
                        })
                        last_err = None
                        break
                    except Exception as exc:  # noqa: BLE001 — record, never skip
                        last_err = str(exc).replace("\n", " ")[:300]
                        if attempt < EPISODE_RETRIES + 1:
                            time.sleep(2.0 * attempt)
                if last_err is not None:
                    row.update({"status": "error", "error": last_err})
                    print("[%d/%d] %-24s %-8s %-9s -> ERROR: %s"
                          % (n, total, model, mode_name, task_id, last_err[:80]),
                          file=sys.stderr)
                else:
                    print("[%d/%d] %-24s %-8s %-9s -> %-19s fp=%s steps=%s (%s/%s tok)"
                          % (n, total, model, mode_name, task_id, row["status"],
                             row["final_passed"], row["steps"],
                             row["tokens_in"], row["tokens_out"]))
                episodes.append(row)
                time.sleep(SLEEP_BETWEEN)

    manifest = {
        "phase": "%s dev-set pilot (presentation=%s)" % (tag, presentation),
        "presentation": presentation,
        "date": datetime.datetime.now().astimezone().isoformat(),
        "models": MODELS,
        "model_labels": {
            "gpt-4o-mini-2024-07-18": "MODEL_A cheap/weak",
            "gpt-4.1": "MODEL_B frontier/strong",
        },
        "modes": [m[0] for m in MODES],
        "task_ids": DEV_TASKS,
        "task_set_freeze_hash": FREEZE_HASH,
        "show_description": show_description,
        "config": base_config,
        "episodes": episodes,
    }
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
        fh.write("\n")

    errors = [e for e in episodes if e.get("status") == "error"]
    print("\npilot complete: %d episodes, %d errors (show_description=%s) -> %s"
          % (len(episodes), len(errors), show_description,
             os.path.relpath(manifest_path, _REPO)))
    return 0 if not errors else 1


if __name__ == "__main__":
    _bare = "--bare-code" in sys.argv
    _hide = _bare or ("--hide-description" in sys.argv)
    sys.exit(run_pilot(
        hide_description=_hide,
        tag="pilot3" if _bare else None,
        presentation="bare-code" if _bare else None,
    ))
