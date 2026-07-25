"""Phase 2 — the checker (a.k.a. the judge).

``run_checks(task_dir, candidate_code)`` is the single function every later phase
(3–5) trusts to decide whether a candidate solution passes a task's frozen test
suite. It is intentionally small, deterministic, and dependency-free (stdlib only).

Semantics
---------
Given a task directory (holding the frozen ``tests.py``) and a string of candidate
Python source, ``run_checks``:

1. creates a fresh temporary directory,
2. writes ``candidate_code`` to ``solution.py`` there (the suites do
   ``from solution import <fn>`` — the ``solution`` import contract from step 1.4),
3. copies the task's ``tests.py`` alongside it,
4. runs ``python3 -B -E -s -m unittest tests -v`` as a subprocess (cwd = the temp
   dir) under a wall-clock timeout, and
5. parses the verbose output into a structured verdict.

Return value (the contract — exactly these three keys are guaranteed; extra keys
may be present and are advisory)::

    {
      "passed":     bool,                                   # True iff the WHOLE suite passed
      "failures":   [{"test": str, "error": str}, ...],     # one entry per failing/erroring test
      "raw_output": str,                                    # the subprocess output, verbatim
      # advisory extras:
      "timed_out":  bool,
      "returncode": int | None,
      "n_total":    int,
      "n_failed":   int,
    }

``passed`` is ``True`` iff the unittest process exited 0 (unittest returns 0 iff
``result.wasSuccessful()`` — no failures and no errors). Whenever ``passed`` is
``False`` the ``failures`` list is non-empty.

Failure taxonomy (the ``test`` field of each failure entry):
  * a real test method name (e.g. ``test_large_value``) — a genuine assertion
    failure (FAIL) or in-test exception (ERROR);
  * ``"__timeout__"`` — the suite exceeded the timeout (e.g. an infinite loop);
  * ``"__collection__"`` — the suite could not even be collected/imported: a
    syntax error in the candidate, a missing/misnamed function, an empty
    submission, or any exception raised at import time;
  * ``"__error__"`` — a non-zero exit that produced no parseable failure (a
    defensive catch-all so ``passed=False`` always carries a reason).

Determinism
-----------
Same ``(task_dir, candidate_code)`` inputs always yield the same ``passed`` and the
same ``failures`` list. To achieve this the per-failure ``error`` text is scrubbed
of the (random) temporary-directory path, which is the only volatile content in a
traceback. ``raw_output`` is preserved verbatim (as required) and therefore still
contains the temp path and unittest's ``Ran N tests in X.XXXs`` timing line — so a
byte-for-byte comparison of two runs must normalise those two volatile substrings
first (see ``test_checker.py``'s determinism test).

Static pre-execution guard (safety-only)
----------------------------------------
Before ANY subprocess is spawned, the candidate is ``ast.parse``d and, if it
parses, statically scanned. A candidate is rejected *without being executed at all*
(verdict ``__banned__``) if it imports any module whose top-level name is on
``BANNED_IMPORTS`` (network / OS / process / filesystem / dynamic-import surface) or
calls any bare builtin on ``BANNED_CALLS`` (``open``/``exec``/``eval``/``input``/
``compile``/``__import__``). If the candidate does NOT parse (a syntax error), the
guard does nothing and control falls through to the subprocess path, so syntax-error
behaviour is byte-identical to the pre-guard checker.

The guard is deliberately SAFETY-ONLY. It bans only what can reach the network, the
filesystem, other processes, or arbitrary dynamic execution — never what is merely
inelegant. In particular ``print`` and every import NOT on the ban list are allowed
by design: a chatty-but-correct model fix must still be graded ``passed=True``.
Banning cosmetic impurity would reject correct submissions and silently distort the
advisory-vs-binding success-rate comparison that is the whole point of the
experiment. Safety bans only; style is never a ground for rejection.

Isolation and its limits
-------------------------
The subprocess runs with ``-E -s -B``:
  * ``-E`` ignores ``PYTHON*`` environment variables,
  * ``-s`` omits the user ``site-packages`` directory,
  * ``-B`` disables ``.pyc`` writing (belt-and-braces against stale bytecode; each
    call already uses a fresh temp dir, so no ``.pyc`` can pre-exist).
These are exactly the components of the ``-I`` ("isolated interpreter") flag that
apply here. ``-I`` itself is deliberately NOT used: ``-I`` implies ``-P`` (Python
3.11+), which removes the run directory from ``sys.path`` — and that would make the
suite's ``from solution import ...`` and ``import tests`` fail (there would be no
importable ``solution``/``tests`` at all). ``-P`` is safe to omit because the run
directory is freshly created by us and contains only our two trusted files.

LIMITATION — no OS-level sandbox. ``-E -s`` gives *interpreter* isolation, not
operating-system isolation. Candidate code runs as a normal subprocess: it could,
in principle, open files or network sockets. This is acceptable for THIS experiment
because every task's code-under-test is drawn from the frozen, validated,
stdlib-pure Phase 1 corpus (no I/O, no network, no clocks) — candidates are graded
against those tasks, and the tasks themselves neither perform nor require any such
access. Network/filesystem sandboxing is explicitly out of scope and is recorded as
a known limitation in EXPERIMENT_LOG.md.
"""

