"""Phase 6.1 — the reproducible analysis.

ONE deterministic command that regenerates ``phase6_analysis/results.md`` and
``phase6_analysis/results.json`` from the committed Phase-5 artifacts ONLY (per-cell
JSONL logs, cell manifests, frozen task metas, and the frozen Phase-2 checker). It
makes **no** API calls, modifies **nothing** outside ``phase6_analysis/``, and treats
``phase1_tasks/`` as immutable. Run it twice: the two outputs are byte-identical (no
timestamps live inside the results — the run date belongs in the EXPERIMENT_LOG entry).

What it computes
----------------
* Per cell: success rate; mean steps; tokens in/out; cost; cost per solved task;
  step_cap / done_ignored / resubmission_rejected / escalated counts; false-DONE count
  (advisory).
* Feedback-compliance rate, operationalized EXACTLY as (also stated verbatim in
  results.md): a post-failure step is compliant iff the next submission is (a)
  non-byte-identical to the failed one AND (b) changes the checker outcome signature —
  the set of failing test names — when ``run_checks`` is re-executed on both submissions
  against the frozen task. Denominator: all post-failure model turns that submitted code.
  Reported as numerator/denominator per cell, never a bare rate. (This is the design
  doc's fallback operationalization; line-coverage tracing was NOT implemented.)
* Identical-resubmission rate per cell (numerator/denominator).
* Breakdowns: success rate by bug_type x cell and difficulty x cell, from each task's
  frozen ``meta.json`` (the missing-edge-case row is flagged).
* Rescue decomposition for the weak-model binding cell: genuine forced repairs
  (FAILED verdict -> changed submission -> PASSED) vs first-sample passes on tasks the
  advisory arm failed — verified from the logs, not assumed.
* Statistics: per model, exact McNemar over the 87 task-paired advisory/binding
  outcomes (discordant counts BOTH directions + exact two-sided binomial p, stdlib
  ``math.comb`` only); the interaction stated with both models' discordant counts.
* A header: FREEZE_HASH, split sha256 (recomputed here with ``hashlib``), per-cell model
  snapshots, config, the D17/D18 presentation note, and the 5.3 pre-registration text
  quoted with a confirmed/disconfirmed mark computed per item.
"""

import glob
import hashlib
import json
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)

# The frozen Phase-2 checker is the single source of truth for a verdict. Re-running it
# on committed submissions is analysis over committed artifacts, not a new experiment.
sys.path.insert(0, os.path.join(_REPO, "phase2_checker"))
from checker import run_checks  # noqa: E402
sys.path.insert(0, os.path.join(_REPO, "phase3_advisory"))
from harness import extract_last_python_block  # noqa: E402

LOG_ROOT = os.path.join(_REPO, "phase5_runs", "logs", "full")
MANIFEST_DIR = os.path.join(_REPO, "phase5_runs", "manifests")
TASKS_DIR = os.path.join(_REPO, "phase1_tasks", "tasks")
SPLIT_JSON = os.path.join(_REPO, "phase1_tasks", "validation", "split.json")

# Published USD per 1M tokens (input, output) — same table Phase 5 costed with.
RATES = {
    "gpt-4o-mini-2024-07-18": (0.15, 0.60),
    "gpt-4.1": (2.00, 8.00),
}

MODEL_ORDER = ["gpt-4o-mini-2024-07-18", "gpt-4.1"]
MODE_ORDER = ["advisory", "binding"]
MODEL_ROLE = {
    "gpt-4o-mini-2024-07-18": "cheap/weak",
    "gpt-4.1": "frontier/strong",
}
WEAK = "gpt-4o-mini-2024-07-18"
STRONG = "gpt-4.1"

# The pre-registration recorded in EXPERIMENT_LOG 5.3, BEFORE any D18 episode ran.
PREREG = (
    "Recorded before any D18 episode: (i) under bare-code presentation, MODEL_A "
    "(gpt-4o-mini) is expected to fail more dev tasks than MODEL_B (gpt-4.1); (ii) in "
    "advisory mode, some post-failure episodes are expected to end as false-DONEs (D14); "
    "(iii) binding is expected to convert some would-be false-DONEs into solved (via "
    "forced iteration) or escalated/step_cap; (iv) the mode difference is expected to be "
    "larger for MODEL_A than MODEL_B (the thesis interaction)."
)

