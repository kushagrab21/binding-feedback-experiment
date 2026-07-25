"""Phase 5.4 — per-cell aggregates + the 2x2 headline for the full 348-episode run.

Reads the four per-cell manifests ``manifests/full_<model>__<mode>.json`` and each
episode's committed JSONL. Per cell: episodes, success, episodes-with-FAILED-verdict,
false-DONEs (advisory), done_ignored/resubmission_rejected/escalated (binding),
step_cap count, mean steps, tokens, cost. Then the headline 2x2: success rate per cell
and the mode effect (Delta = binding - advisory) for each model, plus the interaction
(Delta_MODEL_A - Delta_MODEL_B). Deeper breakdowns are Phase 6.
"""

import glob
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
MANIFEST_DIR = os.path.join(_HERE, "manifests")

RATES = {  # published USD per 1M tokens (input, output)
    "gpt-4o-mini-2024-07-18": (0.15, 0.60),
    "gpt-4.1": (2.00, 8.00),
}

MODEL_ORDER = ["gpt-4o-mini-2024-07-18", "gpt-4.1"]
MODE_ORDER = ["advisory", "binding"]


def _events(rel_log):
    try:
        with open(os.path.join(_REPO, rel_log), "r", encoding="utf-8") as fh:
            return [json.loads(l) for l in fh if l.strip()]
    except Exception:
        return []


def _had_failed_verdict(ep):
    return any(x["event"] == "check_verdict" and x.get("passed") is False
               for x in _events(ep["log"]))


def _cost(model, tin, tout):
    rin, rout = RATES.get(model, (0.0, 0.0))
    return tin * rin / 1e6 + tout * rout / 1e6


def _load_cells():
    cells = {}
    for p in sorted(glob.glob(os.path.join(MANIFEST_DIR, "full_*.json"))):
        if "master" in os.path.basename(p):
            continue
        with open(p, "r", encoding="utf-8") as fh:
            m = json.load(fh)
        cells[(m["model"], m["mode"])] = m
    return cells


def main():
    cells = _load_cells()
    if not cells:
        print("no full_*.json cell manifests found", file=sys.stderr)
        return 1

    print("=" * 80)
    print("PHASE 5.4 FULL RUN REPORT — 2 models x 2 modes x 87 test tasks (D18 bare-code)")
    any_m = next(iter(cells.values()))
    print("freeze_hash:", any_m.get("task_set_freeze_hash"),
          "| split_sha256:", any_m.get("split_sha256", "")[:16] + "...")
    print("=" * 80)

    rate = {}          # (model, mode) -> success rate
    grand_cost = 0.0
    grand_err = 0

    for model in MODEL_ORDER:
        for mode in MODE_ORDER:
            m = cells.get((model, mode))
            if not m:
                continue
            eps = m["episodes"]
            ok = [e for e in eps if e.get("status") != "error"]
            errs = [e for e in eps if e.get("status") == "error"]
            grand_err += len(errs)

            success = sum(1 for e in ok
                          if (e.get("final_passed") if mode == "advisory"
                              else e.get("status") == "solved"))
            failed_v = sum(1 for e in ok if _had_failed_verdict(e))
            false_done = sum(1 for e in ok
                             if mode == "advisory"
                             and e.get("status") == "model_declared_done"
                             and not e.get("final_passed"))
            done_ign = rej = esc = 0
            for e in ok:
                if mode == "binding":
                    evs = _events(e["log"])
                    done_ign += sum(1 for x in evs if x["event"] == "done_ignored")
                    rej += sum(1 for x in evs if x["event"] == "resubmission_rejected")
                    if e.get("status") == "escalated":
                        esc += 1
            step_cap = sum(1 for e in ok if e.get("status") == "step_cap")
            steps = [e["steps"] for e in ok]
            mean_steps = sum(steps) / len(steps) if steps else 0.0
            tin = sum(e["tokens_in"] for e in ok)
            tout = sum(e["tokens_out"] for e in ok)
            cost = _cost(model, tin, tout)
            grand_cost += cost
            rate[(model, mode)] = success / len(ok) if ok else 0.0

            print()
            print("CELL: %s  x  %s   (resolved: %s)"
                  % (model, mode, m.get("model_resolved")))
            print("  episodes            : %d  (errors: %d)" % (len(eps), len(errs)))
            print("  success             : %d / %d  = %.1f%%  (%s)"
                  % (success, len(ok), 100.0 * rate[(model, mode)],
                     "final_passed" if mode == "advisory" else "status=solved"))
            print("  episodes w/ FAILED  : %d" % failed_v)
            if mode == "advisory":
                print("  false-DONEs         : %d" % false_done)
            else:
                print("  done_ignored/rej/esc: %d / %d / %d" % (done_ign, rej, esc))
            print("  step_cap episodes   : %d" % step_cap)
            print("  mean steps          : %.2f" % mean_steps)
            print("  tokens in / out     : %d / %d" % (tin, tout))
            print("  cost                : $%.4f" % cost)

    print()
    print("-" * 80)
    print("TOTAL cost: $%.4f   |   errors across all cells: %d" % (grand_cost, grand_err))
    print("-" * 80)

    # Headline 2x2 + interaction.
    print()
    print("HEADLINE 2x2 — success rate (%):")
    print("  %-26s %10s %10s   %10s" % ("model", "advisory", "binding", "Δ(bind-adv)"))
    deltas = {}
    for model in MODEL_ORDER:
        adv = rate.get((model, "advisory"))
        bind = rate.get((model, "binding"))
        if adv is None or bind is None:
            continue
        d = bind - adv
        deltas[model] = d
        print("  %-26s %9.1f%% %9.1f%%   %+9.1f%%"
              % (model, 100 * adv, 100 * bind, 100 * d))
    print()
    if len(deltas) == 2:
        a, b = MODEL_ORDER
        inter = deltas[a] - deltas[b]
        print("INTERACTION (the thesis): Δmode(%s) - Δmode(%s) = %+.1f%% - %+.1f%% = %+.1f pp"
              % (a, b, 100 * deltas[a], 100 * deltas[b], 100 * inter))
        print("  (positive => binding helps the weak model MORE than the strong model)")

    return 1 if grand_err else 0


if __name__ == "__main__":
    sys.exit(main())