import ast
import os
import re
import shutil
import subprocess
import sys
import tempfile

# Default wall-clock ceiling for a single suite run, in seconds (the contract).
DEFAULT_TIMEOUT_S = 10.0

# --- Static pre-execution guard (safety-only). ---
# Top-level module names the candidate may not import: anything reaching the
# network, the OS/process table, the filesystem, or dynamic import machinery.
BANNED_IMPORTS = frozenset({
    "socket", "subprocess", "os", "sys", "shutil", "pathlib", "tempfile",
    "urllib", "http", "ctypes", "multiprocessing", "threading", "signal",
    "importlib",
})
# Bare builtin names the candidate may not call: file access, arbitrary code
# execution, and dynamic import.
BANNED_CALLS = frozenset({
    "open", "exec", "eval", "input", "compile", "__import__",
})

# A verbose per-test result line: "name (mod.Class.name) ... ok|FAIL|ERROR".
# group(1) = test method name, group(2) = fully-qualified test id, group(3) = status.
# NOTE: this mirrors validate_tasks.py's _VLINE so that failures[0]["test"] equals
# the "first failing test" recorded in phase1_tasks/validation/task_validation.txt.
_VLINE = re.compile(r"^(\w+) \((.*?)\) \.\.\. (ok|FAIL|ERROR)\b")

# The "Ran N tests in X.XXXs" summary line.
_RAN = re.compile(r"^Ran (\d+) tests?\b", re.MULTILINE)

# Header of a failure/error detail block: "FAIL: name (id)" / "ERROR: name (id)".
_BLOCK_HEADER = re.compile(r"^(?:FAIL|ERROR): (\w+) \((.*?)\)\s*$")

_SEP = re.compile(r"^=+$")       # block separator line (unittest uses 70 '=')
_DASH = re.compile(r"^-+$")      # sub-separator / footer line (70 '-')

# Marker that unittest turned an import-time failure into a synthetic failing test.
_FAILED_TEST_MARKER = "_FailedTest"


def _static_guard(candidate_code):
    """Return a rejection reason string if the candidate is statically unsafe.

    Parses ``candidate_code`` and scans for a banned import or a banned bare-name
    call. Returns ``None`` if the candidate is safe *or does not parse* — a syntax
    error is left for the subprocess path so that behaviour is unchanged. When
    multiple violations exist, the earliest by (line, column) is reported, so the
    reason is deterministic.
    """
    try:
        tree = ast.parse(candidate_code)
    except SyntaxError:
        return None  # do not reject here; fall through to the subprocess path

    violations = []  # (lineno, col_offset, reason)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in BANNED_IMPORTS:
                    violations.append((
                        node.lineno, node.col_offset,
                        f"import of banned module '{top}'"))
        elif isinstance(node, ast.ImportFrom):
            # node.module is None for `from . import x` (relative); level>0 has no
            # importable top-level name to ban.
            if node.module and node.level == 0:
                top = node.module.split(".")[0]
                if top in BANNED_IMPORTS:
                    violations.append((
                        node.lineno, node.col_offset,
                        f"import from banned module '{top}'"))
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in BANNED_CALLS:
                violations.append((
                    node.lineno, node.col_offset,
                    f"call to banned builtin '{func.id}'"))

    if not violations:
        return None
    violations.sort(key=lambda v: (v[0], v[1]))
    _lineno, _col, what = violations[0]
    return (
        f"{what} at line {_lineno}: the static safety guard forbids "
        f"network / OS / process / filesystem / dynamic-execution access in "
        f"candidate code, so it was rejected WITHOUT being executed. "
        f"(Safety-only: print and non-banned imports are allowed.)")


def _scrub(text, *paths):
    """Replace each temp-dir path (and its realpath) with a stable placeholder.

    The temporary directory name is random, so tracebacks that mention it are the
    only source of run-to-run variation in a failure's error text. Canonicalising
    it makes the ``failures`` list deterministic.
    """
    for p in paths:
        if p:
            text = text.replace(p, "<sandbox>")
    return text


