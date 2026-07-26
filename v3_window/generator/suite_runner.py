"""Shared helpers for the V3 composition generator/validator.

This module holds the pieces that both ``compose_tasks.py`` (generation, with
inline mutation-interaction rejection) and ``validate_k_tasks.py`` (independent
audit) must agree on, so the two scripts cannot drift:

  * reading the frozen v1 mutation manifest + seed sources/suites,
  * computing the character span of a mutation's ``old`` snippet,
  * the pairwise-disjoint test over spans,
  * composing a buggy source by applying k+1 mutations in manifest order,
  * running a unittest suite against a candidate source via the ``solution.py``
    copy contract in a temp dir, under the v1 20s hang guard.

Everything here is read-only with respect to the frozen v1 tree
(``phase1_tasks/``): it only READS the manifest, seed sources, and suites. It
never edits a frozen file and never solves a task. No randomness, no timestamps.
"""

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

GEN_DIR = Path(__file__).resolve().parent          # v3_window/generator
V3_DIR = GEN_DIR.parent                             # v3_window
REPO_ROOT = V3_DIR.parent                           # repo root
PHASE1_DIR = REPO_ROOT / "phase1_tasks"
SEEDS_DIR = PHASE1_DIR / "seeds"
SEED_TESTS_DIR = SEEDS_DIR / "tests"
MUTATIONS_PATH = PHASE1_DIR / "generator" / "mutations.json"
SEEDS_JSON_PATH = SEEDS_DIR / "SEEDS.json"

TASKS_DIR = V3_DIR / "tasks"

# Per-suite wall-clock ceiling, identical policy to the frozen v1 validator: a
# composed mutant that spins (e.g. an interaction that produces an infinite
# loop) is REJECTED as "not cleanly killable", not silently killed.
SUITE_TIMEOUT_S = 20

_RAN = re.compile(r"^Ran (\d+) tests? in", re.MULTILINE)
_VLINE = re.compile(r"^(\w+) \(.*\) \.\.\. (ok|FAIL|ERROR)\b")


def die(where, message):
    print(f"{where}: ERROR: {message}", file=sys.stderr)
    sys.exit(1)


# --------------------------------------------------------------------------- #
# Frozen-v1 inputs (read-only)
# --------------------------------------------------------------------------- #

def load_manifest_by_seed():
    """Return {seed_id: [mutation, ...]} preserving each mutation's manifest
    index in ``_idx`` (its position in mutations.json), and each seed's list
    ordered by bug_type (bug_types are unique per seed, so this is a total
    order used for deterministic combination enumeration)."""
    manifest = json.loads(MUTATIONS_PATH.read_text())
    by_seed = {}
    for idx, mut in enumerate(manifest["mutations"]):
        rec = dict(mut)
        rec["_idx"] = idx
        by_seed.setdefault(mut["seed_id"], []).append(rec)
    for seed_id in by_seed:
        by_seed[seed_id].sort(key=lambda m: m["bug_type"])
    return by_seed


def load_seeds_meta():
    """Return {seed_id: {function_name, description, ...}} from SEEDS.json."""
    return {e["seed_id"]: e for e in json.loads(SEEDS_JSON_PATH.read_text())}


def seed_source(seed_id):
    return (SEEDS_DIR / f"{seed_id}.py").read_text()


def seed_tests(seed_id):
    return (SEED_TESTS_DIR / f"test_{seed_id}.py").read_text()


# --------------------------------------------------------------------------- #
# Spans, disjointness, composition
# --------------------------------------------------------------------------- #

def span(src, old):
    """(start, end) of the single occurrence of ``old`` in ``src``.

    ``old`` MUST occur exactly once (the frozen v1 per-mutation contract);
    anything else is a hard error in the frozen inputs.
    """
    n = src.count(old)
    if n != 1:
        die("suite_runner",
            f"'old' snippet occurs {n} times (must be exactly 1): {old!r}")
    start = src.index(old)
    return (start, start + len(old))


def pairwise_disjoint(spans):
    """True iff no two [start, end) spans overlap."""
    ordered = sorted(spans)
    for (a_start, a_end), (b_start, b_end) in zip(ordered, ordered[1:]):
        if a_end > b_start:
            return False
    return True


def combo_is_disjoint(seed_src, combo):
    return pairwise_disjoint([span(seed_src, m["old"]) for m in combo])


def compose_buggy(seed_src, combo):
    """Apply every mutation in ``combo`` to a fresh copy of ``seed_src`` in
    MANIFEST ORDER (ascending ``_idx``). Returns (buggy_src, None) on success,
    or (None, reason) if the composition is not cleanly applicable (a mutation's
    ``old`` no longer occurs exactly once after an earlier edit, or the net
    result is a no-op). Callers pre-filter to disjoint spans, so the guards here
    are defensive — they can only trip on a genuine textual interaction.
    """
    src = seed_src
    for mut in sorted(combo, key=lambda m: m["_idx"]):
        if src.count(mut["old"]) != 1:
            return None, (f"mutation {mut['bug_type']} old-snippet no longer "
                          f"occurs exactly once after prior edits "
                          f"(not composable)")
        src = src.replace(mut["old"], mut["new"])
    if src == seed_src:
        return None, "composition produced no change"
    return src, None


def bug_types_sorted(combo):
    return sorted(m["bug_type"] for m in combo)


# --------------------------------------------------------------------------- #
# Running a suite against a candidate source (solution.py copy contract)
# --------------------------------------------------------------------------- #

def run_suite_text(code_text, tests_text):
    """Write ``code_text`` -> solution.py and ``tests_text`` -> tests.py in a
    fresh temp dir, run ``python -m unittest tests -v`` under the hang guard,
    and return a result dict: ok, n_total, n_failed, first_failing, timed_out.
    Identical mechanics to the frozen v1 validator's run_suite.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "solution.py").write_text(code_text)
        (tmp_path / "tests.py").write_text(tests_text)
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "unittest", "tests", "-v"],
                cwd=tmp_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=SUITE_TIMEOUT_S,
            )
        except subprocess.TimeoutExpired:
            return {"ok": False, "n_total": 0, "n_failed": 0,
                    "first_failing": None, "timed_out": True,
                    "raw": f"(suite exceeded {SUITE_TIMEOUT_S}s timeout)"}

    output = proc.stdout
    ran = _RAN.search(output)
    n_total = int(ran.group(1)) if ran else 0
    n_failed = 0
    first_failing = None
    for line in output.splitlines():
        m = _VLINE.match(line)
        if m and m.group(2) in ("FAIL", "ERROR"):
            n_failed += 1
            if first_failing is None:
                first_failing = m.group(1)
    return {"ok": proc.returncode == 0, "n_total": n_total,
            "n_failed": n_failed, "first_failing": first_failing,
            "timed_out": False, "raw": output}


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
