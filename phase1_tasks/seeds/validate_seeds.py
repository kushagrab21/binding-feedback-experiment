"""Validate the Phase 1 seed corpus against SEEDS.json and the format rules.

Run from the repository root (or anywhere):

    python phase1_tasks/seeds/validate_seeds.py

Exits 0 if every check passes, non-zero otherwise. Every failure prints a
concise diagnostic line prefixed with "FAIL:"; a final summary line reports
overall status. Structural inspection uses the `ast` module rather than
textual matching wherever practical.
"""

import ast
import json
import sys
from collections import Counter
from pathlib import Path

SEED_DIR = Path(__file__).resolve().parent
MANIFEST = SEED_DIR / "SEEDS.json"

EXPECTED_COUNT = 25

# Inclusive bounds on the number of code lines in a seed function's body
# (docstring, blank lines, and comment-only lines excluded). Enforced
# uniformly across every seed: too few lines means a near-trivial one-liner
# with little surface for bug injection; too many means an over-large task.
MIN_BODY_LINES = 5
MAX_BODY_LINES = 30

# Required number of seeds per category.
CATEGORY_COUNTS = {
    "numeric": 4,
    "strings": 4,
    "sequences": 4,
    "dictionaries": 3,
    "validation": 3,
    "algorithms": 2,
    "parsing": 5,
}

# Consistent bug-type vocabulary. Every candidate_bug_type must be drawn from
# this closed set so downstream generation has a stable label space. This is the
# final 8-type taxonomy fixed in phase1_tasks/generator/TAXONOMY.md (P1.3); the
# provisional 10-type vocabulary was retired and mapped onto these eight.
ALLOWED_BUG_TYPES = {
    "off-by-one",
    "wrong-comparison",
    "wrong-operator",
    "inverted-condition",
    "wrong-variable",
    "missing-edge-case",
    "wrong-return",
    "input-mutation",
}

# Standard-library modules that are nonetheless banned in seeds because they
# provide impurity (I/O, randomness, networking, clocks, subprocess, etc.).
BANNED_MODULES = {
    "os", "sys", "io", "socket", "subprocess", "random", "secrets",
    "time", "datetime", "calendar", "urllib", "http", "requests",
    "pathlib", "threading", "multiprocessing", "asyncio", "ctypes",
    "shutil", "glob", "tempfile", "select", "signal", "sqlite3",
}

# Builtin callables that imply impurity or dynamic execution.
BANNED_CALLS = {
    "open", "input", "print", "exec", "eval", "__import__", "compile",
}

# Best-effort stdlib module set for the third-party import check.
STDLIB = set(getattr(sys, "stdlib_module_names", set()))


class SeedError(Exception):
    pass


def fail(errors, message):
    errors.append(message)
    print("FAIL: " + message)


def top_level_module(name):
    return name.split(".")[0]


