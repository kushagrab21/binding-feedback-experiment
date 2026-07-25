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


def _had_failed_verdict(ep):
    """True iff any check_verdict in the episode returned passed=False (the deeper
    'model submitted code the checker rejected and had to iterate' signal)."""
    return any(
        x["event"] == "check_verdict" and x.get("passed") is False
        for x in _events(ep["log"])
    )


def _manifest_path_from_argv(argv):
    if "--manifest" in argv:
        i = argv.index("--manifest")
        if i + 1 < len(argv):
            return os.path.abspath(argv[i + 1])
    return MANIFEST_PATH


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    manifest_path = _manifest_path_from_argv(argv)
    with open(manifest_path, "r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    episodes = manifest["episodes"]
    models = manifest["models"]
    modes = manifest["modes"]

    print("=" * 78)
    print("%s DEV-SET PILOT REPORT" % manifest.get("phase", "PHASE 5").upper())
    print("date:", manifest.get("date"), "| show_description:",
          manifest.get("show_description"))
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
            failed_verdict_eps = sum(1 for e in ok if _had_failed_verdict(e))
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
            print("  episodes w/ FAILED  : %d  (>=1 check_verdict passed=False mid-episode)"
                  % failed_verdict_eps)
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

    n_eps = len(episodes)
    full_run = len(models) * len(modes) * TEST_TASKS_PER_CELL
    print()
    print("-" * 78)
    print("PILOT TOTAL cost      : $%.4f  (%d episodes)" % (grand_cost, n_eps))
    print("PROJECTED FULL-RUN    : $%.4f  (%d episodes = %d models x %d modes x %d)"
          % (grand_proj, full_run, len(models), len(modes), TEST_TASKS_PER_CELL))
    print("-" * 78)

    # D13 assessment: per model, dev tasks that (a) finally failed, and (b) had any
    # FAILED verdict mid-episode (the signal — a mid-episode failure that gets repaired
    # is a good outcome here). The decision rule keys on (b): >=3 -> authorize full run.
    print()
    print("D13 ASSESSMENT — per model, dev tasks with a failure signal (either arm):")
    for model in models:
        final_fail = set()
        any_failed = set()
        for e in episodes:
            if e["model"] != model or e.get("status") == "error":
                continue
            if not _is_success(e):
                final_fail.add(e["task_id"])
            if _had_failed_verdict(e):
                any_failed.add(e["task_id"])
        label = manifest.get("model_labels", {}).get(model, "")
        print("  %-24s %-26s" % (model, "(%s)" % label if label else ""))
        print("      final-failed tasks        : %d / %d  %s"
              % (len(final_fail), DEV_TASKS_PER_CELL,
                 sorted(final_fail) if final_fail else "(none)"))
        print("      any-FAILED-verdict tasks  : %d / %d  %s   <- decision-rule metric"
              % (len(any_failed), DEV_TASKS_PER_CELL,
                 sorted(any_failed) if any_failed else "(none — pure one-shot)"))

    any_error = any(e.get("status") == "error" for e in episodes)
    return 1 if any_error else 0


if __name__ == "__main__":
    sys.exit(main())
