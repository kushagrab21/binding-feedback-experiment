"""V2 ladder — the shared episode runner (drives the frozen v1 harnesses via the adapter).

The pilot (dev tasks) and the full run (test tasks) are the SAME sweep over
``tasks × RUNGS × MODES``; only the task list and the output root differ, so both call
``run_cells`` here. Each cell is one (rung × mode); the frozen Phase-3 advisory / Phase-4
binding harness runs each episode with a per-rung ``LadderClient`` under the D18 config
(``show_description=False``, ``step_cap=8``, ``temperature=0``). Transcripts are copied to
``<out_root>/<rung-slug>__<mode>/task_NNN.jsonl`` and every one is schema-validated. Each
cell writes a manifest (provider/route/cost per episode, FREEZE_HASH, split sha, prereg
tag commit); a master manifest sums the cells.

Robustness mirrors v1 P5.4: the client retries 429/5xx with backoff, this driver adds an
episode-level retry, and after the sweep it makes up to ``EXTRA_PASSES`` more passes over
any ``status='error'`` episode. Final state must be 0 errors or the caller stops-and-reports.
No frozen v1 file is edited; ``phase1_tasks/`` is never modified.
"""

import datetime
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_V2 = os.path.dirname(_HERE)
_REPO = os.path.dirname(_V2)

sys.path.insert(0, os.path.join(_V2, "adapter"))
import client as C  # noqa: E402
import validate_schema as V  # noqa: E402


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ADVISORY = _load_module("adv_harness", os.path.join(_REPO, "phase3_advisory", "harness.py"))
BINDING = _load_module("bind_harness", os.path.join(_REPO, "phase4_binding", "harness.py"))

TASKS_DIR = os.path.join(_REPO, "phase1_tasks", "tasks")
SPLIT_PATH = os.path.join(_REPO, "phase1_tasks", "validation", "split.json")

FREEZE_HASH = "dfc14c26ec267b03c2789752cf7e63c34a06fd3b94dc6cebe14f9f70b62f2017"
PRESENTATION = "bare-code"
MODES = [("advisory", ADVISORY), ("binding", BINDING)]

# D18 config: bare-code presentation, step cap 8, temp 0. (Model comes from the client.)
D18_CONFIG = {"temperature": 0, "step_cap": 8, "show_description": False}

SLEEP_BETWEEN = 0.25
EPISODE_RETRIES = 1     # per-episode, on top of the client's own 429/5xx backoff
EXTRA_PASSES = 2        # whole-cell re-runs over still-errored episodes after the sweep