def count_body_code_lines(func_node, source_lines):
    """Return the number of code lines in a function's body, excluding the
    docstring, blank lines, and comment-only lines.

    The body region spans from the first non-docstring statement to the end
    of the last statement. Within that region, a physical line counts only
    if, after stripping whitespace, it is non-empty and does not begin with
    '#'. This deliberately refuses to credit padding (blank lines / comments)
    toward the required line count.
    """
    body = func_node.body
    if (body and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        body = body[1:]  # drop the docstring
    if not body:
        return 0
    start = body[0].lineno
    end = max(getattr(stmt, "end_lineno", stmt.lineno) for stmt in body)
    count = 0
    for lineno in range(start, end + 1):
        stripped = source_lines[lineno - 1].strip()
        if stripped and not stripped.startswith("#"):
            count += 1
    return count


def check_module_ast(errors, seed_id, path, expected_function):
    """AST-level checks for a single seed module. Returns nothing; appends
    to `errors` on any problem."""
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        fail(errors, f"{seed_id}: cannot read {path.name}: {exc}")
        return
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        fail(errors, f"{seed_id}: {path.name} does not parse: {exc}")
        return

    # (6) exactly one public top-level function; no async / classes.
    public_funcs = []
    for node in tree.body:
        if isinstance(node, ast.AsyncFunctionDef):
            fail(errors, f"{seed_id}: async function '{node.name}' is not allowed")
        elif isinstance(node, ast.FunctionDef):
            if not node.name.startswith("_"):
                public_funcs.append(node)
        elif isinstance(node, ast.ClassDef):
            fail(errors, f"{seed_id}: class '{node.name}' is not allowed")

    if len(public_funcs) != 1:
        fail(errors,
             f"{seed_id}: expected exactly 1 public top-level function, "
             f"found {len(public_funcs)}: {[f.name for f in public_funcs]}")
    else:
        func_node = public_funcs[0]
        if func_node.name != expected_function:
            # (7) function name matches manifest.
            fail(errors,
                 f"{seed_id}: function name '{func_node.name}' does not match "
                 f"manifest '{expected_function}'")
        # (12) function body is within the required line bounds.
        body_lines = count_body_code_lines(func_node, source.splitlines())
        if not (MIN_BODY_LINES <= body_lines <= MAX_BODY_LINES):
            fail(errors,
                 f"{seed_id}: function '{func_node.name}' body has {body_lines} "
                 f"code line(s); required {MIN_BODY_LINES}-{MAX_BODY_LINES}")

    # (8)/(9) import and impurity checks over the whole tree.
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod = top_level_module(alias.name)
                _check_import(errors, seed_id, mod)
        elif isinstance(node, ast.ImportFrom):
            if node.module is not None:
                _check_import(errors, seed_id, top_level_module(node.module))
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in BANNED_CALLS:
                fail(errors, f"{seed_id}: prohibited call to '{func.id}'")


def _check_import(errors, seed_id, mod):
    if mod in BANNED_MODULES:
        fail(errors, f"{seed_id}: prohibited import of '{mod}'")
    elif STDLIB and mod not in STDLIB:
        fail(errors, f"{seed_id}: non-stdlib (third-party) import of '{mod}'")


def main():
    errors = []

    # (1) manifest is valid JSON.
    try:
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print("FAIL: SEEDS.json not found")
        print("RESULT: FAILED (1 error)")
        return 1
    except json.JSONDecodeError as exc:
        print(f"FAIL: SEEDS.json is not valid JSON: {exc}")
        print("RESULT: FAILED (1 error)")
        return 1

    if not isinstance(data, list):
        print("FAIL: SEEDS.json must be a JSON array")
        print("RESULT: FAILED (1 error)")
        return 1

    # (2) exactly 20 seeds.
    if len(data) != EXPECTED_COUNT:
        fail(errors, f"expected {EXPECTED_COUNT} seeds, found {len(data)}")

    for index, entry in enumerate(data, start=1):
        expected_id = f"seed_{index:03d}"
        expected_file = f"{expected_id}.py"
        seed_id = entry.get("seed_id", f"<entry {index}>")

        # (3) IDs and filenames sequential.
        if entry.get("seed_id") != expected_id:
            fail(errors, f"entry {index}: seed_id '{entry.get('seed_id')}' "
                         f"is not '{expected_id}'")
        if entry.get("filename") != expected_file:
            fail(errors, f"{seed_id}: filename '{entry.get('filename')}' "
                         f"is not '{expected_file}'")

        # (10) at least two candidate bug types, from the vocabulary.
        bug_types = entry.get("candidate_bug_types", [])
        if not isinstance(bug_types, list) or len(bug_types) < 2:
            fail(errors, f"{seed_id}: needs at least two candidate bug types, "
                         f"got {bug_types}")
        else:
            for bt in bug_types:
                if bt not in ALLOWED_BUG_TYPES:
                    fail(errors, f"{seed_id}: bug type '{bt}' is outside the "
                                 f"allowed vocabulary")

        function_name = entry.get("function_name")
        if not function_name:
            fail(errors, f"{seed_id}: missing function_name")

        # (4) file exists, then (5)(6)(7)(8)(9) AST checks.
        path = SEED_DIR / expected_file
        if not path.exists():
            fail(errors, f"{seed_id}: declared file '{expected_file}' is missing")
        elif function_name:
            check_module_ast(errors, seed_id, path, function_name)

    # (11) category counts.
    category_counter = Counter(e.get("category") for e in data)
    for category, required in CATEGORY_COUNTS.items():
        actual = category_counter.get(category, 0)
        if actual != required:
            fail(errors, f"category '{category}': expected {required}, "
                         f"found {actual}")
    unexpected = set(category_counter) - set(CATEGORY_COUNTS)
    for category in sorted(x for x in unexpected if x is not None):
        fail(errors, f"category '{category}': not an expected category")

    if errors:
        print(f"RESULT: FAILED ({len(errors)} error(s))")
        return 1
    print(f"RESULT: OK — {EXPECTED_COUNT} seeds validated, "
          f"all invariants satisfied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
