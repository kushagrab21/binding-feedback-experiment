"""V3 calibration — deterministic report over ``manifest.json`` + transcripts.

Pure function of committed artifacts (no API calls, no randomness): reads the
manifest's per-episode rows and, for the two binding-only event counts
(``done_ignored`` / ``resubmission_rejected``), the transcripts themselves. Prints:

  * a per (model x tier x mode) table: success n/10, false-DONEs (advisory only),
    step_caps, escalations (binding), done_ignored + resubmission_rejected (binding),
    mean steps, tokens, cost;
  * (a) BAND CHECK — per tier, each of the four WINDOW models' advisory success rate,
    marked IN/OUT of the 40-70% band, with a one-line summary per tier;
  * (b) gpt-4.1 WATCH — the ceiling probe's advisory false-DONE count and step_caps
    per tier, reported with NO design reaction.

REPORT ONLY. This step registers no prediction and reacts to no number; the ordering
caveat (P3's prediction (vii) is registered AFTER this 10-task glimpse, and its
confirmatory test runs on the untouched TEST splits) is printed verbatim.
"""

import json
import os
import sys

import cal_common as G

BAND_LO, BAND_HI = 0.40, 0.70


def _count_events(log_rel, kinds):
    """Count occurrences of each event kind in a transcript. Returns dict kind->n."""
    counts = {k: 0 for k in kinds}
    path = os.path.join(G.repo_root(), log_rel)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                ev = json.loads(line).get("event")
                if ev in counts:
                    counts[ev] += 1
    except FileNotFoundError:
        pass
    return counts


def _mean(xs):
    return (sum(xs) / len(xs)) if xs else 0.0


def main():
    with open(G.MANIFEST_PATH, "r", encoding="utf-8") as fh:
        man = json.load(fh)
    rows = man["episodes"]

    # index rows by (model, tier, mode)
    cells = {}
    for r in rows:
        cells.setdefault((r["model"], r["tier"], r["mode"]), []).append(r)

    print("V3-P2 CALIBRATION REPORT  (dev tasks only; 10 per tier; D18, temp 0, cap 8)")
    print("presentation=%s  config=%s" % (man["presentation"], man["config"]))
    print("tiers: k1 freeze %s… (2 bugs) | k2 freeze %s… (3 bugs)"
          % (man["tiers"]["k1"]["freeze_hash"][:12], man["tiers"]["k2"]["freeze_hash"][:12]))
    print()

    hdr = ("%-22s %-4s %-9s %5s %6s %6s %6s %6s %6s %7s %8s %9s" %
           ("model", "tier", "mode", "succ", "fDONE", "cap", "esc", "d_ign", "resub",
            "mean_st", "tokens", "cost$"))
    print(hdr)
    print("-" * len(hdr))

    for model in G.MODEL_SLUGS:
        for tier in G.TIER_KEYS:
            for mode in G.MODES:
                cr = cells.get((model, tier, mode), [])
                n = len(cr)
                succ = sum(1 for r in cr if r.get("success"))
                fdone = sum(1 for r in cr if r.get("false_done"))
                caps = sum(1 for r in cr if r.get("status") == "step_cap")
                esc = sum(1 for r in cr if r.get("status") == "escalated")
                d_ign = resub = 0
                if mode == "binding":
                    for r in cr:
                        c = _count_events(r.get("log", ""),
                                          ("done_ignored", "resubmission_rejected"))
                        d_ign += c["done_ignored"]
                        resub += c["resubmission_rejected"]
                mean_st = _mean([r.get("steps", 0) for r in cr])
                toks = sum(r.get("tokens_in", 0) + r.get("tokens_out", 0) for r in cr)
                cost = sum(r.get("cost", 0) for r in cr)
                fdone_s = str(fdone) if mode == "advisory" else "-"
                esc_s = str(esc) if mode == "binding" else "-"
                dign_s = str(d_ign) if mode == "binding" else "-"
                resub_s = str(resub) if mode == "binding" else "-"
                print("%-22s %-4s %-9s %5s %6s %6d %6s %6s %6s %7.1f %8d %9.6f" %
                      (model, tier, mode, "%d/%d" % (succ, n), fdone_s, caps,
                       esc_s, dign_s, resub_s, mean_st, toks, cost))

    # --- (a) BAND CHECK ------------------------------------------------------
    print("\n(a) BAND CHECK — window models' ADVISORY success vs the 40–70%% band")
    for tier in G.TIER_KEYS:
        in_band = 0
        for model in G.WINDOW_MODELS:
            cr = cells.get((model, tier, "advisory"), [])
            n = len(cr)
            succ = sum(1 for r in cr if r.get("success"))
            rate = (succ / n) if n else 0.0
            mark = "IN " if BAND_LO <= rate <= BAND_HI else "OUT"
            if mark == "IN ":
                in_band += 1
            print("    %-4s %-22s advisory %d/%d = %5.1f%%  [%s band]"
                  % (tier, model, succ, n, 100 * rate, mark))
        print("    %-4s SUMMARY: %d/4 window models land inside the 40–70%% band."
              % (tier, in_band))

    # --- (b) gpt-4.1 WATCH ---------------------------------------------------
    print("\n(b) gpt-4.1 WATCH — ceiling probe (advisory), NO design reaction")
    for tier in G.TIER_KEYS:
        cr = cells.get((G.CEILING_PROBE, tier, "advisory"), [])
        n = len(cr)
        succ = sum(1 for r in cr if r.get("success"))
        fdone = sum(1 for r in cr if r.get("false_done"))
        caps = sum(1 for r in cr if r.get("status") == "step_cap")
        print("    %-4s gpt-4.1 advisory: success %d/%d  false-DONEs %d  step_caps %d"
              % (tier, succ, n, fdone, caps))

    # --- ordering caveat (verbatim, not buried) ------------------------------
    print("\nORDERING CAVEAT: P3's prediction (vii) will be REGISTERED after this")
    print("10-task-per-tier calibration glimpse; the confirmatory test runs on the")
    print("UNTOUCHED test splits. This report reacts to no number and registers nothing.")

    print("\ntotals: episodes=%d errors=%d cost=$%.6f  (cumulative v3 spend=$%.6f)"
          % (man["n_episodes"], man["n_errors"], man["total_cost_usd"], man["total_cost_usd"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
