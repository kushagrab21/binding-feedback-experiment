"""V3 full run — orchestrator over the 24 (model x mode x tier) cells.

6 models x 2 modes x 2 tiers = 24 cells; k1 = 60 test tasks, k2 = 48 test tasks, so
24 cells -> 6*2*(60+48) = 1,296 episodes. Each cell is its OWN process
(``run_one_cell_full.py``) with a SIGALRM hard per-episode deadline — the V2-P4.1
lesson: thread-pooled drivers wedge on OpenRouter slow-trickle responses, a
per-process signal deadline does not. SIGALRM is used from the START, not just for
recovery. Cells run with bounded concurrency; the orchestrator only collects the
per-cell manifests and assembles the single master manifest.

Steps:
  1. launch all 24 cells (bounded pool), each subprocess self-contained;
  2. require every cell exit 0 (0 errors after its retry passes) or stop-and-report;
  3. fold per-cell manifests into ``manifests/full_master.json`` (models+snapshots,
     routes, modes, tiers + freeze hashes + split shas, prereg tag commit, the V3-D1
     waiver quoted, per-cell summary, totals);
  4. schema-validate all 1,296 transcripts with the v1 schema validator;
  5. print totals + the $12 v3 stop-gate check.
"""

import glob
import hashlib
import json
import os
import subprocess
import sys

import run_common as G

sys.path.insert(0, os.path.join(G.repo_root(), "v2_ladder", "adapter"))
import validate_schema as V  # noqa: E402

MAX_CONCURRENT = 6
V3_STOP_GATE_USD = 12.0
V3_HARD_CAP_USD = 20.0
V3_SPEND_TO_DATE_USD = 0.074336  # calibration (V3-P2.1), from its committed manifest
EXPECTED_EPISODES = 1296


