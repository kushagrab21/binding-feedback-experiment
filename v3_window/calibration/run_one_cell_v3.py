"""V3 calibration — single-cell runner with a SIGALRM hard per-episode deadline.

One process per (model x mode x tier) cell, exactly the ``run_one_cell.py`` pattern
from V2-P4.1: a SIGALRM interrupts the blocking read itself (a socket timeout can be
evaded by a slow-trickle response, an alarm cannot), so no episode exceeds DEADLINE
seconds. Used from the START here (not just for recovery) per the work order.

Usage:  python3 run_one_cell_v3.py <model-slug> <mode> <tier-key>
  e.g.  python3 run_one_cell_v3.py qwen-2.5-7b advisory k1

Writes episode transcripts to ``logs/<model-slug>__<mode>__k{1,2}/<task_id>.jsonl``
and a per-cell fragment ``logs/<cell>/_cell.json`` (rows + resolved snapshot) that the
orchestrator folds into the single ``manifest.json``. Retries are recorded, never
skipped; a cell that still errors after the retry passes exits non-zero.
"""

import datetime
import json
import os
import shutil
import signal
import sys
import time

import cal_common as G

MODEL_SLUG, MODE, TIER_KEY = sys.argv[1], sys.argv[2], sys.argv[3]
DEADLINE = 150  # seconds, hard per-episode (matches v2)

rung = G.RUNG_BY_MODEL[MODEL_SLUG]
mod = G.MODE_MODULE[MODE]
tier = G.TIERS[TIER_KEY]
task_ids = G.dev_task_ids(TIER_KEY)

cell = G.cell_name(MODEL_SLUG, MODE, TIER_KEY)
cell_dir = os.path.join(G.LOGS_ROOT, cell)
if os.path.isdir(cell_dir):
    shutil.rmtree(cell_dir)
os.makedirs(cell_dir, exist_ok=True)

# Isolate the harness's scratch log dir PER CELL so concurrent cell processes never
# collide on a shared dev_logs path; we copy the finished transcript out ourselves.
_scratch = os.path.join(cell_dir, "_harness_scratch")
os.makedirs(_scratch, exist_ok=True)
G.R.ADVISORY.DEV_LOGS_DIR = _scratch
G.R.BINDING.DEV_LOGS_DIR = _scratch


class Deadline(Exception):
    pass


signal.signal(signal.SIGALRM, lambda s, f: (_ for _ in ()).throw(Deadline()))


def base_row(task_id):
    return {"task_id": task_id, "model": MODEL_SLUG, "rung": rung["rank"],
            "slug": rung["slug"], "snapshot": rung["model"], "route": rung["route"],
            "provider": rung["provider"], "mode": MODE, "tier": TIER_KEY}


def run_ep(task_id):
    dest = os.path.join(cell_dir, task_id + ".jsonl")
    tdir = G.task_dir(TIER_KEY, task_id)
    last = None
    for attempt in range(2):
        signal.alarm(DEADLINE)
        try:
            cli = G.C.LadderClient(rung, timeout=30, max_attempts=3)
            summary = mod.run_episode(tdir, cli, G.D18_CONFIG)
            signal.alarm(0)
            shutil.copyfile(summary["log_path"], dest)
            tin, tout = summary["tokens_in"], summary["tokens_out"]
            row = base_row(task_id)
            row.update({
                "status": summary["status"],
                "success": G.R._success(MODE, summary["status"], summary["final_passed"]),
                "final_passed": summary["final_passed"],
                "false_done": (MODE == "advisory"
                               and summary["status"] == "model_declared_done"
                               and not summary["final_passed"]),
                "steps": summary["steps"], "tokens_in": tin, "tokens_out": tout,
                "cost": G.C.episode_cost(tin, tout, rung),
                "model_resolved": G.R._resolved_model(dest),
                "log": os.path.relpath(dest, G.repo_root()),
            })
            return row
        except Deadline:
            signal.alarm(0)
            last = "hard-deadline %ds exceeded" % DEADLINE
        except Exception as e:  # noqa: BLE001 — record, never skip
            signal.alarm(0)
            last = str(e).replace("\n", " ")[:200]
        time.sleep(2)
    row = base_row(task_id)
    row.update({"status": "error", "success": False, "error": last})
    return row


rows = [run_ep(t) for t in task_ids]
for p in range(2):  # up to 2 whole-cell retry passes over still-errored episodes
    if not any(r.get("status") == "error" for r in rows):
        break
    print("  [%s] retry pass %d" % (cell, p + 1), file=sys.stderr)
    for i, r in enumerate(rows):
        if r.get("status") == "error":
            rows[i] = run_ep(r["task_id"])

# Drop the per-cell harness scratch (transcripts already copied out).
shutil.rmtree(_scratch, ignore_errors=True)

errs = [r for r in rows if r.get("status") == "error"]
resolved = next((r.get("model_resolved") for r in rows if r.get("model_resolved")), None)
fragment = {
    "cell": cell, "model": MODEL_SLUG, "mode": MODE, "tier": TIER_KEY,
    "rung": rung["rank"], "slug": rung["slug"], "snapshot": rung["model"],
    "request_id": rung.get("request_id", rung["model"]),
    "model_resolved": resolved, "route": rung["route"], "provider": rung["provider"],
    "price_per_1M_in": rung["pin"], "price_per_1M_out": rung["pout"],
    "tier_freeze_hash": tier["freeze_hash"],
    "date": datetime.datetime.now().astimezone().isoformat(),
    "n_episodes": len(rows), "n_errors": len(errs),
    "cell_cost_usd": round(sum(r.get("cost", 0) for r in rows), 6),
    "episodes": rows,
}
with open(os.path.join(cell_dir, "_cell.json"), "w", encoding="utf-8") as fh:
    json.dump(fragment, fh, indent=2)
    fh.write("\n")

print("CELL %s DONE: %d episodes, %d errors" % (cell, len(rows), len(errs)))
sys.exit(0 if not errs else 1)
