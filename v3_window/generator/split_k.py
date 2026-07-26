"""Deterministic dev/test split per composition tier.

Rule (documented, no randomness):
  * Take the emitted tasks for the tier, ordered by task_id (== emission /
    round-robin order, since numbering follows emission).
  * If more than 70 tasks exist, DROP the task_ids beyond the first 70 before
    splitting (defensive; the generator already caps at 70).
  * dev  = the first 10 task_ids.
  * test = the remaining task_ids.

Because generation emits round-robin (round 1 gives one task per contributing
seed, in seed_id order), the first 10 task_ids are 10 DISTINCT seeds by
construction — a maximally-diverse dev set with no extra machinery. The canonical
full tier (70 tasks) yields 10 dev / 60 test; a tier whose supply is exhausted
below 70 yields 10 dev / (N-10) test, reported honestly.

Writes ``v3_window/tasks/k{tier}/split.json`` with keys tier, rule, dev, test.

    python3 v3_window/generator/split_k.py            # both tiers
    python3 v3_window/generator/split_k.py --tier 1
"""

import argparse
import json
import sys

import suite_runner as sr

DEV_N = 10
CAP = 70
RULE = ("emission(round-robin) order by task_id; drop task_ids beyond the "
        "first 70; dev = first 10 task_ids (10 distinct seeds by construction), "
        "test = the remainder")


def split_tier(tier):
    tier_dir = sr.TASKS_DIR / f"k{tier}"
    task_ids = sorted(d.name for d in tier_dir.iterdir()
                      if d.is_dir() and d.name.startswith("task_"))
    kept = task_ids[:CAP]                       # drop extras beyond 70
    dev = kept[:DEV_N]
    test = kept[DEV_N:]

    assert len(dev) == DEV_N, f"tier k={tier}: need >= {DEV_N} tasks for dev"
    assert set(dev).isdisjoint(test), "dev/test overlap"
    assert set(dev) | set(test) == set(kept), "dev+test != kept"

    dev_seeds = []
    for tid in dev:
        meta = json.loads((tier_dir / tid / "meta.json").read_text())
        dev_seeds.append(meta["seed_name"])
    assert len(set(dev_seeds)) == DEV_N, \
        f"tier k={tier}: dev seeds not distinct: {dev_seeds}"

    payload = {"tier": tier, "rule": RULE, "dev": dev, "test": test}
    (tier_dir / "split.json").write_text(json.dumps(payload, indent=2) + "\n")
    dropped = len(task_ids) - len(kept)
    print(f"[tier k={tier}] total emitted={len(task_ids)} kept={len(kept)} "
          f"dropped_beyond_70={dropped} -> dev={len(dev)} test={len(test)} "
          f"(dev seeds distinct: {len(set(dev_seeds))})")
    return payload


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", type=int, choices=(1, 2), default=None)
    args = ap.parse_args()
    for tier in ([args.tier] if args.tier else [1, 2]):
        split_tier(tier)
    return 0


if __name__ == "__main__":
    sys.exit(main())
