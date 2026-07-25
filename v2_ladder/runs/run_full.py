"""V2-P4 — THE FULL RUN: 87 test tasks × 7 rungs × 2 modes = 1218 episodes (D18).

Pre-authorized conditionally by V2-P3's four criteria (all PASS). Runs the frozen 87-task
TEST split (never the 10 dev tasks) through the adapter under the D18 bare-code config,
commits transcripts under ``v2_ladder/runs/logs/full/<rung-slug>__<mode>/task_NNN.jsonl``
with one manifest per cell (14) + a master, schema-validates every log, prints per-cell
episode/error counts, the total episode count (must be 1218), and total v2 spend.

Robustness mirrors v1 P5.4: client 429/5xx backoff + episode-level retry + up to 2 extra
passes over any errored episode. Final state must be 0 errors, else exit non-zero for a
stop-and-report. Rungs run concurrently (independent models) to bound wall-clock.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "adapter"))
import runner as R  # noqa: E402
import client as C  # noqa: E402

FULL_LOG_ROOT = os.path.join(_HERE, "logs", "full")
MANIFEST_DIR = os.path.join(_HERE, "manifests")
EXPECTED_EPISODES = 1218


def main():
    test = R.load_tasks("test")
    assert len(test) == 87, "expected 87 test tasks, got %d" % len(test)
    print("FULL RUN: %d test tasks × %d rungs × 2 modes = %d episodes"
          % (len(test), len(C.RUNGS), len(test) * len(C.RUNGS) * 2), file=sys.stderr)

    rows_by_cell, master = R.run_cells(test, FULL_LOG_ROOT, MANIFEST_DIR, "full",
                                       parallel_rungs=True)

    # ---- per-cell episode/error counts (14 lines), rung order ----
    print("\n================ FULL-RUN PER-CELL COUNTS ================")
    total_eps = 0
    total_err = 0
    for rung in C.RUNGS:
        for mode in ("advisory", "binding"):
            cell = "%s__%s" % (rung["slug"], mode)
            rows = rows_by_cell[cell]
            n = len(rows)
            e = sum(1 for r in rows if r.get("status") == "error")
            succ = sum(1 for r in rows if r.get("success"))
            total_eps += n
            total_err += e
            print("%-38s episodes=%3d errors=%d success=%d/%d"
                  % (cell, n, e, succ, n))

    print("\ntotal episodes: %d (expected %d)   total errors: %d   total v2 full-run cost: $%.5f"
          % (total_eps, EXPECTED_EPISODES, total_err, master["total_cost_usd"]))

    # ---- schema validation over all full-run logs ----
    n_files, n_ok, bad = R.validate_logs(FULL_LOG_ROOT)
    print("full-run logs schema-validated: %d/%d" % (n_ok, n_files))
    if bad:
        for p, e in list(bad.items())[:5]:
            print("  FAIL %s: %s" % (os.path.basename(p), e[:2]))

    ok = (total_err == 0 and total_eps == EXPECTED_EPISODES
          and n_ok == n_files == EXPECTED_EPISODES)
    if ok:
        print("\nFULL RUN COMPLETE: %d episodes, 0 errors, all logs schema-clean." % total_eps)
    else:
        print("\nSTOP-AND-REPORT: errors=%d episodes=%d schema_ok=%d/%d"
              % (total_err, total_eps, n_ok, n_files))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
