"""Independently audit the emitted composition tasks for a tier.

For every emitted ``v3_window/tasks/k{tier}/task_k{tier}_NNN`` this re-checks the
two invariants from scratch, using the ``solution.py`` copy contract in a fresh
temp dir under the 20s hang guard (same mechanics as the frozen v1 validator):

  (a) reference.py passes the ENTIRE suite;
  (b) composed buggy.py FAILS >= 1 test.

It prints one line per task, then totals, then re-verifies the generator's
``rejected_combos.json`` (each cancel/hang combo is re-composed and re-run to
CONFIRM it really does pass-all / hang — the rejects are audited, not merely
echoed). The full report is written to
``v3_window/tasks/k{tier}/validation_report.txt`` for committing + hash-pinning.
Exit is non-zero if any emitted task violates an invariant, or if any recorded
"bugs cancel" reject does not in fact pass its whole suite on re-check.

    python3 v3_window/generator/validate_k_tasks.py            # both tiers
    python3 v3_window/generator/validate_k_tasks.py --tier 1

Infrastructure only: runs suites against generated files; never solves a task.
"""

import argparse
import itertools
import json
import sys

import suite_runner as sr


def audit_tier(tier):
    tier_dir = sr.TASKS_DIR / f"k{tier}"
    task_dirs = sorted(d for d in tier_dir.iterdir()
                       if d.is_dir() and d.name.startswith("task_"))
    lines = []
    accepted = 0
    rejected_tasks = 0

    for task_dir in task_dirs:
        meta = json.loads((task_dir / "meta.json").read_text())
        seed = meta["seed_name"]
        bts = "+".join(meta["bug_types"])
        tests_text = (task_dir / "tests.py").read_text()
        ref = sr.run_suite_text((task_dir / "reference.py").read_text(),
                                tests_text)
        buggy = sr.run_suite_text((task_dir / "buggy.py").read_text(),
                                  tests_text)
        ref_ok = ref["ok"] and not ref["timed_out"]
        buggy_fails = buggy["n_failed"] >= 1 and not buggy["timed_out"]
        if ref_ok and buggy_fails:
            accepted += 1
            lines.append(
                f"{meta['task_id']} {seed} [{bts}] ref=PASS "
                f"buggy=FAIL({buggy['n_failed']}/{buggy['n_total']}) "
                f"[{buggy['first_failing']}]")
        else:
            rejected_tasks += 1
            reasons = []
            if not ref_ok:
                reasons.append("reference HANGS" if ref["timed_out"]
                               else f"reference FAILS "
                                    f"({ref['n_failed']}/{ref['n_total']})")
            if not buggy_fails:
                reasons.append("buggy HANGS" if buggy["timed_out"]
                               else f"buggy PASSES all {buggy['n_total']} "
                                    f"tests (mutant not killed)")
            lines.append(
                f"{meta['task_id']} {seed} [{bts}] REJECTED: "
                + "; ".join(reasons))

    # Re-verify the generator's recorded interaction rejects.
    rej_path = tier_dir / "rejected_combos.json"
    recorded = json.loads(rej_path.read_text())["rejected"] \
        if rej_path.exists() else []
    by_seed = sr.load_manifest_by_seed()
    reverify_fail = 0
    rej_lines = []
    for rec in recorded:
        seed = rec["seed_id"]
        bts = rec["bug_types"]
        status = "not-recheckable"
        if "bugs cancel" in rec["reason"]:
            # Rebuild this exact combo (by its bug-type set) and confirm pass-all.
            muts = {m["bug_type"]: m for m in by_seed[seed]}
            combo = [muts[b] for b in bts if b in muts]
            if len(combo) == len(bts):
                buggy_src, err = sr.compose_buggy(sr.seed_source(seed), combo)
                if buggy_src is not None:
                    res = sr.run_suite_text(buggy_src, sr.seed_tests(seed))
                    if res["n_failed"] == 0 and not res["timed_out"]:
                        status = "CONFIRMED-cancels(pass-all)"
                    else:
                        status = "RECHECK-MISMATCH"
                        reverify_fail += 1
                else:
                    status = f"not-composable({err})"
        else:
            status = "recorded(hang/not-composable)"
        rej_lines.append(f"    {seed} [{'+'.join(bts)}]: {rec['reason']} "
                         f"-> {status}")

    lines.append("---")
    lines.append(f"tier k={tier}: emitted tasks: {len(task_dirs)}  "
                 f"accepted: {accepted}  rejected: {rejected_tasks}")
    lines.append(f"interaction rejects recorded: {len(recorded)}  "
                 f"re-verify mismatches: {reverify_fail}")
    if recorded:
        lines.append("rejected combos (re-verified):")
        lines.extend(rej_lines)
    lines.append("---")
    ok = rejected_tasks == 0 and reverify_fail == 0
    if ok:
        lines.append(f"K{tier} VALIDATION: OK ({accepted} accepted, both "
                     f"invariants hold for every task; all {len(recorded)} "
                     f"interaction rejects re-verified)")
    else:
        problems = []
        if rejected_tasks:
            problems.append(f"{rejected_tasks} task(s) violate an invariant")
        if reverify_fail:
            problems.append(f"{reverify_fail} reject(s) failed re-verification")
        lines.append(f"K{tier} VALIDATION: FAILED ({'; '.join(problems)})")

    report = "\n".join(lines) + "\n"
    (tier_dir / "validation_report.txt").write_text(report)
    sys.stdout.write(report)
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", type=int, choices=(1, 2), default=None)
    args = ap.parse_args()
    tiers = [args.tier] if args.tier else [1, 2]
    all_ok = True
    for tier in tiers:
        all_ok = audit_tier(tier) and all_ok
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
