"""Report bug-type coverage across the Phase 1 seed corpus.

Reads SEEDS.json and prints, for each of the eight final bug types (the closed
vocabulary fixed in TAXONOMY.md), how many seeds list it as a candidate and which
seeds those are, followed by the total number of (seed, type) pairs.

Coverage invariants (exit non-zero if either is violated):
  - every bug type is a candidate for at least MIN_SEEDS_PER_TYPE seeds, so the
    generator can draw enough distinct tasks of each type; and
  - every seed lists at least MIN_TYPES_PER_SEED candidate types, so no seed is a
    near-dead-end for generation.

Run from anywhere:

    python phase1_tasks/generator/coverage_report.py
"""

import json
import sys
from pathlib import Path

MANIFEST = Path(__file__).resolve().parent.parent / "seeds" / "SEEDS.json"

# The final 8-type taxonomy, in canonical order (see TAXONOMY.md). This is the
# closed vocabulary; any candidate type outside it is a coverage error.
BUG_TYPES = [
    "off-by-one",
    "wrong-comparison",
    "wrong-operator",
    "inverted-condition",
    "wrong-variable",
    "missing-edge-case",
    "wrong-return",
    "input-mutation",
]

MIN_SEEDS_PER_TYPE = 3
MIN_TYPES_PER_SEED = 2


def main():
    try:
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print("FAIL: SEEDS.json not found")
        return 1
    except json.JSONDecodeError as exc:
        print(f"FAIL: SEEDS.json is not valid JSON: {exc}")
        return 1

    allowed = set(BUG_TYPES)
    # Map each bug type -> sorted list of seed ids that list it.
    seeds_by_type = {bt: [] for bt in BUG_TYPES}
    total_pairs = 0
    problems = []

    for entry in data:
        seed_id = entry.get("seed_id", "<unknown>")
        types = entry.get("candidate_bug_types", []) or []
        total_pairs += len(types)

        if len(types) < MIN_TYPES_PER_SEED:
            problems.append(
                f"{seed_id}: only {len(types)} candidate type(s); "
                f"need at least {MIN_TYPES_PER_SEED}")

        for bt in types:
            if bt not in allowed:
                problems.append(
                    f"{seed_id}: candidate type '{bt}' is outside the final "
                    f"8-type taxonomy")
                continue
            seeds_by_type[bt].append(seed_id)

    # Per-type coverage lines (canonical order).
    for bt in BUG_TYPES:
        ids = sorted(seeds_by_type[bt])
        print(f"{bt}: {len(ids)} seeds {ids}")
        if len(ids) < MIN_SEEDS_PER_TYPE:
            problems.append(
                f"type '{bt}': covered by only {len(ids)} seed(s); "
                f"need at least {MIN_SEEDS_PER_TYPE}")

    print(f"total (seed, type) pairs: {total_pairs}")

    if problems:
        for p in problems:
            print("FAIL: " + p)
        print(f"RESULT: FAILED ({len(problems)} problem(s))")
        return 1
    print(f"RESULT: OK — all {len(BUG_TYPES)} types >= {MIN_SEEDS_PER_TYPE} seeds, "
          f"all seeds >= {MIN_TYPES_PER_SEED} types")
    return 0


if __name__ == "__main__":
    sys.exit(main())
