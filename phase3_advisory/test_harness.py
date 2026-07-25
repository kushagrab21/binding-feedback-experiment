"""Phase 3.1 — advisory harness tests (stdlib unittest, MockModel only, no network).

These exercise the advisory loop entirely offline. The only code ever "submitted"
by the mock is read at runtime from a dev task's own ``buggy.py`` / ``reference.py``
(never authored here), honouring the bright line that the builder writes no task
solutions. Only dev task ``task_003`` is touched.

The four required cases:

* (a) buggy -> advisory FAILED appears in the next user message -> reference+DONE ->
  ``model_declared_done``, ``final_passed=True``, ``steps=2``.
* (b) DONE immediately after a failing submission -> harness accepts,
  ``final_passed=False`` (proving the harness does NOT gate on the checker).
* (c) never DONE, always resubmit buggy -> ``step_cap`` at 8.
* (d) the JSONL for (a) carries the FAILED verdict text inside a ``user_message``
  event, and non-zero token fields.
"""

import ast
import json
import os
import unittest

import harness
from providers import MockModel

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)
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


class TestAdvisoryFlow(unittest.TestCase):
    def setUp(self):
        # Code is copied from the task's own files at runtime — never hand-written.
        self.buggy = _read("buggy.py")
        self.reference = _read("reference.py")

    # (a) fail -> fix + DONE ------------------------------------------------
    # Method names are prefixed a/b/c/d so unittest's alphabetical ordering makes
    # this fail->fix episode the lexicographically-first log in dev_logs/, which is
    # what the acceptance snippet inspects (it wants a FAILED verdict shown in a
    # user_message — present here, but not in the (b) DONE-immediately episode).
    def test_a_fail_then_fix_and_done(self):
        client = MockModel([
            _py_block(self.buggy),
            _py_block(self.reference) + "\nDONE",
        ])
        summary = harness.run_episode(TASK_DIR, client, CONFIG)

        self.assertEqual(summary["status"], "model_declared_done")
        self.assertTrue(summary["final_passed"])
        self.assertEqual(summary["steps"], 2)
        self.assertEqual(summary["mode"], "advisory")
        self.assertEqual(summary["task_id"], "task_003")

        # The advisory FAILED verdict must have entered the model's context as the
        # user message following the buggy submission.
        events = _events(summary["log_path"])
        user_msgs = [e for e in events if e["event"] == "user_message"]
        self.assertTrue(
            any("FAILED" in e.get("content", "") for e in user_msgs),
            "expected a FAILED verdict rendered into a user_message",
        )

    # (b) DONE after a failing submission -> accepted, not gated -------------
    def test_b_done_after_failure_is_accepted(self):
        # One turn: buggy code AND a DONE line together. The checker fails the code,
        # but the harness still accepts the declaration -> final_passed=False.
        client = MockModel([_py_block(self.buggy) + "\nDONE"])
        summary = harness.run_episode(TASK_DIR, client, CONFIG)

        self.assertEqual(summary["status"], "model_declared_done")
        self.assertFalse(summary["final_passed"])

        # And the checker genuinely verdicted FAILED that turn (the harness did not
        # gate on it): a check_verdict with passed=False is present.
        events = _events(summary["log_path"])
        verdicts = [e for e in events if e["event"] == "check_verdict"]
        self.assertTrue(verdicts and verdicts[-1]["passed"] is False)

    # (c) never DONE, always buggy -> step cap ------------------------------
    def test_c_never_done_hits_step_cap(self):
        client = MockModel([_py_block(self.buggy)] * CONFIG["step_cap"])
        summary = harness.run_episode(TASK_DIR, client, CONFIG)

        self.assertEqual(summary["status"], "step_cap")
        self.assertEqual(summary["steps"], CONFIG["step_cap"])
        self.assertFalse(summary["final_passed"])

    # (d) the JSONL log records the verdict-in-context and non-zero tokens ---
    def test_d_log_contains_verdict_and_tokens(self):
        client = MockModel([
            _py_block(self.buggy),
            _py_block(self.reference) + "\nDONE",
        ])
        summary = harness.run_episode(TASK_DIR, client, CONFIG)
        events = _events(summary["log_path"])

        # FAILED verdict text literally present inside a user_message event.
        self.assertTrue(
            any(
                e["event"] == "user_message" and "FAILED" in e.get("content", "")
                for e in events
            )
        )
        # Non-zero token fields on the model_response events.
        responses = [e for e in events if e["event"] == "model_response"]
        self.assertTrue(responses)
        for e in responses:
            self.assertGreater(e["tokens_in"], 0)
            self.assertGreater(e["tokens_out"], 0)
        # Episode-level token totals are non-zero too.
        self.assertGreater(summary["tokens_in"], 0)
        self.assertGreater(summary["tokens_out"], 0)

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
            TASK_DIR, MockModel([_py_block(self.reference) + "\nDONE"]), cfg_hidden)
        first_hidden = self._first_user(s_hidden["log_path"])
        self.assertNotIn(desc, first_hidden)
        self.assertIn(self.WITHHELD, first_hidden)
        self.assertIn(meta["function_name"], first_hidden)

        # Default (no show_description key) -> legacy: description present, no notice.
        s_shown = harness.run_episode(
            TASK_DIR, MockModel([_py_block(self.reference) + "\nDONE"]), CONFIG)
        first_shown = self._first_user(s_shown["log_path"])
        self.assertIn(desc, first_shown)
        self.assertNotIn(self.WITHHELD, first_shown)

    # (f) D18 — bare-code presentation strips docstrings + comments -----------
    def test_f_bare_code_strips_docstrings_and_comments(self):
        with open(os.path.join(TASK_DIR, "meta.json"), encoding="utf-8") as fh:
            meta = json.load(fh)
        # Every docstring in the task's buggy source (module + functions).
        tree = ast.parse(self.buggy)
        docstrings = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef,
                                 ast.AsyncFunctionDef, ast.ClassDef)):
                d = ast.get_docstring(node, clean=False)
                if d:
                    docstrings.append(d)
        self.assertTrue(docstrings, "task_003 buggy source should have a docstring")

        cfg = dict(CONFIG)
        cfg["show_description"] = False
        s = harness.run_episode(
            TASK_DIR, MockModel([_py_block(self.reference) + "\nDONE"]), cfg)
        first = self._first_user(s["log_path"])
        # Neither the description nor any docstring text appears in the message.
        self.assertNotIn(meta["description"], first)
        for d in docstrings:
            for line in (ln.strip() for ln in d.splitlines()):
                if line:
                    self.assertNotIn(line, first)

        # Direct: strip removes a docstring AND a # comment, preserving code.
        snippet = ('def f(x):\n'
                   '    """doc-secret-text."""\n'
                   '    y = x + 1  # inline-secret-comment\n'
                   '    return y\n')
        stripped = harness.strip_doc_and_comments(snippet)
        self.assertNotIn("doc-secret-text", stripped)
        self.assertNotIn("inline-secret-comment", stripped)
        self.assertIn("return y", stripped)


if __name__ == "__main__":
    unittest.main()
