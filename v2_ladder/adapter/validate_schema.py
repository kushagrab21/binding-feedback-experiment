"""V2 ladder — episode-log schema validator (calibrated on the frozen v1 logs).

The v1 harnesses write one JSONL line per event. This validator encodes the v1 event
schema exactly — the event set and the required fields/types per event — so that a v2
episode log written through the same frozen harnesses (only the *client* changed) is
verifiably the same shape as a v1 log. The schema was calibrated by a census of all 348
committed v1 full-run logs (``phase5_runs/logs/full/``): the required-field sets below
are precisely the fields present in **every** instance of each event there, and the two
binding-only events (``resubmission_rejected``, ``done_ignored``) are added from the
frozen Phase-4 harness (they don't happen to occur in the v1 full logs but are legal).

"Zero diffs" acceptance: run ``--calibrate`` over 20 sampled committed v1 logs; every
one must validate with an empty error list.

Usage::

    python3 validate_schema.py <path-or-dir> [<path-or-dir> ...]
    python3 validate_schema.py --calibrate        # sample 20 v1 logs, require 0 errors
    python3 validate_schema.py --calibrate --n 20 # explicit sample size

Exit code 0 iff every file validated with zero errors.
"""

import glob
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))

# Base fields on EVERY event (present in all v1 events).
_BASE = {"event": str, "step": int, "timestamp": str, "model": str}

# Per-event ADDITIONAL required fields (on top of _BASE), with types.
# bool is a subclass of int in Python, so integer fields are checked to be non-bool.
_EVENTS = {
    "system_prompt":        {"content": str},
    "user_message":         {"content": str},
    "model_response":       {"content": str, "tokens_in": int, "tokens_out": int},
    "check_verdict":        {"passed": bool, "failures": list, "content": str},
    "resubmission_rejected": {"consecutive_identical": int, "content": str},  # binding-only
    "done_ignored":         {"content": str},                                # binding-only
    "episode_end": {
        "status": str, "final_passed": bool, "steps": int,
        "tokens_in": int, "tokens_out": int,
        "episode_id": str, "task_id": str, "mode": str,
    },
}

_VALID_STATUSES = {"model_declared_done", "step_cap", "solved", "escalated"}
_VALID_MODES = {"advisory", "binding"}


def _type_ok(value, typ):
    if typ is int:
        # exclude bool (a bool is an int subclass) for integer fields
        return isinstance(value, int) and not isinstance(value, bool)
    if typ is bool:
        return isinstance(value, bool)
    return isinstance(value, typ)


def validate_file(path):
    """Return a list of error strings for one episode-log file ([] == valid)."""
    errors = []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw_lines = fh.readlines()
    except OSError as exc:
        return ["cannot read file: %s" % exc]

    records = []
    for i, line in enumerate(raw_lines, 1):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append("line %d: invalid JSON (%s)" % (i, exc))
            continue
        if not isinstance(rec, dict):
            errors.append("line %d: event is not a JSON object" % i)
            continue
        records.append((i, rec))

    if not records:
        return errors + ["no events in file"]

    for i, rec in records:
        ev = rec.get("event")
        # base fields
        for k, typ in _BASE.items():
            if k not in rec:
                errors.append("line %d [%s]: missing base field '%s'" % (i, ev, k))
            elif not _type_ok(rec[k], typ):
                errors.append("line %d [%s]: base field '%s' wrong type (got %s)"
                              % (i, ev, k, type(rec[k]).__name__))
        if ev not in _EVENTS:
            errors.append("line %d: unknown event type %r" % (i, ev))
            continue
        for k, typ in _EVENTS[ev].items():
            if k not in rec:
                errors.append("line %d [%s]: missing required field '%s'" % (i, ev, k))
            elif not _type_ok(rec[k], typ):
                errors.append("line %d [%s]: field '%s' wrong type (got %s, want %s)"
                              % (i, ev, k, type(rec[k]).__name__, typ.__name__))
        if rec.get("step") is not None and _type_ok(rec.get("step"), int) and rec["step"] < 0:
            errors.append("line %d [%s]: negative step %d" % (i, ev, rec["step"]))
        # failures must be a list of objects
        if ev == "check_verdict" and isinstance(rec.get("failures"), list):
            for j, f in enumerate(rec["failures"]):
                if not isinstance(f, dict):
                    errors.append("line %d [check_verdict]: failures[%d] not an object" % (i, j))
        # episode_end value-domain checks
        if ev == "episode_end":
            if rec.get("status") not in _VALID_STATUSES:
                errors.append("line %d [episode_end]: status %r not in %s"
                              % (i, rec.get("status"), sorted(_VALID_STATUSES)))
            if rec.get("mode") not in _VALID_MODES:
                errors.append("line %d [episode_end]: mode %r not in %s"
                              % (i, rec.get("mode"), sorted(_VALID_MODES)))

    # structural invariants (hold for every v1 log)
    first_ev = records[0][1].get("event")
    last_ev = records[-1][1].get("event")
    if first_ev != "system_prompt":
        errors.append("first event is %r, expected 'system_prompt'" % first_ev)
    if records[0][1].get("step") != 0:
        errors.append("first event step is %r, expected 0" % records[0][1].get("step"))
    if last_ev != "episode_end":
        errors.append("last event is %r, expected 'episode_end'" % last_ev)
    n_sys = sum(1 for _, r in records if r.get("event") == "system_prompt")
    n_end = sum(1 for _, r in records if r.get("event") == "episode_end")
    if n_sys != 1:
        errors.append("expected exactly 1 system_prompt, found %d" % n_sys)
    if n_end != 1:
        errors.append("expected exactly 1 episode_end, found %d" % n_end)
    return errors


def _iter_paths(args):
    for a in args:
        if os.path.isdir(a):
            for p in sorted(glob.glob(os.path.join(a, "**", "*.jsonl"), recursive=True)):
                yield p
        else:
            yield a


def validate_many(paths):
    """Validate a list of files; return (n_files, n_ok, {path: errors})."""
    results = {}
    n_ok = 0
    for p in paths:
        errs = validate_file(p)
        results[p] = errs
        if not errs:
            n_ok += 1
    return len(results), n_ok, results


def _calibrate(n=20):
    """Sample the first N committed v1 full-run logs and require zero diffs."""
    all_logs = sorted(glob.glob(
        os.path.join(_REPO_ROOT, "phase5_runs", "logs", "full", "**", "*.jsonl"),
        recursive=True))
    sample = all_logs[:n]
    n_files, n_ok, results = validate_many(sample)
    bad = {p: e for p, e in results.items() if e}
    print("schema calibration on v1: %d/%d sampled committed v1 logs OK" % (n_ok, n_files))
    if bad:
        for p, e in bad.items():
            print("  FAIL %s" % os.path.relpath(p, _REPO_ROOT))
            for line in e[:10]:
                print("    - %s" % line)
    return 0 if (n_ok == n_files and n_files == n) else 1


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    if argv[0] == "--calibrate":
        n = 20
        if "--n" in argv:
            n = int(argv[argv.index("--n") + 1])
        return _calibrate(n)
    paths = list(_iter_paths(argv))
    n_files, n_ok, results = validate_many(paths)
    bad = {p: e for p, e in results.items() if e}
    print("schema validation: %d/%d files OK (%d with diffs)" % (n_ok, n_files, len(bad)))
    for p, e in bad.items():
        print("  FAIL %s" % p)
        for line in e[:10]:
            print("    - %s" % line)
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