def _sha256_file(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _prereg_tag_commit():
    try:
        out = subprocess.run(["git", "rev-parse", "v2-prereg^{commit}"],
                             cwd=_REPO, capture_output=True, text=True, timeout=15)
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        return None


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


def _run_one(mod, mode_name, task_id, rung, cell_dir):
    """Run one episode; copy transcript to cell_dir/task_NNN.jsonl; return a row dict."""
    task_dir = os.path.join(TASKS_DIR, task_id)
    dest = os.path.join(cell_dir, task_id + ".jsonl")
    row = {"task_id": task_id, "mode": mode_name, "rung": rung["rank"],
           "slug": rung["slug"], "model": rung["model"], "route": rung["route"],
           "provider": rung["provider"]}
    last_err = None
    for attempt in range(1, EPISODE_RETRIES + 2):
        try:
            cli = C.LadderClient(rung)
            summary = mod.run_episode(task_dir, cli, D18_CONFIG)
            shutil.copyfile(summary["log_path"], dest)
            tin, tout = summary["tokens_in"], summary["tokens_out"]
            row.update({
                "status": summary["status"],
                "success": _success(mode_name, summary["status"], summary["final_passed"]),
                "final_passed": summary["final_passed"],
                "false_done": (mode_name == "advisory"
                               and summary["status"] == "model_declared_done"
                               and not summary["final_passed"]),
                "steps": summary["steps"],
                "tokens_in": tin,
                "tokens_out": tout,
                "cost": C.episode_cost(tin, tout, rung),
                "model_resolved": _resolved_model(dest),
                "log": os.path.relpath(dest, _REPO),
            })
            return row
        except Exception as exc:  # noqa: BLE001 — record, never skip
            last_err = str(exc).replace("\n", " ")[:300]
            if attempt < EPISODE_RETRIES + 1:
                time.sleep(2.0 * attempt)
    row.update({"status": "error", "success": False, "error": last_err})
    return row


def load_tasks(which):
    with open(SPLIT_PATH, "r", encoding="utf-8") as fh:
        split = json.load(fh)
    return sorted(split[which])


def _run_cell(rung, mode_name, mod, task_ids, out_root, manifest_dir,
              phase_label, split_sha, tag_commit, date, log):
    """Run one (rung × mode) cell: sweep + retry passes + write the cell manifest.

    Returns (cell, rows, manifest_name, n_errors)."""
    cell = "%s__%s" % (rung["slug"], mode_name)
    cell_dir = os.path.join(out_root, cell)
    if os.path.isdir(cell_dir):
        shutil.rmtree(cell_dir)
    os.makedirs(cell_dir, exist_ok=True)

    print("\n=== CELL %s : %d episodes ===" % (cell, len(task_ids)), file=log)
    rows = []
    for i, task_id in enumerate(task_ids, 1):
        row = _run_one(mod, mode_name, task_id, rung, cell_dir)
        rows.append(row)
        print("  [%s %d/%d] %s -> %s" % (cell, i, len(task_ids), task_id,
                                         row.get("status")), file=log)
        time.sleep(SLEEP_BETWEEN)

    for p in range(1, EXTRA_PASSES + 1):
        errored = [r for r in rows if r.get("status") == "error"]
        if not errored:
            break
        print("  [%s] retry pass %d over %d errored" % (cell, p, len(errored)), file=log)
        time.sleep(3.0)
        for idx, r in enumerate(rows):
            if r.get("status") != "error":
                continue
            rows[idx] = _run_one(mod, mode_name, r["task_id"], rung, cell_dir)
            time.sleep(SLEEP_BETWEEN)

    errs = [r for r in rows if r.get("status") == "error"]
    resolved = next((r.get("model_resolved") for r in rows if r.get("model_resolved")), None)
    manifest = {
        "phase": phase_label, "cell": cell, "rung": rung["rank"], "model": rung["model"],
        "model_resolved": resolved, "route": rung["route"], "provider": rung["provider"],
        "price_per_1M_in": rung["pin"], "price_per_1M_out": rung["pout"], "mode": mode_name,
        "presentation": PRESENTATION, "date": date, "task_set_freeze_hash": FREEZE_HASH,
        "split_sha256": split_sha, "prereg_tag_commit": tag_commit, "config": D18_CONFIG,
        "n_episodes": len(rows), "n_errors": len(errs),
        "cell_cost_usd": round(sum(r.get("cost", 0) for r in rows), 6), "episodes": rows,
    }
    name = "%s_%s.json" % (phase_label, cell)
    with open(os.path.join(manifest_dir, name), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
        fh.write("\n")
    print("  [%s] done: %d episodes, %d errors -> %s"
          % (cell, len(rows), len(errs), name), file=log)
    return cell, rows, name, len(errs)


def run_cells(task_ids, out_root, manifest_dir, phase_label, log=sys.stderr,
              parallel_rungs=False):
    """Run tasks × RUNGS × MODES. Returns (rows_by_cell, master) and writes manifests.

    When ``parallel_rungs`` is set, the 7 rungs run concurrently (each a worker running
    its own two cells sequentially). Rungs are independent models, so this only overlaps
    network waits; each episode's log/id/manifest paths are disjoint per cell and the
    frozen harness's id counter is atomic, so the outputs are identical to the sequential
    order — only wall-clock differs.
    """
    os.makedirs(out_root, exist_ok=True)
    os.makedirs(manifest_dir, exist_ok=True)
    split_sha = _sha256_file(SPLIT_PATH)
    tag_commit = _prereg_tag_commit()
    date = datetime.datetime.now().astimezone().isoformat()

    def _rung_work(rung):
        out = []
        for mode_name, mod in MODES:
            out.append(_run_cell(rung, mode_name, mod, task_ids, out_root, manifest_dir,
                                 phase_label, split_sha, tag_commit, date, log))
        return out

    rows_by_cell = {}
    cell_manifest_names = []
    grand_errors = 0

    if parallel_rungs:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=len(C.RUNGS)) as ex:
            for cell_results in ex.map(_rung_work, C.RUNGS):
                for cell, rows, name, n_errs in cell_results:
                    rows_by_cell[cell] = rows
                    cell_manifest_names.append(name)
                    grand_errors += n_errs
    else:
        for rung in C.RUNGS:
            for cell, rows, name, n_errs in _rung_work(rung):
                rows_by_cell[cell] = rows
                cell_manifest_names.append(name)
                grand_errors += n_errs

    total_cost = round(sum(r.get("cost", 0) for rows in rows_by_cell.values() for r in rows), 6)
    total_eps = sum(len(rows) for rows in rows_by_cell.values())
    master = {
        "phase": phase_label + " (master)",
        "date": date,
        "presentation": PRESENTATION,
        "rungs": [r["slug"] for r in C.RUNGS],
        "modes": [m[0] for m in MODES],
        "n_tasks": len(task_ids),
        "task_set_freeze_hash": FREEZE_HASH,
        "split_sha256": split_sha,
        "prereg_tag_commit": tag_commit,
        "cell_manifests": cell_manifest_names,
        "total_episodes": total_eps,
        "total_errors": grand_errors,
        "total_cost_usd": total_cost,
    }
    with open(os.path.join(manifest_dir, "%s_master.json" % phase_label), "w",
              encoding="utf-8") as fh:
        json.dump(master, fh, indent=2)
        fh.write("\n")
    return rows_by_cell, master


def validate_logs(out_root):
    """Schema-validate every .jsonl under out_root. Returns (n_files, n_ok, bad)."""
    import glob
    paths = sorted(glob.glob(os.path.join(out_root, "**", "*.jsonl"), recursive=True))
    n_files, n_ok, results = V.validate_many(paths)
    bad = {p: e for p, e in results.items() if e}
    return n_files, n_ok, bad
