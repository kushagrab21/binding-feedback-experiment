"""V3-P4 RAW TALLY — item 2 (counts only; NO conclusions; analysis is P5).

Pure function of the committed master manifest + transcripts (no API calls, no
randomness, no statistics). Prints, verbatim per the work order:
  * the 24-line per-cell episodes/errors table;
  * per (model x tier): advisory success, binding success, Δ (count and pp),
    advisory false-DONEs, step_caps (both modes), escalations (binding);
  * the timestamp-ordering proof — v3-prereg tag time vs the earliest test-log
    episode timestamp;
  * total cost + cumulative v3 spend.

This step draws NO conclusion and runs NO test (McNemar, mediator, etc. are P5).
"""

import glob
import json
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
MASTER = os.path.join(_HERE, "manifests", "full_master.json")
MODEL_ORDER = ["llama-3.1-8b", "qwen-2.5-7b", "claude-3-haiku", "gpt-4o-mini",
               "gemini-2.5-flash-lite", "gpt-4.1"]
TIER_ORDER = ["k1", "k2"]


def main():
    with open(MASTER) as fh:
        m = json.load(fh)
    rows = m["episodes"]

    # index rows by (model, tier, mode)
    cells = {}
    for r in rows:
        cells.setdefault((r["model"], r["tier"], r["mode"]), []).append(r)

    print("=" * 78)
    print("V3-P4 RAW TALLY  (1,296 episodes; D18, temp 0, cap 8; TEST splits k1=60/k2=48)")
    print("counts only — NO conclusions, NO statistics (analysis is P5)")
    print("=" * 78)

    # ---- (1) 24-line per-cell episodes/errors table -------------------------
    print("\n(1) PER-CELL episodes / errors  (24 cells)")
    print("%-40s %8s %7s %8s" % ("cell", "episodes", "errors", "cost$"))
    print("-" * 65)
    tot_ep = tot_err = 0
    tot_cost = 0.0
    for model in MODEL_ORDER:
        for mode in ("advisory", "binding"):
            for tier in TIER_ORDER:
                cr = cells.get((model, tier, mode), [])
                ne = len(cr)
                nerr = sum(1 for r in cr if r.get("status") == "error")
                cost = sum(r.get("cost", 0) for r in cr)
                tot_ep += ne
                tot_err += nerr
                tot_cost += cost
                print("%-40s %8d %7d %8.6f"
                      % ("%s__%s__%s" % (model, mode, tier), ne, nerr, cost))
    print("-" * 65)
    print("%-40s %8d %7d %8.6f" % ("TOTAL (24 cells)", tot_ep, tot_err, tot_cost))

    # ---- (2) per model x tier raw summary -----------------------------------
    print("\n(2) PER MODEL x TIER  (advisory / binding success, Δ, false-DONEs, caps, esc)")
    hdr = ("%-22s %-4s %7s %7s %6s %6s  %8s %8s  %7s %7s  %4s" %
           ("model", "tier", "adv_S", "bnd_S", "Δcnt", "Δpp",
            "adv_fD", "bnd_fD", "adv_cap", "bnd_cap", "esc"))
    print(hdr)
    print("-" * len(hdr))
    for model in MODEL_ORDER:
        for tier in TIER_ORDER:
            adv = cells.get((model, tier, "advisory"), [])
            bnd = cells.get((model, tier, "binding"), [])
            n = len(adv)
            adv_s = sum(1 for r in adv if r.get("success"))
            bnd_s = sum(1 for r in bnd if r.get("success"))
            dcnt = bnd_s - adv_s
            dpp = (100.0 * dcnt / n) if n else 0.0
            adv_fd = sum(1 for r in adv if r.get("false_done"))
            bnd_fd = sum(1 for r in bnd if r.get("false_done"))  # binding: always 0 by defn
            adv_cap = sum(1 for r in adv if r.get("status") == "step_cap")
            bnd_cap = sum(1 for r in bnd if r.get("status") == "step_cap")
            esc = sum(1 for r in bnd if r.get("status") == "escalated")
            print("%-22s %-4s %6s%% %6s%% %+6d %+6.1f  %8d %8d  %7d %7d  %4d"
                  % (model, tier, "%d/%d" % (adv_s, n), "%d/%d" % (bnd_s, n),
                     dcnt, dpp, adv_fd, bnd_fd, adv_cap, bnd_cap, esc))

    # ---- (3) timestamp-ordering proof ---------------------------------------
    print("\n(3) TIMESTAMP-ORDERING PROOF  (registration precedes the test run)")
    tag_ci = subprocess.check_output(
        ["git", "show", "v3-prereg", "--no-patch", "--format=%ci"],
        cwd=_REPO, text=True).strip().splitlines()[-1]
    tag_commit = subprocess.check_output(
        ["git", "rev-list", "-n", "1", "v3-prereg"], cwd=_REPO, text=True).strip()
    # earliest first-event timestamp across ALL 1296 test transcripts
    earliest = None
    earliest_file = None
    for p in glob.glob(os.path.join(_HERE, "logs", "full", "**", "*.jsonl"), recursive=True):
        with open(p) as fh:
            first = fh.readline().strip()
        if not first:
            continue
        ts = json.loads(first).get("timestamp")
        if ts and (earliest is None or ts < earliest):
            earliest = ts
            earliest_file = os.path.relpath(p, _REPO)
    print("    v3-prereg tag commit : %s" % tag_commit)
    print("    v3-prereg tag time   : %s" % tag_ci)
    print("    earliest test-log ts : %s" % earliest)
    print("      (%s)" % earliest_file)
    print("    ORDERING: prereg tag time  <  earliest test-log timestamp  =>  %s"
          % ("PASS (registration precedes data)" if tag_ci < earliest else "FAIL"))
    print("    NOTE: the run-logs git commit (V3-P4.1) is created after this tally, so it")
    print("          also post-dates v3-prereg by construction.")

    # ---- (4) totals ---------------------------------------------------------
    print("\n(4) COST")
    print("    full-run cost (this run) : $%.6f" % m["total_cost_usd"])
    print("    v3 spend to date (calib) : $%.6f" % m["v3_spend_to_date_usd"])
    print("    cumulative v3 spend      : $%.6f" % m["cumulative_v3_spend_usd"])
    print("    stop-gate $12.00: %s   hard cap $20.00: %s"
          % ("OK" if m["cumulative_v3_spend_usd"] < 12 else "TRIPPED",
             "OK" if m["cumulative_v3_spend_usd"] < 20 else "TRIPPED"))
    print("\n(this tally draws no conclusion and registers nothing — P5 does the analysis.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
