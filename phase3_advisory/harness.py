"""Phase 3 — the ADVISORY harness.

This mode's defining property: **feedback is advisory text only, and the model
decides everything, including when to stop.** The harness renders the checker's
verdict as plain text into the next user message and imposes *no* restriction on
what the model does next; if the model writes a line that is exactly ``DONE``, the
episode ends immediately and the harness accepts that declaration *regardless of the
last verdict*. That non-gating is the whole point of the advisory condition — it is
the baseline the binding harness (Phase 4) is compared against.

Per-turn contract
------------------
For each model turn the harness:

1. extracts the LAST ```python fenced block (if any) from the reply, and
2. detects a line that is exactly ``DONE`` *outside* any code fence.

Then:

* If a code block is present -> run ``run_checks`` and render the verdict
  (``PASSED``; or ``FAILED`` with each failing test name + an error excerpt) as
  plain text into the next user message. No restriction is placed on the reply.
* If ``DONE`` is present -> the episode ends immediately
  (``status = "model_declared_done"``); the declaration is accepted even if the
  last verdict was a failure. (When a turn has *both* code and ``DONE``, the code is
  checked first so ``final_passed`` reflects that verdict, then ``DONE`` ends it.)
* If neither is present -> a fixed reminder is sent (and the turn still counts).

Hitting the step cap (from ``config``, default 8) ends the episode with
``status = "step_cap"``.

``run_episode`` returns the episode summary and writes one JSONL log per episode
under ``dev_logs/`` (one line per event), so the verdict text that entered the
model's context is literally visible in the log.
"""

import datetime
import itertools
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)

# Import the frozen Phase 2 checker.
sys.path.insert(0, os.path.join(_REPO_ROOT, "phase2_checker"))
from checker import run_checks  # noqa: E402

DEV_LOGS_DIR = os.path.join(_HERE, "dev_logs")

# Monotonic tie-breaker so two episodes started in the same microsecond get
# distinct ids/log paths (Date/random-free determinism is not required here).
_SEQ = itertools.count(1)

# ---------------------------------------------------------------------------
# Fixed prompt templates (verbatim in code — part of the experiment's protocol)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are fixing a buggy Python function. Reply with a complete replacement for "
    "the function in a single ```python code block. Tests are not shown to you; you "
    "will receive only a checker verdict after each submission. When you believe the "
    "function is correct and complete, declare completion by writing DONE on its own "
    "line, outside any code block."
)

REMINDER_MESSAGE = (
    "Your last message contained neither a Python code block nor a DONE line. "
    "Reply with a complete replacement function in a single ```python code block, "
    "or write DONE on its own line to finish."
)


# Design revision D17: when the description is withheld, this fixed sentence replaces
# it verbatim (the meta description string must not appear anywhere in the message).
WITHHELD_NOTICE = (
    "The specification of the intended behavior is withheld. Use the checker's "
    "feedback to determine correct behavior."
)


def build_first_user_message(meta, buggy_source, show_description=True):
    """The first user turn: (description | withheld-notice) + function name + buggy source.

    This is the ONE shared first-message builder (the binding harness imports it), so
    both arms present the task identically. When ``show_description`` is False (D17), the
    task's ``meta["description"]`` is withheld entirely — it must not appear anywhere in
    the message — and replaced by the fixed ``WITHHELD_NOTICE`` sentence; the function
    name and full buggy source are still shown.
    """
    header = meta["description"] if show_description else WITHHELD_NOTICE
    return (
        "%s\n\n"
        "Function to fix: %s\n\n"
        "Here is the current (buggy) implementation:\n\n"
        "```python\n%s\n```\n"
        % (header, meta["function_name"], buggy_source.rstrip("\n"))
    )


# ---------------------------------------------------------------------------
# Reply parsing
# ---------------------------------------------------------------------------

_PY_BLOCK_RE = re.compile(r"```[ \t]*(?:python|py)?[ \t]*\r?\n(.*?)```", re.DOTALL)


def extract_last_python_block(text):
    """Return the source of the LAST fenced code block, or ``None`` if there is none."""
    blocks = _PY_BLOCK_RE.findall(text or "")
    if not blocks:
        return None
    return blocks[-1]


