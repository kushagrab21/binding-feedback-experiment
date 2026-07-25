# Task Format Specification

This document specifies the on-disk format for every task in the experiment. It is
authoritative: task generators (step 1.2+) and validators (step 1.5+) must conform to
it, and any deviation is a bug in the task, not in the checker.

## Directory layout

Each task is a self-contained directory:

```
phase1_tasks/tasks/task_NNN/
├── buggy.py       # the function-under-test, containing a deliberate bug
├── tests.py       # deterministic test suite for the function
├── reference.py   # a correct implementation of the same function
└── meta.json      # metadata (schema below)
```

`NNN` is a zero-padded, monotonically increasing integer (`task_001`, `task_002`, …).

## Task content rules

Each task tests **exactly one pure function**. The function and its tests must obey:

- **Pure:** no I/O (no file, stdin/stdout, or console reads/writes as part of the
  function's contract), no randomness, no network, no clocks, no global mutable state.
- **Stdlib only:** no third-party imports. Only the Python standard library.
- **Deterministic tests:** the same inputs always produce the same pass/fail result.
- **Fast:** the full test suite runs in **under 2 seconds**.

`buggy.py`, `reference.py`, and `tests.py` must all define / reference the same
`function_name`, so that swapping `buggy.py` for `reference.py` is a drop-in change
that only affects correctness, not the interface the tests call.

## `meta.json` schema

```json
{
  "task_id":       "task_001",        // string, matches the directory name
  "seed_name":     "string",          // the seed this task was derived from
  "bug_type":      "string",          // category of the injected bug
  "difficulty":    "easy|medium|hard|null",  // null until step 1.6 assigns it
  "function_name": "string",          // the single function under test
  "description":   "string"           // one-line spec of what the function should do
}
```

Field notes:

- `task_id` — MUST equal the containing directory name (`task_NNN`).
- `seed_name` — identifier of the source seed the task was generated from.
- `bug_type` — the class of bug injected into `buggy.py` (e.g. off-by-one,
  wrong-operator, boundary-omission). Vocabulary is defined by the generator.
- `difficulty` — one of `"easy"`, `"medium"`, `"hard"`, or `null`. It MAY be `null`
  until step 1.6 assigns difficulty labels; it MUST NOT be any other value.
- `function_name` — the name of the single pure function the task is about.
- `description` — a one-line human-readable specification of the correct behaviour.

## Task invariants

Every task MUST satisfy both invariants. These are checked by the validator:

- **(a) Reference passes:** running `tests.py` against `reference.py` passes the
  **entire** test suite.
- **(b) Buggy fails:** running `tests.py` against `buggy.py` fails **at least one**
  test.

A task that violates either invariant is invalid and must not enter the task set.
