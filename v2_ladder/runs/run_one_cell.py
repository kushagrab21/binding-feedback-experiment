"""Single-cell runner with a SIGALRM hard per-episode deadline (main-thread only).

Unlike a socket timeout (which a slow-trickle connection evades), SIGALRM interrupts the
blocking read itself, so no episode can exceed DEADLINE seconds. Used to finish the two
OpenRouter open-weight cells that intermittently wedged. Row/manifest shapes match the
committed runner exactly so the outputs are indistinguishable from a normal run.
"""
import sys, os, signal, time, shutil, json, datetime
sys.path.insert(0, 'v2_ladder/runs'); sys.path.insert(0, 'v2_ladder/adapter')
import runner as R, client as C

SLUG, MODE = sys.argv[1], sys.argv[2]
DEADLINE = 150
rung = C.RUNGS_BY_SLUG[SLUG]
mod = dict(R.MODES)[MODE]
test = R.load_tasks('test')
OUT = 'v2_ladder/runs/logs/full'; MAN = 'v2_ladder/runs/manifests'
cell = '%s__%s' % (SLUG, MODE)
cell_dir = os.path.join(OUT, cell)
if os.path.isdir(cell_dir): shutil.rmtree(cell_dir)
os.makedirs(cell_dir, exist_ok=True)

class Deadline(Exception): pass
signal.signal(signal.SIGALRM, lambda s, f: (_ for _ in ()).throw(Deadline()))

def base_row(task_id):
    return {"task_id": task_id, "mode": MODE, "rung": rung["rank"], "slug": rung["slug"],
            "model": rung["model"], "route": rung["route"], "provider": rung["provider"]}

def run_ep(task_id):
    dest = os.path.join(cell_dir, task_id + '.jsonl')
    task_dir = os.path.join(R.TASKS_DIR, task_id)
    last = None
    for attempt in range(2):
        signal.alarm(DEADLINE)
        try:
            cli = C.LadderClient(rung, timeout=30, max_attempts=3)
            summary = mod.run_episode(task_dir, cli, R.D18_CONFIG)
            signal.alarm(0)
            shutil.copyfile(summary['log_path'], dest)
            tin, tout = summary['tokens_in'], summary['tokens_out']
            row = base_row(task_id)
            row.update({"status": summary['status'],
                        "success": R._success(MODE, summary['status'], summary['final_passed']),
                        "final_passed": summary['final_passed'],
                        "false_done": (MODE == 'advisory' and summary['status'] == 'model_declared_done' and not summary['final_passed']),
                        "steps": summary['steps'], "tokens_in": tin, "tokens_out": tout,
                        "cost": C.episode_cost(tin, tout, rung),
                        "model_resolved": R._resolved_model(dest),
                        "log": os.path.relpath(dest, R._REPO)})
            return row
        except Deadline:
            signal.alarm(0); last = "hard-deadline %ds exceeded" % DEADLINE
        except Exception as e:
            signal.alarm(0); last = str(e).replace("\n", " ")[:200]
        time.sleep(2)
    row = base_row(task_id); row.update({"status": "error", "success": False, "error": last})
    return row

rows = [run_ep(t) for t in test]
for p in range(2):
    if not any(r.get('status') == 'error' for r in rows): break
    print("  [%s] retry pass %d" % (cell, p + 1), file=sys.stderr)
    for i, r in enumerate(rows):
        if r.get('status') == 'error':
            rows[i] = run_ep(r['task_id'])

errs = [r for r in rows if r.get('status') == 'error']
resolved = next((r.get('model_resolved') for r in rows if r.get('model_resolved')), None)
manifest = {"phase": "full", "cell": cell, "rung": rung["rank"], "model": rung["model"],
            "model_resolved": resolved, "route": rung["route"], "provider": rung["provider"],
            "price_per_1M_in": rung["pin"], "price_per_1M_out": rung["pout"], "mode": MODE,
            "presentation": R.PRESENTATION, "date": datetime.datetime.now().astimezone().isoformat(),
            "task_set_freeze_hash": R.FREEZE_HASH, "split_sha256": R._sha256_file(R.SPLIT_PATH),
            "prereg_tag_commit": R._prereg_tag_commit(), "config": R.D18_CONFIG,
            "n_episodes": len(rows), "n_errors": len(errs),
            "cell_cost_usd": round(sum(r.get('cost', 0) for r in rows), 6), "episodes": rows}
with open(os.path.join(MAN, "full_%s.json" % cell), "w") as fh:
    json.dump(manifest, fh, indent=2); fh.write("\n")
print("CELL %s DONE: %d episodes, %d errors" % (cell, len(rows), len(errs)))
sys.exit(0 if not errs else 1)