def has_done_line(text):
    """True iff a line exactly ``DONE`` appears OUTSIDE any code fence."""
    in_fence = False
    for line in (text or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence and stripped == "DONE":
            return True
    return False


def render_verdict(verdict):
    """Render a checker verdict as the advisory plain-text feedback."""
    if verdict.get("passed"):
        return "PASSED\n\nThe checker reports that all tests passed."
    lines = ["FAILED", "", "The checker reports the following failing tests:"]
    for f in verdict.get("failures", []):
        name = f.get("test", "<unknown>")
        err = (f.get("error", "") or "").strip()
        excerpt = err.splitlines()[-1] if err else ""
        if len(excerpt) > 300:
            excerpt = excerpt[:300] + " ..."
        lines.append("- %s: %s" % (name, excerpt))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Per-episode JSONL logging
# ---------------------------------------------------------------------------

def _now_iso():
    return datetime.datetime.now().astimezone().isoformat()


def _stamp():
    return datetime.datetime.now().strftime("%Y%m%dT%H%M%S_%f") + "_%d" % next(_SEQ)


class _EpisodeLog:
    """Append-only JSONL writer: one line per event."""

    def __init__(self, path, model_id):
        self.path = path
        self.model_id = model_id
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # Truncate any pre-existing file for this (unique) episode id.
        open(self.path, "w").close()

    def write(self, event, step, **fields):
        record = {
            "event": event,
            "step": step,
            "timestamp": _now_iso(),
            "model": self.model_id,
        }
        record.update(fields)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# The episode loop
# ---------------------------------------------------------------------------

def run_episode(task_dir, client, config):
    """Run one advisory episode and return its summary dict.

    Summary keys: ``episode_id, task_id, mode, status, final_passed, steps,
    tokens_in, tokens_out`` (plus advisory ``log_path``).
    """
    with open(os.path.join(task_dir, "meta.json"), "r", encoding="utf-8") as fh:
        meta = json.load(fh)
    with open(os.path.join(task_dir, "buggy.py"), "r", encoding="utf-8") as fh:
        buggy_source = fh.read()

    step_cap = int(config.get("step_cap", 8))
    model_id = getattr(client, "model", None)
    task_id = meta["task_id"]

    episode_id = "%s-advisory-%s" % (task_id, _stamp())
    log_path = os.path.join(DEV_LOGS_DIR, episode_id + ".jsonl")
    log = _EpisodeLog(log_path, model_id)

    system = SYSTEM_PROMPT
    show_description = bool(config.get("show_description", True))
    first_user = build_first_user_message(meta, buggy_source, show_description)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": first_user},
    ]
    log.write("system_prompt", step=0, content=system)
    log.write("user_message", step=0, content=first_user)

    tokens_in = tokens_out = 0
    final_passed = False
    status = None
    steps = 0

    for step in range(1, step_cap + 1):
        steps = step
        resp = client.complete(messages)
        tokens_in += int(resp.get("tokens_in", 0))
        tokens_out += int(resp.get("tokens_out", 0))
        messages.append({"role": "assistant", "content": resp["text"]})
        log.write(
            "model_response",
            step=step,
            content=resp["text"],
            tokens_in=int(resp.get("tokens_in", 0)),
            tokens_out=int(resp.get("tokens_out", 0)),
            model=resp.get("model", model_id),
        )

        code = extract_last_python_block(resp["text"])
        done = has_done_line(resp["text"])

        feedback = None
        if code is not None:
            verdict = run_checks(task_dir, code)
            final_passed = bool(verdict["passed"])
            feedback = render_verdict(verdict)
            log.write(
                "check_verdict",
                step=step,
                passed=final_passed,
                failures=verdict.get("failures", []),
                content=feedback,
            )

        if done:
            status = "model_declared_done"
            break

        if code is not None:
            messages.append({"role": "user", "content": feedback})
            log.write("user_message", step=step, content=feedback)
        else:
            messages.append({"role": "user", "content": REMINDER_MESSAGE})
            log.write("user_message", step=step, content=REMINDER_MESSAGE)

    if status is None:
        status = "step_cap"

    summary = {
        "episode_id": episode_id,
        "task_id": task_id,
        "mode": "advisory",
        "status": status,
        "final_passed": final_passed,
        "steps": steps,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "log_path": log_path,
    }
    log.write(
        "episode_end",
        step=steps,
        status=status,
        final_passed=final_passed,
        steps=steps,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        episode_id=episode_id,
        task_id=task_id,
        mode="advisory",
    )
    return summary
