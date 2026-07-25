"""V2-P3 — the DEV PILOT: 10 dev tasks × 7 rungs × 2 modes = 140 episodes (D18).

Runs the frozen 10-task DEV split (never the 87 test tasks) through the adapter, commits
transcripts under ``v2_ladder/runs/logs/pilot/<rung-slug>__<mode>/task_NNN.jsonl`` with one
manifest per cell + a master, schema-validates all 140 logs, prints the per-cell pilot
table (success / fail / false-DONE / step_cap / steps / tokens / cost / ×87 projection),
and evaluates the four pre-authorization criteria as PASS/FAIL:

  (1) pilot errors after retries == 0
  (2) schema validator: zero diffs on all 140 pilot logs
  (3) pilot actual cost ≤ 3× the prereg projection pro-rated for 140 episodes
  (4) rung 6 (or its fallback) confirmed reasoning-free

Exit 0 iff ALL FOUR PASS (the full run may launch); non-zero otherwise (stop-and-report).
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "adapter"))
import runner as R  # noqa: E402
import client as C  # noqa: E402

PILOT_LOG_ROOT = os.path.join(_HERE, "logs", "pilot")
MANIFEST_DIR = os.path.join(_HERE, "manifests")

# Prereg §(e): padded projection for the full 1218-episode run.
PREREG_FULL_PROJECTION = 1.251
FULL_EPISODES = 1218
PILOT_EPISODES = 140


def _cell_stats(rows):
    n = len(rows)
    succ = sum(1 for r in rows if r.get("success"))
    err = sum(1 for r in rows if r.get("status") == "error")
    false_done = sum(1 for r in rows if r.get("false_done"))
    step_cap = sum(1 for r in rows if r.get("status") == "step_cap")
    steps = [r.get("steps", 0) for r in rows if "steps" in r]
    mean_steps = (sum(steps) / len(steps)) if steps else 0.0
    tin = sum(r.get("tokens_in", 0) for r in rows)
    tout = sum(r.get("tokens_out", 0) for r in rows)
    cost = sum(r.get("cost", 0.0) for r in rows)
    return {"n": n, "succ": succ, "fail": n - succ, "err": err, "false_done": false_done,
            "step_cap": step_cap, "mean_steps": mean_steps, "tin": tin, "tout": tout,
            "cost": cost, "x87_proj": cost * 8.7}


def _print_table(rows_by_cell):
    hdr = ("%-30s %-9s %4s %4s %5s %6s %6s %8s %8s %9s %10s"
           % ("cell", "mode", "succ", "fail", "fDONE", "cap", "steps", "tok_in",
              "tok_out", "cost$", "x87proj$"))
    print(hdr)
    print("-" * len(hdr))
    for rung in C.RUNGS:
        for mode in ("advisory", "binding"):
            cell = "%s__%s" % (rung["slug"], mode)
            s = _cell_stats(rows_by_cell[cell])
            print("%-30s %-9s %2d/%-2d %4d %5d %6d %6.1f %8d %8d %9.5f %10.4f"
                  % (rung["slug"], mode, s["succ"], s["n"], s["fail"], s["false_done"],
                     s["step_cap"], s["mean_steps"], s["tin"], s["tout"], s["cost"],
                     s["x87_proj"]))


def _rung6_reasoning_free():
    """Criterion (4): re-confirm rung 6 (registered, or fallback) is reasoning-free."""
    r6 = next(r for r in C.RUNGS if r["rank"] == 6)
    cli = C.LadderClient(r6)
    try:
        resp = cli.complete([{"role": "user", "content": "Respond with exactly: pong"}])
    except Exception as exc:  # noqa: BLE001
        return False, "rung6 call error: %s" % str(exc)[:120]
    free = (not cli.last_reasoning_text) and (not cli.last_reasoning_tokens) \
        and resp.get("tokens_in", 0) > 0 and resp.get("tokens_out", 0) > 0
    return free, ("reasoning_tokens=%s reasoning_text=%r"
                  % (cli.last_reasoning_tokens or 0, (cli.last_reasoning_text or "")[:30]))


def main():
    dev = R.load_tasks("dev")
    assert len(dev) == 10, "expected 10 dev tasks, got %d" % len(dev)
    print("DEV PILOT: %d tasks × %d rungs × 2 modes = %d episodes"
          % (len(dev), len(C.RUNGS), len(dev) * len(C.RUNGS) * 2), file=sys.stderr)

    rows_by_cell, master = R.run_cells(dev, PILOT_LOG_ROOT, MANIFEST_DIR, "pilot")

    print("\n================ PILOT TABLE ================")
    _print_table(rows_by_cell)

    total_cost = master["total_cost_usd"]
    total_err = master["total_errors"]
    total_eps = master["total_episodes"]
    print("\ntotal episodes: %d   total errors: %d   total pilot cost: $%.5f"
          % (total_eps, total_err, total_cost))

    # ---- schema validation over all 140 pilot logs ----
    n_files, n_ok, bad = R.validate_logs(PILOT_LOG_ROOT)
    print("pilot logs schema-validated: %d/%d" % (n_ok, n_files))
    if bad:
        for p, e in list(bad.items())[:5]:
            print("  FAIL %s: %s" % (os.path.basename(p), e[:2]))

    # ---- four pre-authorization criteria ----
    prorated = PREREG_FULL_PROJECTION * (PILOT_EPISODES / FULL_EPISODES)
    threshold = 3.0 * prorated
    c1 = (total_err == 0)
    c2 = (n_ok == n_files and n_files == PILOT_EPISODES)
    c3 = (total_cost <= threshold)
    c4_free, c4_detail = _rung6_reasoning_free()

    print("\n================ PRE-AUTHORIZATION CRITERIA ================")
    print("(1) pilot errors after retries == 0            : %s  (errors=%d)"
          % ("PASS" if c1 else "FAIL", total_err))
    print("(2) schema: zero diffs on all 140 pilot logs   : %s  (%d/%d ok)"
          % ("PASS" if c2 else "FAIL", n_ok, n_files))
    print("(3) pilot cost ≤ 3× prorated projection        : %s  ($%.5f ≤ $%.5f = 3×$%.5f)"
          % ("PASS" if c3 else "FAIL", total_cost, threshold, prorated))
    print("(4) rung 6 confirmed reasoning-free            : %s  (%s)"
          % ("PASS" if c4_free else "FAIL", c4_detail))

    all_pass = c1 and c2 and c3 and c4_free
    print("\nALL FOUR CRITERIA: %s" % ("PASS -> full run authorized"
                                       if all_pass else "NOT ALL PASS -> stop-and-report"))
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