def _parse_detail_blocks(output):
    """Map fully-qualified test id -> its (stripped) FAIL/ERROR detail text.

    Walks the verbose output line by line, isolating each block that begins with a
    '=' separator followed by a ``FAIL:``/``ERROR:`` header, and stops the block at
    the next '=' separator or at the trailing ``----\\nRan N tests`` footer.
    """
    lines = output.splitlines()
    n = len(lines)
    blocks = {}
    i = 0
    while i < n:
        if _SEP.match(lines[i]) and i + 1 < n:
            m = _BLOCK_HEADER.match(lines[i + 1])
            if m:
                full_id = m.group(2)
                j = i + 2
                if j < n and _DASH.match(lines[j]):
                    j += 1  # skip the dash line under the header
                body = []
                while j < n and not _SEP.match(lines[j]):
                    # Stop at the footer: a dash line immediately before "Ran N...".
                    if (_DASH.match(lines[j]) and j + 1 < n
                            and _RAN.match(lines[j + 1])):
                        break
                    body.append(lines[j])
                    j += 1
                blocks[full_id] = "\n".join(body).strip()
                i = j
                continue
        i += 1
    return blocks


def run_checks(task_dir, candidate_code, timeout=DEFAULT_TIMEOUT_S):
    """Run ``task_dir``'s frozen suite against ``candidate_code``; return a verdict.

    Parameters
    ----------
    task_dir : path-like
        A task directory containing ``tests.py`` (per TASK_FORMAT.md).
    candidate_code : str
        Python source to be written to ``solution.py`` and tested.
    timeout : float
        Wall-clock ceiling for the subprocess, in seconds. Defaults to the
        contract's 10s; exposed only so tests can use a shorter bound for the
        deliberate infinite-loop case.

    Returns
    -------
    dict
        See module docstring for the contract.
    """
    task_dir = os.fspath(task_dir)
    tests_src = os.path.join(task_dir, "tests.py")

    # --- Static pre-execution guard: reject unsafe candidates without running. ---
    banned_reason = _static_guard(candidate_code)
    if banned_reason is not None:
        return {
            "passed": False,
            "failures": [{"test": "__banned__", "error": banned_reason}],
            "raw_output": ("static guard: candidate rejected before execution "
                           "(no subprocess run)\n" + banned_reason),
            "timed_out": False,
            "returncode": None,
            "n_total": 0,
            "n_failed": 1,
        }

    tmp = tempfile.mkdtemp(prefix="checker_")
    real_tmp = os.path.realpath(tmp)
    try:
        with open(os.path.join(tmp, "solution.py"), "w") as fh:
            fh.write(candidate_code)
        shutil.copyfile(tests_src, os.path.join(tmp, "tests.py"))

        try:
            proc = subprocess.run(
                [sys.executable, "-B", "-E", "-s", "-m", "unittest", "tests", "-v"],
                cwd=tmp,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raw = exc.output or ""
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", "replace")
            return {
                "passed": False,
                "failures": [{
                    "test": "__timeout__",
                    "error": (f"suite exceeded the {timeout:g}s timeout "
                              f"(non-terminating candidate)"),
                }],
                "raw_output": raw,
                "timed_out": True,
                "returncode": None,
                "n_total": 0,
                "n_failed": 0,
            }

        output = proc.stdout or ""
        returncode = proc.returncode

        ran = _RAN.search(output)
        n_total = int(ran.group(1)) if ran else 0

        # Verbose status lines, in run (alphabetical) order.
        status_lines = []  # (method_name, full_id, status)
        for line in output.splitlines():
            m = _VLINE.match(line)
            if m:
                status_lines.append((m.group(1), m.group(2), m.group(3)))

        # --- Collection failure? Two shapes, both -> __collection__. ---
        # (i) import-family error: unittest reports a synthetic "_FailedTest".
        # (ii) hard load crash (e.g. SyntaxError): a raw traceback, no "Ran" line.
        is_collection = (
            _FAILED_TEST_MARKER in output
            or (returncode != 0 and ran is None)
        )
        if is_collection:
            return {
                "passed": False,
                "failures": [{
                    "test": "__collection__",
                    "error": _scrub(output, real_tmp, tmp).strip(),
                }],
                "raw_output": output,
                "timed_out": False,
                "returncode": returncode,
                "n_total": n_total,
                "n_failed": max(n_total, 1),
            }

        # --- Normal run: build failures from the verbose status lines. ---
        blocks = _parse_detail_blocks(output)
        failures = []
        for method, full_id, status in status_lines:
            if status in ("FAIL", "ERROR"):
                detail = blocks.get(full_id, "")
                failures.append({
                    "test": method,
                    "error": _scrub(detail, real_tmp, tmp),
                })

        passed = returncode == 0

        # Defensive catch-all: non-zero exit with nothing parsed as a failure.
        if not passed and not failures:
            failures.append({
                "test": "__error__",
                "error": _scrub(output, real_tmp, tmp).strip(),
            })

        return {
            "passed": passed,
            "failures": failures,
            "raw_output": output,
            "timed_out": False,
            "returncode": returncode,
            "n_total": n_total,
            "n_failed": len(failures),
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
