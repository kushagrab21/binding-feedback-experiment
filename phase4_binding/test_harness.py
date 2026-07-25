"""Phase 4.1 — binding harness tests (stdlib unittest, MockModel only, no network).

These exercise the binding loop entirely offline. The only code ever "submitted" by
the mock is read at runtime from a dev task's own ``buggy.py`` / ``reference.py``
(never authored here), honouring the bright line that the builder writes no task
solutions. Only dev task ``task_003`` is touched. Where a test needs several distinct
still-failing submissions (case d), each is the task's own ``buggy.py`` with a unique
trailing *comment* appended: only whitespace/comment differs, so every variant is
byte-distinct (never a rejected identical) yet still fails the checker — it is never a
hand-written fix.

The four required cases:

* (a) buggy then reference -> ``solved`` at step 2 — the key structural test: a
  response containing DONE with failing code does NOT end the episode
  (``done_ignored`` logged, loop continues), where advisory would have terminated.
* (b) identical failed resubmission -> ``resubmission_rejected`` logged, and the
  checker is invoked only ONCE for the two identical submissions.
* (c) three consecutive identical failures -> ``escalated`` at step 3. Definition
  (verbatim): a failed check followed by 2 byte-identical resubmissions = 3
  consecutive identical failures -> escalated.
* (d) never-repeating but never-passing submissions -> ``step_cap`` at 8.
"""

import json
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)

# phase4's own dir first, so ``import harness`` binds the BINDING harness (not the
# identically-named advisory one). MockModel is imported from the phase3 providers
# module (appended, never prepended, so it cannot shadow ``harness``).
sys.path.insert(0, _HERE)
sys.path.append(os.path.join(_REPO_ROOT, "phase3_advisory"))

import harness
from providers import MockModel

TASK_DIR = os.path.join(_REPO_ROOT, "phase1_tasks", "tasks", "task_003")

CONFIG = {"model": "mock-model", "temperature": 0, "step_cap": 8}


def _read(name):
    with open(os.path.join(TASK_DIR, name), "r", encoding="utf-8") as fh:
        return fh.read()


def _py_block(source):
    return "```python\n%s\n```" % source.rstrip("\n")