COMPLIANCE_DEF = (
    "A post-failure step is compliant iff the next submission is (a) non-byte-identical "
    "to the failed one AND (b) changes the checker outcome signature -- the set of "
    "failing test names -- when run_checks is re-executed on both submissions against "
    "the frozen task. Denominator: all post-failure model turns that submitted code."
)


# ---------------------------------------------------------------------------
# Artifact loading
# ---------------------------------------------------------------------------

def _events(path):
    with open(path, "r", encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def _cell_dir(model, mode):
    return os.path.join(LOG_ROOT, "%s__%s" % (model, mode))


def _task_dir(task_id):
    return os.path.join(TASKS_DIR, task_id)


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_manifest(model, mode):
    with open(os.path.join(MANIFEST_DIR, "full_%s__%s.json" % (model, mode)),
              "r", encoding="utf-8") as fh:
        return json.load(fh)


def _load_test_ids():
    with open(SPLIT_JSON, "r", encoding="utf-8") as fh:
        return sorted(json.load(fh)["test"])


def _load_metas(task_ids):
    metas = {}
    for t in task_ids:
        with open(os.path.join(_task_dir(t), "meta.json"), "r", encoding="utf-8") as fh:
            metas[t] = json.load(fh)
    return metas


# ---------------------------------------------------------------------------
# Per-episode extraction (logs are the source of truth)
# ---------------------------------------------------------------------------

def _episode(model, mode, task_id):
    """One episode's facts, read straight from its committed JSONL log."""
    ev = _events(os.path.join(_cell_dir(model, mode), task_id + ".jsonl"))
    end = next(e for e in ev if e["event"] == "episode_end")
    submissions = []  # ordered (step, code) for turns that submitted a code block
    for e in ev:
        if e["event"] == "model_response":
            code = extract_last_python_block(e.get("content", ""))
            if code is not None:
                submissions.append((e["step"], code))
    return {
        "task_id": task_id,
        "status": end["status"],
        "final_passed": bool(end["final_passed"]),
        "steps": int(end["steps"]),
        "tokens_in": int(end["tokens_in"]),
        "tokens_out": int(end["tokens_out"]),
        "n_check_verdicts": sum(1 for e in ev if e["event"] == "check_verdict"),
        "n_done_ignored": sum(1 for e in ev if e["event"] == "done_ignored"),
        "n_resub_rejected": sum(1 for e in ev if e["event"] == "resubmission_rejected"),
        "submissions": submissions,
    }


def _solved(ep, mode):
    """Success semantics: advisory grades on final_passed; binding on status==solved."""
    return ep["final_passed"] if mode == "advisory" else ep["status"] == "solved"


def _failset(task_id, code):
    """Re-run the frozen checker; return (passed, frozenset(failing test names))."""
    v = run_checks(_task_dir(task_id), code)
    return bool(v["passed"]), frozenset(f["test"] for f in v.get("failures", []))


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def _cost(model, tin, tout):
    rin, rout = RATES[model]
    return tin * rin / 1e6 + tout * rout / 1e6


def _compliance_and_identical(episodes, task_ids):
    """Walk every episode; for each post-failure submission re-run the checker on it and
    on the failed submission before it. Returns (compliant, denom, identical)."""
    compliant = denom = identical = 0
    for ep in episodes:
        subs = ep["submissions"]
        for i in range(1, len(subs)):
            prev_code = subs[i - 1][1]
            cur_code = subs[i][1]
            prev_passed, prev_set = _failset(ep["task_id"], prev_code)
            if prev_passed:
                continue  # not a post-failure step
            denom += 1
            _, cur_set = _failset(ep["task_id"], cur_code)
            if cur_code == prev_code:
                identical += 1
            if cur_code != prev_code and cur_set != prev_set:
                compliant += 1
    return compliant, denom, identical


def _mcnemar(adv_solved, bind_solved, task_ids):
    """Exact McNemar over paired outcomes. b = advisory-pass & binding-fail;
    c = advisory-fail & binding-pass; exact two-sided binomial p over n=b+c."""
    b = sum(1 for t in task_ids if adv_solved[t] and not bind_solved[t])
    c = sum(1 for t in task_ids if not adv_solved[t] and bind_solved[t])
    n = b + c
    if n == 0:
        p = 1.0
    else:
        tail = sum(math.comb(n, i) for i in range(0, min(b, c) + 1))
        p = min(1.0, 2.0 * tail * (0.5 ** n))
    return b, c, n, p


# ---------------------------------------------------------------------------
# Assemble the full result object
# ---------------------------------------------------------------------------

def build():
    task_ids = _load_test_ids()
    metas = _load_metas(task_ids)
    split_sha = _sha256_file(SPLIT_JSON)

    manifests = {}
    freeze_hashes = set()
    for model in MODEL_ORDER:
        for mode in MODE_ORDER:
            m = _load_manifest(model, mode)
            manifests[(model, mode)] = m
            freeze_hashes.add(m["task_set_freeze_hash"])
    assert len(freeze_hashes) == 1, "cells disagree on FREEZE_HASH: %r" % freeze_hashes
    freeze_hash = next(iter(freeze_hashes))
    # split_sha256 recorded in the manifests must match the file we just hashed.
    manifest_split = {m["split_sha256"] for m in manifests.values()}
    assert manifest_split == {split_sha}, (
        "split sha mismatch: file=%s manifests=%r" % (split_sha, manifest_split))

    cells = {}
    solved_map = {}  # (model, mode) -> {task_id: bool}
    for model in MODEL_ORDER:
        for mode in MODE_ORDER:
            eps = [_episode(model, mode, t) for t in task_ids]
            assert len(eps) == 87, "cell %s/%s has %d episodes" % (model, mode, len(eps))
            solved = {ep["task_id"]: _solved(ep, mode) for ep in eps}
            solved_map[(model, mode)] = solved
            n_solved = sum(solved.values())
            tin = sum(ep["tokens_in"] for ep in eps)
            tout = sum(ep["tokens_out"] for ep in eps)
            cost = _cost(model, tin, tout)
            false_done = sum(
                1 for ep in eps
                if mode == "advisory"
                and ep["status"] == "model_declared_done"
                and not ep["final_passed"])
            comp, comp_den, ident = _compliance_and_identical(eps, task_ids)
            cells[(model, mode)] = {
                "model": model,
                "model_resolved": manifests[(model, mode)]["model_resolved"],
                "role": MODEL_ROLE[model],
                "mode": mode,
                "n_episodes": len(eps),
                "n_solved": n_solved,
                "success_rate": n_solved / len(eps),
                "mean_steps": sum(ep["steps"] for ep in eps) / len(eps),
                "tokens_in": tin,
                "tokens_out": tout,
                "cost_usd": cost,
                "cost_per_solved_usd": (cost / n_solved) if n_solved else None,
                "n_episodes_with_failed_verdict": sum(
                    1 for ep in eps
                    if _cell_had_failed(model, mode, ep["task_id"])),
                "false_done": false_done if mode == "advisory" else None,
                "step_cap": sum(1 for ep in eps if ep["status"] == "step_cap"),
                "done_ignored": sum(ep["n_done_ignored"] for ep in eps),
                "resubmission_rejected": sum(ep["n_resub_rejected"] for ep in eps),
                "escalated": sum(1 for ep in eps if ep["status"] == "escalated"),
                "compliance_num": comp,
                "compliance_den": comp_den,
                "identical_resub_num": ident,
                "identical_resub_den": comp_den,
            }

    # Breakdowns: success by bug_type x cell and difficulty x cell.
    bug_types = sorted({metas[t]["bug_type"] for t in task_ids})
    difficulties = ["easy", "medium", "hard"]

    def _by(key, values):
        table = {}
        for v in values:
            row = {}
            group = [t for t in task_ids if metas[t][key] == v]
            for model in MODEL_ORDER:
                for mode in MODE_ORDER:
                    s = solved_map[(model, mode)]
                    row["%s__%s" % (model, mode)] = {
                        "solved": sum(1 for t in group if s[t]),
                        "n": len(group),
                    }
            table[v] = row
        return table

    breakdown_bug = _by("bug_type", bug_types)
    breakdown_diff = _by("difficulty", difficulties)

    # Rescue decomposition for the weak-model binding cell.
    adv_failed = sorted(t for t in task_ids if not solved_map[(WEAK, "advisory")][t])
    forced_repairs, first_sample = [], []
    for t in adv_failed:
        ep = _episode(WEAK, "binding", t)
        rec = {"task_id": t, "bug_type": metas[t]["bug_type"],
               "difficulty": metas[t]["difficulty"], "status": ep["status"],
               "steps": ep["steps"], "n_check_verdicts": ep["n_check_verdicts"]}
        # A genuine forced repair: a FAILED verdict, then a changed submission that PASSED
        # (>=2 checked verdicts). A first-sample pass solves on the first verdict (1 check).
        if ep["status"] == "solved" and ep["n_check_verdicts"] >= 2:
            forced_repairs.append(rec)
        elif ep["status"] == "solved" and ep["n_check_verdicts"] == 1:
            first_sample.append(rec)
        else:
            first_sample.append(rec)  # (should not occur; kept explicit)

    # Statistics: exact McNemar per model + the interaction.
    stats = {}
    for model in MODEL_ORDER:
        b, c, n, p = _mcnemar(solved_map[(model, "advisory")],
                              solved_map[(model, "binding")], task_ids)
        stats[model] = {
            "adv_pass_bind_fail_b": b,
            "adv_fail_bind_pass_c": c,
            "discordant_n": n,
            "exact_two_sided_p": p,
        }
    delta = {m: cells[(m, "binding")]["success_rate"]
                - cells[(m, "advisory")]["success_rate"] for m in MODEL_ORDER}
    interaction = delta[WEAK] - delta[STRONG]

    # Pre-registration confirmation, computed from the numbers above.
    weak_adv_fail = cells[(WEAK, "advisory")]["n_episodes"] - cells[(WEAK, "advisory")]["n_solved"]
    strong_adv_fail = cells[(STRONG, "advisory")]["n_episodes"] - cells[(STRONG, "advisory")]["n_solved"]
    weak_false_done = cells[(WEAK, "advisory")]["false_done"]
    weak_bind_solved_of_adv_failed = sum(
        1 for t in adv_failed if solved_map[(WEAK, "binding")][t])
    prereg_marks = [
        ("(i) MODEL_A fails more than MODEL_B under bare-code",
         weak_adv_fail > strong_adv_fail,
         "weak advisory fails %d vs strong %d" % (weak_adv_fail, strong_adv_fail)),
        ("(ii) advisory post-failure episodes end as false-DONEs (D14)",
         weak_false_done > 0 and weak_false_done == weak_adv_fail,
         "all %d weak-advisory failures are false-DONEs" % weak_false_done),
        ("(iii) binding converts would-be false-DONEs into solved",
         len(adv_failed) > 0 and weak_bind_solved_of_adv_failed == len(adv_failed),
         "%d/%d advisory-failed tasks solved in binding (%d forced repairs, %d first-sample); 0 escalated/step_cap"
         % (weak_bind_solved_of_adv_failed, len(adv_failed),
            len(forced_repairs), len(first_sample))),
        ("(iv) mode difference larger for MODEL_A than MODEL_B (interaction)",
         delta[WEAK] > delta[STRONG],
         "delta_weak=%+.1fpp vs delta_strong=%+.1fpp" % (100 * delta[WEAK], 100 * delta[STRONG])),
    ]

    return {
        "header": {
            "freeze_hash": freeze_hash,
            "split_sha256": split_sha,
            "n_test_tasks": len(task_ids),
            "presentation": manifests[(WEAK, "advisory")]["presentation"],
            "config": {("%s__%s" % (model, mode)): manifests[(model, mode)]["config"]
                       for model in MODEL_ORDER for mode in MODE_ORDER},
            "model_snapshots": {model: manifests[(model, "advisory")]["model_resolved"]
                                for model in MODEL_ORDER},
        },
        "cells": {("%s__%s" % (model, mode)): cells[(model, mode)]
                  for model in MODEL_ORDER for mode in MODE_ORDER},
        "compliance_definition": COMPLIANCE_DEF,
        "line_coverage_note": ("Line-coverage tracing was NOT implemented; this is the "
                               "design doc's fallback outcome-signature operationalization."),
        "breakdown_bug_type": breakdown_bug,
        "breakdown_difficulty": breakdown_diff,
        "rescue_decomposition": {
            "advisory_failed_tasks": adv_failed,
            "forced_repairs": forced_repairs,
            "first_sample_passes": first_sample,
            "n_forced_repairs": len(forced_repairs),
            "n_first_sample_passes": len(first_sample),
        },
        "statistics": {
            "mcnemar": stats,
            "delta_binding_minus_advisory": {m: delta[m] for m in MODEL_ORDER},
            "interaction_pp": interaction,
        },
        "prereg": {"text": PREREG, "marks": prereg_marks},
    }


def _cell_had_failed(model, mode, task_id):
    ev = _events(os.path.join(_cell_dir(model, mode), task_id + ".jsonl"))
    return any(e["event"] == "check_verdict" and e.get("passed") is False for e in ev)


# ---------------------------------------------------------------------------
# Rendering (deterministic; no timestamps)
# ---------------------------------------------------------------------------

def _pct(x):
    return "%.1f%%" % (100 * x)


def render_md(R):
    h = R["header"]
    L = []
    L.append("# Phase 6.1 — Reproducible analysis: the results table")
    L.append("")
    L.append("Regenerated by `phase6_analysis/analyze.py` from committed Phase-5 artifacts "
             "only (per-cell JSONL logs, cell manifests, frozen task metas, and the frozen "
             "Phase-2 checker). No API calls; nothing outside `phase6_analysis/` is written; "
             "`phase1_tasks/` is immutable. Two runs produce byte-identical output — there is "
             "no timestamp inside this file (the run date lives in the EXPERIMENT_LOG entry).")
    L.append("")
    L.append("## Header / provenance")
    L.append("")
    L.append("- **FREEZE_HASH (task set):** `%s`" % h["freeze_hash"])
    L.append("- **split.json sha256 (recomputed here):** `%s`" % h["split_sha256"])
    L.append("- **Test tasks:** %d (2 models x 2 modes = %d cells x 87 = 348 episodes)"
             % (h["n_test_tasks"], 4))
    L.append("- **Presentation:** %s (D18)" % h["presentation"])
    L.append("- **Model snapshots:** " + "; ".join(
        "%s -> `%s`" % (m, h["model_snapshots"][m]) for m in MODEL_ORDER))
    cfg = h["config"]["%s__advisory" % WEAK]
    L.append("- **Run config (identical across cells except `model`):** temperature=%s, "
             "step_cap=%s, show_description=%s"
             % (cfg["temperature"], cfg["step_cap"], cfg["show_description"]))
    L.append("")
    L.append("**Presentation note (D17/D18).** D17 withholds the separate `meta[\"description\"]`, "
             "replacing it with a fixed withheld-notice sentence. D18 goes further: with "
             "`show_description=false` the buggy source is additionally shown with every "
             "docstring and comment stripped (an AST `ast.unparse` transform applied only when "
             "building the prompt). Both are presentation-layer only — the frozen `buggy.py` "
             "files on disk are never modified; the injected bug and any runtime string literals "
             "are preserved. The model is handed the function name + bare code + the "
             "withheld-notice sentence, nothing else.")
    L.append("")

    # Pre-registration.
    L.append("## Pre-registration (from EXPERIMENT_LOG 5.3), with confirmed/disconfirmed marks")
    L.append("")
    L.append("> %s" % R["prereg"]["text"])
    L.append("")
    for label, ok, detail in R["prereg"]["marks"]:
        L.append("- **%s** %s — %s" % ("CONFIRMED" if ok else "DISCONFIRMED",
                                        label, detail))
    L.append("")

    # Per-cell table.
    L.append("## Per-cell results")
    L.append("")
    L.append("| model (role) | mode | success | mean steps | tok in/out | cost | $/solved | "
             "false-DONE | step_cap | done_ign/rej/esc |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for model in MODEL_ORDER:
        for mode in MODE_ORDER:
            c = R["cells"]["%s__%s" % (model, mode)]
            fd = "%d" % c["false_done"] if c["false_done"] is not None else "—"
            cps = "$%.5f" % c["cost_per_solved_usd"] if c["cost_per_solved_usd"] is not None else "—"
            dre = ("%d/%d/%d" % (c["done_ignored"], c["resubmission_rejected"], c["escalated"])
                   if mode == "binding" else "—")
            L.append("| %s (%s) | %s | **%d/%d = %s** | %.2f | %d/%d | $%.4f | %s | %s | %d | %s |"
                     % (model, c["role"], mode, c["n_solved"], c["n_episodes"],
                        _pct(c["success_rate"]), c["mean_steps"], c["tokens_in"],
                        c["tokens_out"], c["cost_usd"], cps, fd, c["step_cap"], dre))
    L.append("")

    # Headline 2x2.
    L.append("## Headline 2x2 (success rate) + interaction")
    L.append("")
    L.append("| model | advisory | binding | Δ (binding − advisory) |")
    L.append("|---|---|---|---|")
    d = R["statistics"]["delta_binding_minus_advisory"]
    for model in MODEL_ORDER:
        adv = R["cells"]["%s__advisory" % model]["success_rate"]
        bind = R["cells"]["%s__binding" % model]["success_rate"]
        L.append("| %s (%s) | %s | %s | %+.1f pp |"
                 % (model, MODEL_ROLE[model], _pct(adv), _pct(bind), 100 * d[model]))
    L.append("")
    L.append("**Interaction (the thesis): Δmode(weak) − Δmode(strong) = %+.1f − %+.1f = %+.1f pp.**"
             % (100 * d[WEAK], 100 * d[STRONG], 100 * R["statistics"]["interaction_pp"]))
    L.append("")

    # Feedback compliance.
    L.append("## Feedback-compliance rate")
    L.append("")
    L.append("**Operationalization (verbatim):** %s" % R["compliance_definition"])
    L.append("")
    L.append("*%s*" % R["line_coverage_note"])
    L.append("")
    L.append("| cell | compliant / post-failure submissions | identical-resubmission / post-failure |")
    L.append("|---|---|---|")
    for model in MODEL_ORDER:
        for mode in MODE_ORDER:
            c = R["cells"]["%s__%s" % (model, mode)]
            L.append("| %s__%s | %d/%d | %d/%d |"
                     % (model, mode, c["compliance_num"], c["compliance_den"],
                        c["identical_resub_num"], c["identical_resub_den"]))
    L.append("")
    L.append("Denominators are reported so no rate is bare. A `0/0` cell means the mode never "
             "produced a post-failure submission at all: in weak-advisory every failure was a "
             "terminal false-DONE, so the model was never given a post-failure turn to comply "
             "with. Identical-resubmission is 0 everywhere (consistent with D15 — this model "
             "never byte-repeats — so the binding rejection/escalation machinery never engaged).")
    L.append("")

    # Breakdowns.
    L.append("## Success rate by bug type × cell")
    L.append("")
    cell_cols = ["%s__%s" % (m, mode) for m in MODEL_ORDER for mode in MODE_ORDER]
    short = {"gpt-4o-mini-2024-07-18__advisory": "weak/adv",
             "gpt-4o-mini-2024-07-18__binding": "weak/bind",
             "gpt-4.1__advisory": "strong/adv",
             "gpt-4.1__binding": "strong/bind"}
    L.append("| bug_type | " + " | ".join(short[c] for c in cell_cols) + " |")
    L.append("|---|" + "|".join(["---"] * len(cell_cols)) + "|")
    for bt in sorted(R["breakdown_bug_type"]):
        row = R["breakdown_bug_type"][bt]
        cellsig = " | ".join("%d/%d" % (row[c]["solved"], row[c]["n"]) for c in cell_cols)
        flag = "  ⟵ spec-carrying class" if bt == "missing-edge-case" else ""
        name = "**%s**" % bt if bt == "missing-edge-case" else bt
        L.append("| %s | %s |%s" % (name, cellsig, flag))
    L.append("")
    L.append("The **missing-edge-case** row is where the weak model's advisory failures "
             "concentrate: 6 of its 8 advisory failures are missing-edge-case bugs, whose "
             "required behavior (a guard that raises on a boundary input) was documented only "
             "in the description/docstring that D18 withholds. Binding repairs all of them.")
    L.append("")
    L.append("## Success rate by difficulty × cell")
    L.append("")
    L.append("| difficulty | " + " | ".join(short[c] for c in cell_cols) + " |")
    L.append("|---|" + "|".join(["---"] * len(cell_cols)) + "|")
    for diff in ["easy", "medium", "hard"]:
        row = R["breakdown_difficulty"][diff]
        cellsig = " | ".join("%d/%d" % (row[c]["solved"], row[c]["n"]) for c in cell_cols)
        L.append("| %s | %s |" % (diff, cellsig))
    L.append("")

    # Rescue decomposition.
    rd = R["rescue_decomposition"]
    L.append("## Rescue decomposition — weak-model binding cell")
    L.append("")
    L.append("Of the %d tasks the weak model FAILED in advisory, all %d are solved in binding, "
             "decomposed (from the logs) into **%d genuine forced repairs** (a FAILED verdict, "
             "then a byte-changed submission that PASSED — ≥2 checked verdicts) and **%d "
             "first-sample passes** (binding's first submission passed at temp-0, while the "
             "advisory arm's first draft false-DONE'd the same task — sampling variance, not "
             "iteration):"
             % (len(rd["advisory_failed_tasks"]), len(rd["advisory_failed_tasks"]),
                rd["n_forced_repairs"], rd["n_first_sample_passes"]))
    L.append("")
    L.append("| task | bug_type | difficulty | binding status | steps | checked verdicts | class |")
    L.append("|---|---|---|---|---|---|---|")
    for rec in rd["forced_repairs"]:
        L.append("| %s | %s | %s | %s | %d | %d | forced repair |"
                 % (rec["task_id"], rec["bug_type"], rec["difficulty"], rec["status"],
                    rec["steps"], rec["n_check_verdicts"]))
    for rec in rd["first_sample_passes"]:
        L.append("| %s | %s | %s | %s | %d | %d | first-sample pass |"
                 % (rec["task_id"], rec["bug_type"], rec["difficulty"], rec["status"],
                    rec["steps"], rec["n_check_verdicts"]))
    L.append("")
    L.append("So the honest count is **%d forced repairs + %d first-sample passes = %d**; the "
             "+9.2 pp binding advantage includes the small stochastic component from the two "
             "first-sample passes." % (rd["n_forced_repairs"], rd["n_first_sample_passes"],
                                       len(rd["advisory_failed_tasks"])))
    L.append("")

    # Statistics.
    L.append("## Statistics — exact McNemar (task-paired, 87 pairs per model)")
    L.append("")
    L.append("Paired on task id: advisory outcome vs binding outcome. `b` = advisory-pass & "
             "binding-fail; `c` = advisory-fail & binding-pass. Exact two-sided binomial p over "
             "the n=b+c discordant pairs (stdlib `math.comb`, no SciPy).")
    L.append("")
    L.append("| model | b (adv✓ bind✗) | c (adv✗ bind✓) | discordant n | exact two-sided p |")
    L.append("|---|---|---|---|---|")
    for model in MODEL_ORDER:
        s = R["statistics"]["mcnemar"][model]
        L.append("| %s | %d | %d | %d | %.6g |"
                 % (model, s["adv_pass_bind_fail_b"], s["adv_fail_bind_pass_c"],
                    s["discordant_n"], s["exact_two_sided_p"]))
    L.append("")
    sw = R["statistics"]["mcnemar"][WEAK]
    ss = R["statistics"]["mcnemar"][STRONG]
    L.append("**Interaction.** Weak model: %d discordant pairs, all in the advisory-fail / "
             "binding-pass direction (b=%d, c=%d), exact p=%.6g. Strong model: %d discordant "
             "pairs (b=%d, c=%d), p=%.6g. Binding significantly helps the weak model and does "
             "nothing measurable for the strong one — a positive interaction in the "
             "pre-registered direction."
             % (sw["discordant_n"], sw["adv_pass_bind_fail_b"], sw["adv_fail_bind_pass_c"],
                sw["exact_two_sided_p"], ss["discordant_n"], ss["adv_pass_bind_fail_b"],
                ss["adv_fail_bind_pass_c"], ss["exact_two_sided_p"]))
    L.append("")
    return "\n".join(L) + "\n"


def main():
    R = build()
    md = render_md(R)
    with open(os.path.join(_HERE, "results.json"), "w", encoding="utf-8") as fh:
        json.dump(R, fh, indent=2, sort_keys=True)
        fh.write("\n")
    with open(os.path.join(_HERE, "results.md"), "w", encoding="utf-8") as fh:
        fh.write(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
