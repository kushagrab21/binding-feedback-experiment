"""Phase 4 — the BINDING harness.

This mode is the structural mirror of the Phase 3 advisory harness. It uses the
**same model, same checker, same step cap, and — deliberately — the same
task-presentation text and the same verdict-rendering text** as advisory (both are
imported verbatim from ``phase3_advisory/harness.py`` so the two arms deliver
*identical feedback content*; the arms differ only structurally). There are exactly
**three** structural differences from advisory, and no others:

1. **Done is computed, not declared.** The episode ends successfully
   (``status = "solved"``) only when ``run_checks`` passes. There is no declare-done
   action; the system prompt tells the model to keep submitting a corrected, full
   replacement until the checker passes (it never mentions ``DONE``). Any ``DONE``-like
   line in a response is ignored as plain text — and, when a bare ``DONE`` line is
   present, a ``done_ignored`` event is logged. That is the precise
   divergence-from-advisory point (advisory would have *terminated* there).

2. **Identical resubmission is rejected by the harness.** After a failed check, if the
   next submission is byte-identical (after extracting the code block) to the previous
   failed one, the harness does NOT run the checker: it logs a ``resubmission_rejected``
   event and re-sends the SAME verdict text as before, with no added advice or
   explanation (the rejection changes harness state, not the feedback content). The
   consecutive-identical counter increments.

3. **Escalation.** Three consecutive identical failed submissions end the episode with
   ``status = "escalated"`` (a failure for the model, logged distinctly). The exact
   definition, encoded here and in the tests verbatim: **a failed check followed by 2
   byte-identical resubmissions = 3 consecutive identical failures -> escalated.**

Other terminal status: ``step_cap`` (from ``config``, default 8), when the model keeps
submitting non-identical still-failing code until the cap.

``run_episode`` returns the episode summary (``mode = "binding"``) and writes one JSONL
log per episode under ``dev_logs/`` (git-ignored). The event shapes are identical to
advisory's, plus the two binding-only events ``resubmission_rejected`` and
``done_ignored``: ``system_prompt, user_message, model_response, check_verdict,
resubmission_rejected, done_ignored, episode_end``.
"""

import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)

# ---------------------------------------------------------------------------
# Reuse the advisory harness verbatim for everything the two arms must share.
# The file is loaded by absolute path (both files are named ``harness.py``, so a
# plain ``import harness`` would be ambiguous). On import the advisory module wires
# up the frozen Phase 2 checker itself, so ``advisory.run_checks`` is available too.
# ---------------------------------------------------------------------------
_ADV_PATH = os.path.join(_REPO_ROOT, "phase3_advisory", "harness.py")
_spec = importlib.util.spec_from_file_location("advisory_harness", _ADV_PATH)
advisory = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(advisory)

# Shared, byte-for-byte with advisory: task presentation + verdict rendering + reply
# parsing + the JSONL logger + the id stamp + the checker.
build_first_user_message = advisory.build_first_user_message
render_verdict = advisory.render_verdict
extract_last_python_block = advisory.extract_last_python_block
has_done_line = advisory.has_done_line
run_checks = advisory.run_checks

DEV_LOGS_DIR = os.path.join(_HERE, "dev_logs")

# ---------------------------------------------------------------------------
# Binding-only prompt templates.
#
# The first two sentences are identical to advisory's SYSTEM_PROMPT (task framing +
# "you see only a checker verdict"). Only the STOP mechanism differs: binding has no
# declare-done action, so the prompt tells the model to keep submitting until the
# checker passes and never mentions DONE. The reminder likewise never mentions DONE.
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are fixing a buggy Python function. Reply with a complete replacement for "
    "the function in a single ```python code block. Tests are not shown to you; you "
    "will receive only a checker verdict after each submission. Keep submitting a "
    "corrected, complete replacement until the checker reports that all tests pass; "
    "the episode ends only when the checker passes. There is no way to declare "
    "completion yourself."
)

REMINDER_MESSAGE = (
    "Your last message contained no Python code block. Reply with a complete "
    "replacement function in a single ```python code block."
)


# ---------------------------------------------------------------------------
# The episode loop
# ---------------------------------------------------------------------------

def run_episode(task_dir, client, config):
    """Run one binding episode and return its summary dict.

    Summary keys mirror advisory's: ``episode_id, task_id, mode, status,
    final_passed, steps, tokens_in, tokens_out`` (plus ``log_path``), with
    ``mode = "binding"`` and ``status`` one of ``solved`` / ``escalated`` / ``step_cap``.
    """
    with open(os.path.join(task_dir, "meta.json"), "r", encoding="utf-8") as fh:
        meta = json.load(fh)
    with open(os.path.join(task_dir, "buggy.py"), "r", encoding="utf-8") as fh:
        buggy_source = fh.read()

    step_cap = int(config.get("step_cap", 8))
    model_id = getattr(client, "model", None)
    task_id = meta["task_id"]

    episode_id = "%s-binding-%s" % (task_id, advisory._stamp())
    log_path = os.path.join(DEV_LOGS_DIR, episode_id + ".jsonl")
    log = advisory._EpisodeLog(log_path, model_id)

    system = SYSTEM_PROMPT
    first_user = build_first_user_message(meta, buggy_source)
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

    # Identical-resubmission tracking. ``prev_code`` is the extracted code block of the
    # previous submission (checked or rejected); ``prev_verdict_text`` is the verdict
    # last rendered for a checked-and-failed submission (re-sent verbatim on rejection).
    # ``consecutive_identical`` counts consecutive identical failed submissions: a
    # checked failure sets it to 1, and each byte-identical resubmission increments it;
    # reaching 3 escalates (i.e. one failed check + two identical resubmissions).
    prev_code = None
    prev_verdict_text = None
    consecutive_identical = 0

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

        # Divergence-from-advisory event: a bare DONE line is ignored as text (advisory
        # would have terminated here). Logged whenever present; never ends the episode.
        if has_done_line(resp["text"]):
            log.write("done_ignored", step=step, content=resp["text"])

        if code is None:
            # No submission this turn: send the binding reminder. The turn still counts.
            messages.append({"role": "user", "content": REMINDER_MESSAGE})
            log.write("user_message", step=step, content=REMINDER_MESSAGE)
            continue

        # Identical resubmission of the previous (failed) code -> reject, do NOT check.
        if prev_code is not None and code == prev_code:
            consecutive_identical += 1
            log.write(
                "resubmission_rejected",
                step=step,
                consecutive_identical=consecutive_identical,
                content=prev_verdict_text,
            )
            if consecutive_identical >= 3:
                status = "escalated"
                break
            # Re-send the SAME verdict text as before — no added advice or explanation.
            messages.append({"role": "user", "content": prev_verdict_text})
            log.write("user_message", step=step, content=prev_verdict_text)
            continue

        # New / different submission -> run the checker.
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

        if final_passed:
            status = "solved"
            break

        # Failed check: this submission starts (or restarts) an identical-failure streak.
        prev_code = code
        prev_verdict_text = feedback
        consecutive_identical = 1
        messages.append({"role": "user", "content": feedback})
        log.write("user_message", step=step, content=feedback)

    if status is None:
        status = "step_cap"

    summary = {
        "episode_id": episode_id,
        "task_id": task_id,
        "mode": "binding",
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
        mode="binding",
    )
    return summary
