"""V3 calibration — orchestrator over the 20 (model x mode x tier) cells.

5 models x 2 modes x 2 tiers = 20 cells x 10 dev tasks = 200 episodes. Each cell is
its OWN process (``run_one_cell_v3.py``) with a SIGALRM hard per-episode deadline —
the V2-P4.1 lesson: thread-pooled drivers wedge on OpenRouter slow-trickle responses,
a per-process signal deadline does not. Cells run with bounded concurrency; the
orchestrator only collects fragments and assembles the single ``manifest.json``.

Steps:
  1. launch all 20 cells (bounded pool), each subprocess self-contained;
  2. require every cell exit 0 (0 errors after its retry passes) or stop-and-report;
  3. fold per-cell fragments into ``manifest.json`` (models+snapshots, routes, modes,
     tiers, tier freeze hashes, split sha256s, config, per-episode rows);
  4. schema-validate all 200 transcripts with the v1 schema validator;
  5. print totals + the $12 v3 stop-gate check.
"""

import hashlib
import json
import os
import subprocess
import sys

import cal_common as G

sys.path.insert(0, os.path.join(G.repo_root(), "v2_ladder", "adapter"))
import validate_schema as V  # noqa: E402

MAX_CONCURRENT = 5
V3_STOP_GATE_USD = 12.0
V3_HARD_CAP_USD = 20.0


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
                                      "run_one_cell_v3.py"), model, mode, tier],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def main():
    cells = _cells()
    print("V3 calibration: %d cells x 10 dev tasks = %d episodes"
          % (len(cells), len(cells) * 10))
    results = {}
    pending = list(cells)
    running = {}  # proc -> cell
    while pending or running:
        while pending and len(running) < MAX_CONCURRENT:
            cell = pending.pop(0)
            running[_launch(cell)] = cell
        # wait for any one to finish
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

    # --- collect fragments ---------------------------------------------------
    fragments = []
    all_rows = []
    for model, mode, tier in cells:
        cell = G.cell_name(model, mode, tier)
        frag_path = os.path.join(G.LOGS_ROOT, cell, "_cell.json")
        with open(frag_path, "r", encoding="utf-8") as fh:
            frag = json.load(fh)
        fragments.append(frag)
        all_rows.extend(frag["episodes"])

    total_errors = sum(f["n_errors"] for f in fragments)
    total_cost = round(sum(f["cell_cost_usd"] for f in fragments), 6)

    # --- models block (resolved snapshots per model) -------------------------
    models_block = []
    seen = set()
    for f in fragments:
        if f["model"] in seen:
            continue
        seen.add(f["model"])
        models_block.append({
            "model": f["model"], "slug": f["slug"], "snapshot": f["snapshot"],
            "request_id": f["request_id"], "model_resolved": f["model_resolved"],
            "route": f["route"], "provider": f["provider"],
            "price_per_1M_in": f["price_per_1M_in"], "price_per_1M_out": f["price_per_1M_out"],
            "band_member": f["model"] in G.WINDOW_MODELS,
            "ceiling_probe": f["model"] == G.CEILING_PROBE,
        })

    manifest = {
        "phase": "V3-P2 dev calibration",
        "presentation": G.PRESENTATION,
        "config": G.D18_CONFIG,
        "modes": G.MODES,
        "models": models_block,
        "tiers": {
            tk: {"tier": G.TIERS[tk]["tier"], "n_bugs": G.TIERS[tk]["n_bugs"],
                 "freeze_hash": G.TIERS[tk]["freeze_hash"],
                 "split_sha256": _sha256_file(G.TIERS[tk]["split"]),
                 "dev_task_ids": G.dev_task_ids(tk)}
            for tk in G.TIER_KEYS
        },
        "n_cells": len(fragments),
        "n_episodes": len(all_rows),
        "n_errors": total_errors,
        "total_cost_usd": total_cost,
        "cells": [{k: f[k] for k in ("cell", "model", "mode", "tier", "route",
                                     "provider", "model_resolved", "n_episodes",
                                     "n_errors", "cell_cost_usd")} for f in fragments],
        "episodes": all_rows,
    }
    with open(G.MANIFEST_PATH, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
        fh.write("\n")

    # --- schema-validate all transcripts -------------------------------------
    import glob
    paths = sorted(glob.glob(os.path.join(G.LOGS_ROOT, "**", "*.jsonl"), recursive=True))
    n_files, n_ok, results_v = V.validate_many(paths)
    bad = {p: e for p, e in results_v.items() if e}

    # --- report --------------------------------------------------------------
    print("\n==== V3 CALIBRATION SUMMARY ====")
    nonzero = [c for c, rc in results.items() if rc != 0]
    print("cells exit 0: %d/%d  (nonzero: %s)"
          % (len(cells) - len(nonzero), len(cells), nonzero or "none"))
    print("episodes: %d   errors: %d" % (len(all_rows), total_errors))
    print("schema-validated: %d/%d  (bad: %d)" % (n_ok, n_files, len(bad)))
    for p in list(bad)[:10]:
        print("  SCHEMA-FAIL %s: %s" % (os.path.relpath(p, G.repo_root()), bad[p][:3]))
    print("item-1 cost: $%.6f" % total_cost)
    print("cumulative v3 spend: $%.6f  (V3-P0/P1 made no API calls -> this run is all of it)"
          % total_cost)
    print("v3 stop-gate $%.2f: %s   hard cap $%.2f: %s"
          % (V3_STOP_GATE_USD, "OK" if total_cost < V3_STOP_GATE_USD else "TRIPPED",
             V3_HARD_CAP_USD, "OK" if total_cost < V3_HARD_CAP_USD else "TRIPPED"))
    print("manifest: %s" % os.path.relpath(G.MANIFEST_PATH, G.repo_root()))

    ok = (total_errors == 0 and not nonzero and n_ok == n_files == 200
          and total_cost < V3_STOP_GATE_USD)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
