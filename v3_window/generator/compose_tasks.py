"""Deterministically generate composed multi-bug tasks for tier k in {1, 2}.

Total bugs per task = k+1 (tier 1 -> 2 bugs, tier 2 -> 3 bugs). For a tier we:

  1. For each frozen v1 seed, enumerate every combination of (k+1) of that
     seed's mutations (from the frozen ``mutations.json``) whose ``old`` snippets
     are PAIRWISE DISJOINT in the seed source (and each occurs exactly once —
     the v1 per-mutation contract). Within a seed the combos are ordered by
     their sorted bug-type tuple (bug_types are unique per seed, so this is a
     total order).
  2. Select round-robin across seeds (seed_id ascending, one emitted task per
     seed per round) for MAXIMUM SEED DIVERSITY, until 70 accepted tasks or the
     supply is exhausted.
  3. Acceptance is checked inline: the composed buggy is run against the seed's
     suite; it must FAIL >= 1 test. A combination whose composition PASSES the
     whole suite means the bugs CANCEL (a mutation-interaction reject) — it is
     logged (with the combo) and skipped, and that seed's turn refills from its
     next combo. A composed mutant that HANGS is likewise rejected.
  4. Each accepted task is emitted to
     ``v3_window/tasks/k{tier}/task_k{tier}_NNN/`` with buggy.py (all k+1
     mutations applied in manifest order), reference.py + tests.py (verbatim
     from the seed), and meta.json (seed, tier k, n_bugs, ALL constituent bug
     types, function/description).

Numbering ``task_k{tier}_001..`` follows emission (round-robin) order. There is
no randomness and no timestamp; two runs are byte-identical. The frozen v1 tree
is only read. Also writes, per tier, ``rejected_combos.json`` (the cancel/hang
combos) alongside the task dirs, for the validator to re-verify and report.

    python3 v3_window/generator/compose_tasks.py            # both tiers
    python3 v3_window/generator/compose_tasks.py --tier 1   # one tier

Infrastructure only: composes buggy variants from the manifest; never solves.
"""

import argparse
import itertools
import json
import shutil
import sys

import suite_runner as sr

TARGET_PER_TIER = 70


def wipe_tier_dir(tier):
    tier_dir = sr.TASKS_DIR / f"k{tier}"
    tier_dir.mkdir(parents=True, exist_ok=True)
    for child in sorted(tier_dir.iterdir()):
        if child.is_dir() and child.name.startswith("task_"):
            shutil.rmtree(child)
    return tier_dir


def valid_combo_queues(tier, by_seed):
    """Return {seed_id: [combo, ...]} of size-(k+1) disjoint combos, each
    seed's list ordered by sorted bug-type tuple. Only seeds with >= 1 valid
    combo appear."""
    size = tier + 1
    queues = {}
    for seed_id in sorted(by_seed):
        seed_src = sr.seed_source(seed_id)
        muts = by_seed[seed_id]
        combos = []
        for combo in itertools.combinations(muts, size):
            if sr.combo_is_disjoint(seed_src, combo):
                combos.append(combo)
        combos.sort(key=lambda c: sr.bug_types_sorted(c))
        if combos:
            queues[seed_id] = combos
    return queues


def generate_tier(tier, by_seed, seeds_meta):
    size = tier + 1
    queues = valid_combo_queues(tier, by_seed)
    total_supply = sum(len(v) for v in queues.values())

    emitted = []      # (seed_id, combo, buggy_src, suite_result)
    rejected = []     # {seed_id, bug_types, reason}

    # Round-robin: each round gives every seed (seed_id order) one turn; a turn
    # pops combos until it emits one accepted task or the seed's queue empties.
    while len(emitted) < TARGET_PER_TIER and any(queues.values()):
        progressed = False
        for seed_id in sorted(queues):
            if len(emitted) >= TARGET_PER_TIER:
                break
            queue = queues[seed_id]
            seed_src = sr.seed_source(seed_id)
            tests_src = sr.seed_tests(seed_id)
            while queue:
                combo = queue.pop(0)
                bts = sr.bug_types_sorted(combo)
                buggy_src, err = sr.compose_buggy(seed_src, combo)
                if buggy_src is None:
                    rejected.append({"seed_id": seed_id, "bug_types": bts,
                                     "reason": err})
                    continue
                res = sr.run_suite_text(buggy_src, tests_src)
                if res["timed_out"]:
                    rejected.append({"seed_id": seed_id, "bug_types": bts,
                                     "reason": "composed buggy HANGS "
                                     f"(exceeded {sr.SUITE_TIMEOUT_S}s)"})
                    continue
                if res["n_failed"] >= 1:
                    emitted.append((seed_id, combo, buggy_src, res))
                    progressed = True
                    break
                # Passes the whole suite -> the bugs cancel.
                rejected.append({"seed_id": seed_id, "bug_types": bts,
                                 "reason": "composition PASSES all "
                                 f"{res['n_total']} tests (bugs cancel)"})
        if not progressed:
            break

    tier_dir = wipe_tier_dir(tier)
    for i, (seed_id, combo, buggy_src, res) in enumerate(emitted, start=1):
        seed_meta = seeds_meta[seed_id]
        task_id = f"task_k{tier}_{i:03d}"
        task_dir = tier_dir / task_id
        task_dir.mkdir(parents=True)
        (task_dir / "reference.py").write_text(sr.seed_source(seed_id))
        (task_dir / "buggy.py").write_text(buggy_src)
        (task_dir / "tests.py").write_text(sr.seed_tests(seed_id))
        meta = {
            "task_id": task_id,
            "seed_name": seed_id,
            "tier": tier,
            "n_bugs": size,
            "bug_types": sr.bug_types_sorted(combo),
            "constituent_mutations": [
                {"bug_type": m["bug_type"], "note": m["note"]}
                for m in sorted(combo, key=lambda m: m["_idx"])
            ],
            "function_name": seed_meta["function_name"],
            "description": seed_meta["description"],
            "difficulty": None,
        }
        (task_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")

    (tier_dir / "rejected_combos.json").write_text(
        json.dumps({"tier": tier, "n_bugs": size, "rejected": rejected},
                   indent=2) + "\n")

    reached = len(emitted)
    print(f"[tier k={tier}, {size} bugs] valid disjoint combos in supply: "
          f"{total_supply}")
    print(f"[tier k={tier}] emitted (accepted) tasks: {reached}"
          + ("" if reached >= TARGET_PER_TIER
             else f"  (supply exhausted before {TARGET_PER_TIER}; "
                  f"achievable count reported, not forced)"))
    print(f"[tier k={tier}] mutation-interaction rejects "
          f"(cancel/hang/not-composable): {len(rejected)}")
    return reached, len(rejected)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", type=int, choices=(1, 2), default=None,
                    help="generate only this tier (default: both)")
    args = ap.parse_args()

    by_seed = sr.load_manifest_by_seed()
    seeds_meta = sr.load_seeds_meta()
    tiers = [args.tier] if args.tier else [1, 2]
    for tier in tiers:
        generate_tier(tier, by_seed, seeds_meta)
    return 0


if __name__ == "__main__":
    sys.exit(main())
