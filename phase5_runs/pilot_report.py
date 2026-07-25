"""Phase 5.1 — per-cell aggregates for the dev-set pilot.

Reads ``phase5_runs/manifests/pilot_manifest.json`` (episode rows) and each episode's
committed JSONL (for event counts), then prints one block per cell (model x mode):

    episodes, success count, false-DONE count (advisory: model_declared_done with
    final_passed=False), done_ignored / resubmission_rejected / escalated counts,
    mean steps, total tokens in/out, cost at published rates, and a projected
    full-run cost (per-episode averages scaled x 87 test tasks per cell).

Success is mode-specific: advisory success = final verdict passed (final_passed True);
binding success = status == "solved".

It also prints the D13 assessment: per model, how many of the ten dev tasks were failed
at least once in either arm (the signal question the pilot exists to answer).
"""

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
MANIFEST_PATH = os.path.join(_HERE, "manifests", "pilot_manifest.json")

# Published USD rates per 1M tokens (input, output), keyed by requested model id.
RATES = {
    "gpt-4o-mini-2024-07-18": (0.15, 0.60),
    "gpt-4.1": (2.00, 8.00),
}

TEST_TASKS_PER_CELL = 87   # full-run projection target (the 87 frozen test tasks)
DEV_TASKS_PER_CELL = 10


def _events(rel_log):
    path = os.path.join(_REPO, rel_log)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return [json.loads(l) for l in fh if l.strip()]
    except Exception:
        return []


def _is_success(ep):
    if ep["mode"] == "advisory":
        return bool(ep.get("final_passed"))
    return ep.get("status") == "solved"


def _cost(model, tin, tout):
    rin, rout = RATES.get(model, (0.0, 0.0))
    return tin * rin / 1e6 + tout * rout / 1e6


def main():
    with open(MANIFEST_PATH, "r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    episodes = manifest["episodes"]
    models = manifest["models"]
    modes = manifest["modes"]

    print("=" * 78)
    print("PHASE 5.1 DEV-SET PILOT REPORT")
    print("date:", manifest.get("date"))
    print("freeze_hash:", manifest.get("task_set_freeze_hash"))
    print("=" * 78)

    grand_cost = 0.0
    grand_proj = 0.0

    for model in models:
        for mode in modes:
            cell = [e for e in episodes if e["model"] == model and e["mode"] == mode]
            if not cell:
                continue
            errors = [e for e in cell if e.get("status") == "error"]
            ok = [e for e in cell if e.get("status") != "error"]

            n = len(cell)
            success = sum(1 for e in ok if _is_success(e))
            false_done = sum(
                1 for e in ok
                if mode == "advisory"
                and e.get("status") == "model_declared_done"
                and not e.get("final_passed")
            )
            done_ignored = rejected = escalated = 0
            for e in ok:
                if mode == "binding":
                    evs = _events(e["log"])
                    done_ignored += sum(1 for x in evs if x["event"] == "done_ignored")
                    rejected += sum(1 for x in evs if x["event"] == "resubmission_rejected")
                    if e.get("status") == "escalated":
                        escalated += 1
            steps = [e["steps"] for e in ok]
            mean_steps = sum(steps) / len(steps) if steps else 0.0
            tin = sum(e["tokens_in"] for e in ok)
            tout = sum(e["tokens_out"] for e in ok)
            cost = _cost(model, tin, tout)
            # Full-run projection: per-episode average cost x 87 test tasks.
            per_ep_cost = cost / len(ok) if ok else 0.0
            proj = per_ep_cost * TEST_TASKS_PER_CELL
            grand_cost += cost
            grand_proj += proj

            print()
            print("CELL: %s  x  %s" % (model, mode))
            print("  episodes            : %d  (errors: %d)" % (n, len(errors)))
            print("  success             : %d / %d  (%s)"
                  % (success, len(ok),
                     "final_passed" if mode == "advisory" else "status=solved"))
            if mode == "advisory":
                print("  false-DONE          : %d  (declared_done w/ final_passed=False)"
                      % false_done)
            else:
                print("  done_ignored events : %d" % done_ignored)
                print("  resubmission_reject : %d" % rejected)
                print("  escalated episodes  : %d" % escalated)
            print("  mean steps          : %.2f" % mean_steps)
            print("  tokens in / out     : %d / %d" % (tin, tout))
            print("  cost (pilot cell)   : $%.4f" % cost)
            print("  projected full-run  : $%.4f   (avg $%.5f/ep x %d)"
                  % (proj, per_ep_cost, TEST_TASKS_PER_CELL))

    print()
    print("-" * 78)
    print("PILOT TOTAL cost      : $%.4f  (40 episodes)" % grand_cost)
    print("PROJECTED FULL-RUN    : $%.4f  (348 episodes = 2 models x 2 modes x 87)"
          % grand_proj)
    print("-" * 78)

    # D13 assessment: per model, dev tasks failed at least once in EITHER arm.
    print()
    print("D13 ASSESSMENT — dev tasks failed at least once (either arm), per model:")
    for model in models:
        failed_tasks = set()
        for e in episodes:
            if e["model"] != model or e.get("status") == "error":
                continue
            if not _is_success(e):
                failed_tasks.add(e["task_id"])
        label = manifest.get("model_labels", {}).get(model, "")
        print("  %-24s %-24s : %d / %d dev tasks failed >=1x  %s"
              % (model, "(%s)" % label if label else "",
                 len(failed_tasks), DEV_TASKS_PER_CELL,
                 sorted(failed_tasks) if failed_tasks else "(all one-shot)"))

    any_error = any(e.get("status") == "error" for e in episodes)
    return 1 if any_error else 0


if __name__ == "__main__":
    sys.exit(main())