def _events(log_path):
    with open(log_path, "r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


class TestBindingFlow(unittest.TestCase):
    def setUp(self):
        # Code is copied from the task's own files at runtime — never hand-written.
        self.buggy = _read("buggy.py")
        self.reference = _read("reference.py")

    # (a) buggy(+DONE) -> reference -> solved; DONE does NOT end the episode ---------
    def test_a_done_ignored_then_computed_solve(self):
        # Turn 1 submits the buggy code AND a DONE line. In advisory this would end the
        # episode immediately (model_declared_done); in binding the DONE is ignored as
        # text (done_ignored logged) and the loop continues. Turn 2 submits reference,
        # the checker passes, and completion is COMPUTED -> solved at step 2.
        client = MockModel([
            _py_block(self.buggy) + "\nDONE",
            _py_block(self.reference),
        ])
        summary = harness.run_episode(TASK_DIR, client, CONFIG)

        self.assertEqual(summary["status"], "solved")
        self.assertTrue(summary["final_passed"])
        self.assertEqual(summary["steps"], 2)
        self.assertEqual(summary["mode"], "binding")
        self.assertEqual(summary["task_id"], "task_003")

        events = _events(summary["log_path"])
        # The DONE line was ignored, not obeyed: a done_ignored event fired at step 1,
        # and there is NO advisory-style "model_declared_done" status anywhere.
        done_ignored = [e for e in events if e["event"] == "done_ignored"]
        self.assertEqual(len(done_ignored), 1)
        self.assertEqual(done_ignored[0]["step"], 1)
        self.assertNotEqual(summary["status"], "model_declared_done")
        # Step 1 failed (buggy), step 2 passed (reference) — completion is computed.
        verdicts = [e for e in events if e["event"] == "check_verdict"]
        self.assertEqual([v["passed"] for v in verdicts], [False, True])

    # (b) identical resubmission is rejected; checker runs once for the two identicals -
    def test_b_identical_resubmission_rejected_checker_runs_once(self):
        # buggy, buggy (identical -> rejected, NOT checked), reference -> solved.
        client = MockModel([
            _py_block(self.buggy),
            _py_block(self.buggy),
            _py_block(self.reference),
        ])
        summary = harness.run_episode(TASK_DIR, client, CONFIG)

        self.assertEqual(summary["status"], "solved")
        self.assertEqual(summary["steps"], 3)

        events = _events(summary["log_path"])
        rejected = [e for e in events if e["event"] == "resubmission_rejected"]
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0]["step"], 2)

        # The two byte-identical buggy submissions triggered the checker only ONCE:
        # exactly two check_verdict events total (buggy@1 FAILED, reference@3 PASSED).
        verdicts = [e for e in events if e["event"] == "check_verdict"]
        self.assertEqual(len(verdicts), 2)
        self.assertEqual([v["passed"] for v in verdicts], [False, True])
        self.assertEqual([v["step"] for v in verdicts], [1, 3])

        # The rejection re-sent the SAME verdict text as the original failure, verbatim.
        failed_user_msg = next(
            e for e in events
            if e["event"] == "user_message" and e["step"] == 1
        )
        self.assertEqual(rejected[0]["content"], failed_user_msg["content"])

    # (c) three consecutive identical failures -> escalated at step 3 ----------------
    def test_c_three_consecutive_identical_escalate(self):
        # Definition (verbatim): a failed check followed by 2 byte-identical
        # resubmissions = 3 consecutive identical failures -> escalated.
        #   step 1: buggy fails the checker      (consecutive_identical = 1)
        #   step 2: buggy identical -> rejected  (consecutive_identical = 2)
        #   step 3: buggy identical -> rejected  (consecutive_identical = 3) -> escalated
        client = MockModel([
            _py_block(self.buggy),
            _py_block(self.buggy),
            _py_block(self.buggy),
        ])
        summary = harness.run_episode(TASK_DIR, client, CONFIG)

        self.assertEqual(summary["status"], "escalated")
        self.assertEqual(summary["steps"], 3)
        self.assertFalse(summary["final_passed"])

        events = _events(summary["log_path"])
        # Exactly one real check (step 1); the two identicals were rejected, not checked.
        verdicts = [e for e in events if e["event"] == "check_verdict"]
        self.assertEqual(len(verdicts), 1)
        rejected = [e for e in events if e["event"] == "resubmission_rejected"]
        self.assertEqual(len(rejected), 2)
        self.assertEqual([r["consecutive_identical"] for r in rejected], [2, 3])
        end = [e for e in events if e["event"] == "episode_end"][0]
        self.assertEqual(end["status"], "escalated")

    # (d) never-repeating but never-passing -> step cap at 8 -------------------------
    def test_d_never_repeats_never_passes_hits_step_cap(self):
        # 8 byte-distinct submissions that all still fail: each is the task's own
        # buggy.py with a unique trailing comment (only a comment differs, so it never
        # counts as an identical resubmission, and it never passes the checker).
        client = MockModel([
            _py_block(self.buggy + "\n# attempt %d" % i)
            for i in range(CONFIG["step_cap"])
        ])
        summary = harness.run_episode(TASK_DIR, client, CONFIG)

        self.assertEqual(summary["status"], "step_cap")
        self.assertEqual(summary["steps"], CONFIG["step_cap"])
        self.assertFalse(summary["final_passed"])

        events = _events(summary["log_path"])
        # Every one of the 8 distinct submissions was actually checked; none rejected.
        verdicts = [e for e in events if e["event"] == "check_verdict"]
        self.assertEqual(len(verdicts), CONFIG["step_cap"])
        self.assertTrue(all(v["passed"] is False for v in verdicts))
        rejected = [e for e in events if e["event"] == "resubmission_rejected"]
        self.assertEqual(len(rejected), 0)

    # (e) D17 — description withheld vs shown in the first user message -------
    WITHHELD = ("The specification of the intended behavior is withheld. "
                "Use the checker's feedback to determine correct behavior.")

    def _first_user(self, log_path):
        for e in _events(log_path):
            if e["event"] == "user_message" and e["step"] == 0:
                return e["content"]
        raise AssertionError("no step-0 user_message")

    def test_e_hidden_vs_shown_description(self):
        with open(os.path.join(TASK_DIR, "meta.json"), encoding="utf-8") as fh:
            meta = json.load(fh)
        desc = meta["description"]

        # show_description: False -> description text absent, withheld notice present.
        cfg_hidden = dict(CONFIG)
        cfg_hidden["show_description"] = False
        s_hidden = harness.run_episode(
            TASK_DIR, MockModel([_py_block(self.reference)]), cfg_hidden)
        first_hidden = self._first_user(s_hidden["log_path"])
        self.assertNotIn(desc, first_hidden)
        self.assertIn(self.WITHHELD, first_hidden)
        self.assertIn(meta["function_name"], first_hidden)

        # Default (no show_description key) -> legacy: description present, no notice.
        s_shown = harness.run_episode(
            TASK_DIR, MockModel([_py_block(self.reference)]), CONFIG)
        first_shown = self._first_user(s_shown["log_path"])
        self.assertIn(desc, first_shown)
        self.assertNotIn(self.WITHHELD, first_shown)


if __name__ == "__main__":
    unittest.main()