def _sha256_file(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _cells():
    out = []
    for model in G.MODEL_SLUGS:
        for mode in G.MODES:
            for tier in G.TIER_KEYS:
                out.append((model, mode, tier))
    return out


def _launch(cell):
    model, mode, tier = cell
    return subprocess.Popen(
        [sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "run_one_cell_full.py"), model, mode, tier],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def main():
    cells = _cells()
    print("V3 full run: %d cells (k1=60 + k2=48 test tasks per model x mode) = %d episodes"
          % (len(cells), 6 * 2 * (60 + 48)))
    results = {}
    pending = list(cells)
    running = {}  # proc -> cell
    while pending or running:
        while pending and len(running) < MAX_CONCURRENT:
            cell = pending.pop(0)
            running[_launch(cell)] = cell
        done_proc = None
        while done_proc is None:
            for proc in list(running):
                if proc.poll() is not None:
                    done_proc = proc
                    break
            if done_proc is None:
                os.wait()  # block until a child changes state; re-poll
        cell = running.pop(done_proc)
        out = done_proc.stdout.read() if done_proc.stdout else ""
        rc = done_proc.returncode
        results[cell] = rc
        tag = "OK" if rc == 0 else "NONZERO(rc=%d)" % rc
        print("[%s__%s__%s] %s  %s" % (cell[0], cell[1], cell[2], tag,
                                       out.strip().splitlines()[-1] if out.strip() else ""))

    # --- collect per-cell manifests -----------------------------------------
    cell_manifests = []
    all_rows = []
    for model, mode, tier in cells:
        cell = G.cell_name(model, mode, tier)
        cm_path = os.path.join(G.MANIFESTS_CELL_DIR, "full_%s.json" % cell)
        with open(cm_path, "r", encoding="utf-8") as fh:
            cm = json.load(fh)
        cell_manifests.append(cm)
        all_rows.extend(cm["episodes"])

    total_errors = sum(c["n_errors"] for c in cell_manifests)
    total_cost = round(sum(c["cell_cost_usd"] for c in cell_manifests), 6)

    # --- models block (resolved snapshots per model) -------------------------
    models_block = []
    seen = set()
    for c in cell_manifests:
        if c["model"] in seen:
            continue
        seen.add(c["model"])
        role = ("bottom-edge anchor" if c["model"] == G.BOTTOM_ANCHOR
                else "top anchor" if c["model"] == G.TOP_ANCHOR else "window")
        models_block.append({
            "model": c["model"], "slug": c["slug"], "snapshot": c["snapshot"],
            "request_id": c["request_id"], "model_resolved": c["model_resolved"],
            "route": c["route"], "provider": c["provider"],
            "price_per_1M_in": c["price_per_1M_in"], "price_per_1M_out": c["price_per_1M_out"],
            "role": role,
        })
    # keep models in roster order
    models_block.sort(key=lambda m: G.MODEL_SLUGS.index(m["model"]))

    master = {
        "phase": "V3-P4 full run (master)",
        "presentation": G.PRESENTATION,
        "config": G.D18_CONFIG,
        "modes": G.MODES,
        "models": models_block,
        "dropped_model": {"model": "llama-3.2-3b",
                          "reason": "below the window at k=0 (v2 advisory 66/87, 30 step_caps, "
                                    "binding below advisory); logged roster decision, PREREG §2"},
        "tiers": {
            tk: {"tier": G.TIERS[tk]["tier"], "n_bugs": G.TIERS[tk]["n_bugs"],
                 "freeze_hash": G.TIERS[tk]["freeze_hash"],
                 "split_sha256": _sha256_file(G.TIERS[tk]["split"]),
                 "n_test_tasks": len(G.test_task_ids(tk)),
                 "test_task_ids": G.test_task_ids(tk)}
            for tk in G.TIER_KEYS
        },
        "prereg_tag_commit": G.PREREG_TAG_COMMIT,
        "deviation_V3_D1": G.V3_D1_WAIVER,
        "n_cells": len(cell_manifests),
        "n_episodes": len(all_rows),
        "n_errors": total_errors,
        "total_cost_usd": total_cost,
        "v3_spend_to_date_usd": V3_SPEND_TO_DATE_USD,
        "cumulative_v3_spend_usd": round(V3_SPEND_TO_DATE_USD + total_cost, 6),
        "cell_manifests": ["full_%s.json" % G.cell_name(m, mo, tk)
                           for m in G.MODEL_SLUGS for mo in G.MODES for tk in G.TIER_KEYS],
        "cells": [{k: c[k] for k in ("cell", "model", "mode", "tier", "route",
                                     "provider", "model_resolved", "tier_freeze_hash",
                                     "n_episodes", "n_errors", "cell_cost_usd")}
                  for c in cell_manifests],
        "episodes": all_rows,
    }
    with open(G.MASTER_MANIFEST_PATH, "w", encoding="utf-8") as fh:
        json.dump(master, fh, indent=2)
        fh.write("\n")

    # --- schema-validate all transcripts -------------------------------------
    paths = sorted(glob.glob(os.path.join(G.LOGS_ROOT, "**", "*.jsonl"), recursive=True))
    n_files, n_ok, results_v = V.validate_many(paths)
    bad = {p: e for p, e in results_v.items() if e}

    # --- report --------------------------------------------------------------
    print("\n==== V3 FULL-RUN SUMMARY ====")
    nonzero = [c for c, rc in results.items() if rc != 0]
    print("cells exit 0: %d/%d  (nonzero: %s)"
          % (len(cells) - len(nonzero), len(cells), nonzero or "none"))
    print("episodes: %d   errors: %d" % (len(all_rows), total_errors))
    print("schema-validated: %d/%d  (bad: %d)" % (n_ok, n_files, len(bad)))
    for p in list(bad)[:10]:
        print("  SCHEMA-FAIL %s: %s" % (os.path.relpath(p, G.repo_root()), bad[p][:3]))
    print("item-1 cost: $%.6f" % total_cost)
    print("cumulative v3 spend: $%.6f  (calibration $%.6f + this run $%.6f)"
          % (V3_SPEND_TO_DATE_USD + total_cost, V3_SPEND_TO_DATE_USD, total_cost))
    cum = V3_SPEND_TO_DATE_USD + total_cost
    print("v3 stop-gate $%.2f: %s   hard cap $%.2f: %s"
          % (V3_STOP_GATE_USD, "OK" if cum < V3_STOP_GATE_USD else "TRIPPED",
             V3_HARD_CAP_USD, "OK" if cum < V3_HARD_CAP_USD else "TRIPPED"))
    print("master manifest: %s" % os.path.relpath(G.MASTER_MANIFEST_PATH, G.repo_root()))

    ok = (total_errors == 0 and not nonzero
          and n_ok == n_files == EXPECTED_EPISODES and cum < V3_STOP_GATE_USD)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
