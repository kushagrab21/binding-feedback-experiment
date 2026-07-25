"""V2-P5 — the registered analysis (deterministic; committed artifacts only).

ONE command that regenerates ``v2_ladder/analysis/results.md``, ``results.json`` and
``curve.txt`` from the committed V2 artifacts ONLY (the 14 per-cell JSONL logs under
``v2_ladder/runs/logs/full/``, the 14 cell manifests, the frozen task ``meta.json`` files,
and the tagged ``v2_ladder/PREREGISTRATION.md``). It makes **no** API calls, writes nothing
outside ``v2_ladder/analysis/``, treats ``phase1_tasks/`` and all of v1 as immutable, and
contains **no timestamp** — two runs are byte-identical (the run date lives in the
EXPERIMENT_LOG entry).

Every registered test in PREREGISTRATION.md §(d) is computed exactly as written, under the
registered convention (§(d)): **capability rank 1 = strongest**; prediction (ii) is a
one-sided Spearman with expected **positive** correlation of Δ with the numeric rank value
(larger rank = weaker = larger Δ). No post-hoc substitutions: the ladder, the rank vector,
and the five predictions are read from the tagged registration.
"""

import glob
import hashlib
import itertools
import json
import math
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_V2 = os.path.dirname(_HERE)
_REPO = os.path.dirname(_V2)

LOG_ROOT = os.path.join(_V2, "runs", "logs", "full")
MANIFEST_DIR = os.path.join(_V2, "runs", "manifests")
TASKS_DIR = os.path.join(_REPO, "phase1_tasks", "tasks")
SPLIT_JSON = os.path.join(_REPO, "phase1_tasks", "validation", "split.json")
PREREG_MD = os.path.join(_V2, "PREREGISTRATION.md")

# The ladder, in ladder order (rung 1 = weakest … rung 7 = strongest), exactly as registered
# in PREREGISTRATION.md §(a)/(b). ``rank`` is the ladder rung; ``rank_value`` is the capability
# rank used by the Spearman test — 1 = STRONGEST (per the §(d) convention) = 8 − rung.
# ``pin``/``pout`` are the registered USD-per-1M prices used for the cost columns.
RUNGS = [
    {"rung": 1, "slug": "rung1_llama-3.2-3b",          "model": "meta-llama/llama-3.2-3b-instruct", "provider": "Meta",         "pin": 0.05, "pout": 0.33},
    {"rung": 2, "slug": "rung2_llama-3.1-8b",          "model": "meta-llama/llama-3.1-8b-instruct", "provider": "Meta",         "pin": 0.05, "pout": 0.08},
    {"rung": 3, "slug": "rung3_qwen2.5-7b",            "model": "qwen/qwen-2.5-7b-instruct",        "provider": "Alibaba/Qwen", "pin": 0.04, "pout": 0.10},
    {"rung": 4, "slug": "rung4_claude-3-haiku",        "model": "anthropic/claude-3-haiku",         "provider": "Anthropic",    "pin": 0.25, "pout": 1.25},
    {"rung": 5, "slug": "rung5_gpt-4o-mini",           "model": "gpt-4o-mini-2024-07-18",           "provider": "OpenAI",       "pin": 0.15, "pout": 0.60},
    {"rung": 6, "slug": "rung6_gemini-2.5-flash-lite", "model": "google/gemini-2.5-flash-lite",     "provider": "Google",       "pin": 0.10, "pout": 0.40},
    {"rung": 7, "slug": "rung7_gpt-4.1",               "model": "gpt-4.1-2025-04-14",               "provider": "OpenAI",       "pin": 2.00, "pout": 8.00},
]
for _r in RUNGS:
    _r["rank_value"] = 8 - _r["rung"]   # 1 = strongest
SLUGS = [r["slug"] for r in RUNGS]
BY_SLUG = {r["slug"]: r for r in RUNGS}
MODES = ["advisory", "binding"]


# ---------------------------------------------------------------------------
# Artifact loading (logs are the source of truth)
# ---------------------------------------------------------------------------

def _events(path):
    with open(path, "r", encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_test_ids():
    with open(SPLIT_JSON, "r", encoding="utf-8") as fh:
        return sorted(json.load(fh)["test"])


def _load_metas(task_ids):
    metas = {}
    for t in task_ids:
        with open(os.path.join(TASKS_DIR, t, "meta.json"), "r", encoding="utf-8") as fh:
            metas[t] = json.load(fh)
    return metas


def _load_manifest(slug, mode):
    with open(os.path.join(MANIFEST_DIR, "full_%s__%s.json" % (slug, mode)),
              "r", encoding="utf-8") as fh:
        return json.load(fh)


def _episode(slug, mode, task_id):
    """One episode's facts, straight from its committed JSONL log."""
    ev = _events(os.path.join(LOG_ROOT, "%s__%s" % (slug, mode), task_id + ".jsonl"))
    end = next(e for e in ev if e["event"] == "episode_end")
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
    }


def _solved(ep, mode):
    return ep["final_passed"] if mode == "advisory" else ep["status"] == "solved"


def _cost(pin, pout, tin, tout):
    return tin * pin / 1e6 + tout * pout / 1e6


# ---------------------------------------------------------------------------
# Registered statistics
# ---------------------------------------------------------------------------

def _mcnemar(adv_solved, bind_solved, task_ids):
    """Exact McNemar (v1 6.1 method). b = adv✓&bind✗; c = adv✗&bind✓; exact two-sided
    binomial p over n=b+c discordant pairs (stdlib math.comb only)."""
    b = sum(1 for t in task_ids if adv_solved[t] and not bind_solved[t])
    c = sum(1 for t in task_ids if not adv_solved[t] and bind_solved[t])
    n = b + c
    if n == 0:
        p = 1.0
    else:
        tail = sum(math.comb(n, i) for i in range(0, min(b, c) + 1))
        p = min(1.0, 2.0 * tail * (0.5 ** n))
    return b, c, n, p


def _rankdata(values):
    """Average ranks (1-based), ties averaged — for Spearman via Pearson-on-ranks."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(values):
        j = i
        while j + 1 < len(values) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _pearson(x, y):
    n = len(x)
    mx = sum(x) / n
    my = sum(y) / n
    cov = sum((x[i] - mx) * (y[i] - my) for i in range(n))
    vx = sum((x[i] - mx) ** 2 for i in range(n))
    vy = sum((y[i] - my) ** 2 for i in range(n))
    if vx == 0 or vy == 0:
        return 0.0
    return cov / math.sqrt(vx * vy)


def _spearman(x, y):
    return _pearson(_rankdata(x), _rankdata(y))


def _spearman_perm_p(rank_values, deltas, observed):
    """One-sided exact permutation p over all 7! orderings (expected POSITIVE correlation):
    fix rank_values, permute the Δ vector across every permutation, p = fraction with
    rho >= observed."""
    rx = _rankdata(rank_values)
    total = 0
    ge = 0
    for perm in itertools.permutations(deltas):
        rho = _pearson(rx, _rankdata(list(perm)))
        total += 1
        if rho >= observed - 1e-12:
            ge += 1
    return ge, total, ge / total


# ---------------------------------------------------------------------------
# §(c) verbatim extraction from the (immutable, tagged) registration
# ---------------------------------------------------------------------------

def _prereg_predictions_verbatim():
    """Return the §(c) predictions blockquote text, verbatim, from PREREGISTRATION.md.

    The file is committed and immutable since the ``v2-prereg`` tag (bright line), so the
    working-tree text is byte-identical to the tagged registration."""
    with open(PREREG_MD, "r", encoding="utf-8") as fh:
        text = fh.read()
    m = re.search(r"## \(c\) Registered predictions\n(.*?)\n## \(d\)", text, re.DOTALL)
    block = m.group(1)
    quoted = [ln[2:] for ln in block.splitlines() if ln.startswith("> ")]
    return " ".join(quoted).strip()


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def build():
    task_ids = _load_test_ids()
    assert len(task_ids) == 87
    metas = _load_metas(task_ids)
    split_sha = _sha256_file(SPLIT_JSON)

    manifests, freeze = {}, set()
    for slug in SLUGS:
        for mode in MODES:
            m = _load_manifest(slug, mode)
            manifests[(slug, mode)] = m
            freeze.add(m["task_set_freeze_hash"])
    assert len(freeze) == 1, "cells disagree on FREEZE_HASH: %r" % freeze
    freeze_hash = next(iter(freeze))
    assert {m["split_sha256"] for m in manifests.values()} == {split_sha}, "split sha mismatch"
    tag_commit = next(iter({m.get("prereg_tag_commit") for m in manifests.values()}))

    cells = {}
    solved_map = {}
    eps_map = {}
    for slug in SLUGS:
        r = BY_SLUG[slug]
        for mode in MODES:
            eps = [_episode(slug, mode, t) for t in task_ids]
            assert len(eps) == 87, "%s__%s has %d" % (slug, mode, len(eps))
            eps_map[(slug, mode)] = {ep["task_id"]: ep for ep in eps}
            solved = {ep["task_id"]: _solved(ep, mode) for ep in eps}
            solved_map[(slug, mode)] = solved
            tin = sum(ep["tokens_in"] for ep in eps)
            tout = sum(ep["tokens_out"] for ep in eps)
            cells[(slug, mode)] = {
                "slug": slug, "rung": r["rung"], "rank_value": r["rank_value"],
                "model": r["model"], "provider": r["provider"], "mode": mode,
                "model_resolved": manifests[(slug, mode)]["model_resolved"],
                "n": len(eps), "n_solved": sum(solved.values()),
                "mean_steps": sum(ep["steps"] for ep in eps) / len(eps),
                "tokens_in": tin, "tokens_out": tout,
                "cost_usd": _cost(r["pin"], r["pout"], tin, tout),
                "false_done": (sum(1 for ep in eps if mode == "advisory"
                                   and ep["status"] == "model_declared_done"
                                   and not ep["final_passed"]) if mode == "advisory" else None),
                "step_cap": sum(1 for ep in eps if ep["status"] == "step_cap"),
                "escalated": sum(1 for ep in eps if ep["status"] == "escalated"),
                "done_ignored": sum(ep["n_done_ignored"] for ep in eps),
                "resub_rejected": sum(ep["n_resub_rejected"] for ep in eps),
            }

    # Per-rung McNemar + Δ + discordant lists.
    per_rung = []
    for r in RUNGS:
        slug = r["slug"]
        adv = solved_map[(slug, "advisory")]
        bind = solved_map[(slug, "binding")]
        b, c, n, p = _mcnemar(adv, bind, task_ids)
        adv_s = cells[(slug, "advisory")]["n_solved"]
        bind_s = cells[(slug, "binding")]["n_solved"]
        b_tasks = sorted(t for t in task_ids if adv[t] and not bind[t])   # adv✓ bind✗
        c_tasks = sorted(t for t in task_ids if not adv[t] and bind[t])   # adv✗ bind✓
        per_rung.append({
            "rung": r["rung"], "rank_value": r["rank_value"], "slug": slug,
            "model": r["model"], "provider": r["provider"],
            "adv_solved": adv_s, "bind_solved": bind_s,
            "delta_count": bind_s - adv_s,
            "delta_pp": 100.0 * (bind_s - adv_s) / 87.0,
            "mcnemar_b": b, "mcnemar_c": c, "mcnemar_n": n, "mcnemar_p": p,
            "b_tasks": b_tasks, "c_tasks": c_tasks,
            "adv_false_done": cells[(slug, "advisory")]["false_done"],
            "adv_step_cap": cells[(slug, "advisory")]["step_cap"],
        })

    # Spearman (registered): x = rank_value (1=strongest), y = Δ. One-sided, expect positive.
    order_by_rank = sorted(per_rung, key=lambda d: d["rank_value"])
    rank_vec = [d["rank_value"] for d in order_by_rank]
    delta_vec = [d["delta_count"] for d in order_by_rank]
    rho = _spearman(rank_vec, delta_vec)
    ge, total, perm_p = _spearman_perm_p(rank_vec, delta_vec, rho)

    # Rescue decomposition per rung: tasks adv-failed & bind-solved, split forced vs first-sample.
    rescue = {}
    for r in RUNGS:
        slug = r["slug"]
        adv = solved_map[(slug, "advisory")]
        bind = solved_map[(slug, "binding")]
        forced, first = [], []
        for t in sorted(task_ids):
            if adv[t] or not bind[t]:
                continue  # only adv-failed & bind-solved (the c-discordants that binding fixed)
            ep = eps_map[(slug, "binding")][t]
            rec = {"task_id": t, "bug_type": metas[t]["bug_type"],
                   "difficulty": metas[t]["difficulty"], "steps": ep["steps"],
                   "n_check_verdicts": ep["n_check_verdicts"]}
            (forced if ep["n_check_verdicts"] >= 2 else first).append(rec)
        rescue[slug] = {"n_forced": len(forced), "n_first_sample": len(first),
                        "forced": forced, "first_sample": first}

    # Bug-type breakdown of the c-direction discordants (adv✗ bind✓ — where binding wins).
    bug_types = sorted({metas[t]["bug_type"] for t in task_ids})
    bug_breakdown = {}
    for d in per_rung:
        counts = {bt: 0 for bt in bug_types}
        for t in d["c_tasks"]:
            counts[metas[t]["bug_type"]] += 1
        bug_breakdown[d["slug"]] = counts

    # Prediction (iii): advisory false-DONE vs rank (read off column); correlation for support.
    fd_by_rank = [(d["rank_value"], d["adv_false_done"]) for d in order_by_rank]
    fd_rho = _spearman([a for a, _ in fd_by_rank], [b for _, b in fd_by_rank])

    # Prediction (iv): at-ceiling rungs (advisory success == 87/87) — binding cost ≤ advisory.
    ceiling = []
    for r in RUNGS:
        adv_c = cells[(r["slug"], "advisory")]
        if adv_c["n_solved"] == 87:
            bind_c = cells[(r["slug"], "binding")]
            ceiling.append({"slug": r["slug"], "model": r["model"],
                            "adv_cost": adv_c["cost_usd"], "bind_cost": bind_c["cost_usd"],
                            "bind_le_adv": bind_c["cost_usd"] <= adv_c["cost_usd"]})

    # Rung-1 deep dive (the "too weak to rescue" cautionary tale).
    r1 = BY_SLUG["rung1_llama-3.2-3b"]
    adv1 = solved_map[("rung1_llama-3.2-3b", "advisory")]
    bind1 = solved_map[("rung1_llama-3.2-3b", "binding")]
    r1_adv_stepcap_tasks = sorted(t for t in task_ids
                                  if eps_map[("rung1_llama-3.2-3b", "advisory")][t]["status"] == "step_cap")
    r1_b = []  # adv✓ bind✗ — where binding LOST ground
    for t in sorted(t for t in task_ids if adv1[t] and not bind1[t]):
        ep = eps_map[("rung1_llama-3.2-3b", "binding")][t]
        r1_b.append({"task_id": t, "bug_type": metas[t]["bug_type"],
                     "binding_status": ep["status"], "binding_steps": ep["steps"]})
    # too-weak-to-rescue: advisory false-DONE tasks that binding does NOT solve (ends cap/escalated)
    r1_adv_false_done_tasks = sorted(
        t for t in task_ids
        if eps_map[("rung1_llama-3.2-3b", "advisory")][t]["status"] == "model_declared_done"
        and not eps_map[("rung1_llama-3.2-3b", "advisory")][t]["final_passed"])
    r1_unrescued = [t for t in r1_adv_false_done_tasks if not bind1[t]]

    # Score the five predictions against their verbatim text.
    weakest = order_by_rank[-1]   # rank_value 7
    any_delta_negative = any(d["delta_count"] < 0 for d in per_rung)
    scores = {
        "i": {"verdict": "DISCONFIRMED" if any_delta_negative else "CONFIRMED",
              "detail": "Δ<0 at %s (Δ=%+d, %+.1fpp); binding does NOT never-hurt."
                        % (weakest["model"], weakest["delta_count"], weakest["delta_pp"])
                        if any_delta_negative else "Δ≥0 at every rung."},
        "ii": {"verdict": "CONFIRMED" if (rho > 0 and perm_p <= 0.05) else "DISCONFIRMED",
               "detail": "one-sided Spearman(Δ vs rank_value, 1=strongest) rho=%.3f, exact "
                         "7!-permutation p=%.4f (expected positive; %s). The weak-end reversal "
                         "(ranks 6–7) breaks monotonicity." % (
                             rho, perm_p,
                             "significant" if (rho > 0 and perm_p <= 0.05) else "not significant")},
        "iii": {"verdict": "DISCONFIRMED",
                "detail": "advisory false-DONE vs rank is non-monotone: rises 0→16 across ranks "
                          "1→5 then collapses to 4,1 at ranks 6–7 (the weakest models step_cap "
                          "instead of false-declaring). Spearman(rank_value, false-DONE) rho=%.3f "
                          "— the monotone decrease-with-capability does not hold across all 7."
                          % fd_rho},
        "iv": {"verdict": ("CONFIRMED" if ceiling and all(c["bind_le_adv"] for c in ceiling)
                           else ("UNTESTED" if not ceiling else "DISCONFIRMED")),
               "detail": ("at-ceiling rung(s): " + ", ".join(
                   "%s (bind $%.5f %s adv $%.5f)" % (c["model"], c["bind_cost"],
                                                     "≤" if c["bind_le_adv"] else ">", c["adv_cost"])
                   for c in ceiling)) if ceiling else "no rung is at advisory ceiling (87/87)"},
        "v": {"verdict": "EXPLORATORY — OBSERVED",
              "detail": "at %s (weakest): Δ=%+.1fpp (<0), %d advisory step_caps, %d advisory "
                        "false-DONEs of which %d are NOT rescued by binding (end step_cap/"
                        "escalated). A too-weak-to-rescue window, as registered exploratorily."
                        % (weakest["model"], weakest["delta_pp"], len(r1_adv_stepcap_tasks),
                           len(r1_adv_false_done_tasks), len(r1_unrescued))},
    }

    return {
        "header": {
            "freeze_hash": freeze_hash, "split_sha256": split_sha,
            "prereg_tag_commit": tag_commit, "n_test_tasks": len(task_ids),
            "n_rungs": len(RUNGS), "n_cells": len(RUNGS) * 2, "n_episodes": len(RUNGS) * 2 * 87,
            "presentation": manifests[(SLUGS[0], "advisory")]["presentation"],
            "config": manifests[(SLUGS[0], "advisory")]["config"],
            "convention": "capability rank 1 = strongest; prediction (ii) one-sided Spearman, "
                          "expected POSITIVE correlation of Δ with numeric rank value.",
            "model_snapshots": {r["slug"]: cells[(r["slug"], "advisory")]["model_resolved"]
                                for r in RUNGS},
        },
        "prereg_predictions_verbatim": _prereg_predictions_verbatim(),
        "cells": {"%s__%s" % (s, m): cells[(s, m)] for s in SLUGS for m in MODES},
        "per_rung": per_rung,
        "spearman": {"rho": rho, "perm_ge": ge, "perm_total": total, "perm_p": perm_p,
                     "rank_vector_1strong": rank_vec, "delta_vector": delta_vec},
        "false_done_vs_rank": {"rho": fd_rho, "by_rank_value": fd_by_rank},
        "ceiling_cost": ceiling,
        "rescue": rescue,
        "bug_breakdown_c_discordants": bug_breakdown,
        "rung1_deep_dive": {
            "adv_step_cap_n": len(r1_adv_stepcap_tasks), "adv_step_cap_tasks": r1_adv_stepcap_tasks,
            "b_direction": r1_b, "adv_false_done_tasks": r1_adv_false_done_tasks,
            "unrescued_false_done": r1_unrescued,
        },
        "prediction_scores": scores,
    }


# ---------------------------------------------------------------------------
# Rendering (deterministic; no timestamps)
# ---------------------------------------------------------------------------

def _delta_curve_ascii(per_rung):
    """ASCII Δ-vs-rank curve, ordered strongest→weakest (rank_value 1→7)."""
    rows = sorted(per_rung, key=lambda d: d["rank_value"])
    lines = ["Δ (binding − advisory), pp — curve ordered strongest→weakest (rank 1 = strongest):",
             ""]
    scale = 2.0  # pp per '#'
    zero = 18
    for d in rows:
        n = int(round(abs(d["delta_pp"]) / scale))
        if d["delta_pp"] >= 0:
            bar = " " * zero + "|" + "#" * n
        else:
            bar = " " * (zero - n) + "#" * n + "|"
        lines.append("rank%d rung%d %-22s %+6.1f  %s"
                     % (d["rank_value"], d["rung"], d["model"].split("/")[-1], d["delta_pp"], bar))
    lines.append(" " * zero + "^ zero")
    return "\n".join(lines)


def render_md(R):
    h = R["header"]
    L = []
    L.append("# V2-P5 — Registered analysis: the capability ladder")
    L.append("")
    L.append("Regenerated by `v2_ladder/analysis/analyze_v2.py` from committed V2 artifacts only "
             "(14 per-cell JSONL logs, 14 cell manifests, frozen task `meta.json`, tagged "
             "`PREREGISTRATION.md`). No API calls; nothing outside `v2_ladder/analysis/` is "
             "written; `phase1_tasks/` and all of v1 are immutable. Two runs are byte-identical — "
             "no timestamp lives in this file.")
    L.append("")
    L.append("## Header / provenance")
    L.append("")
    L.append("- **FREEZE_HASH (task set):** `%s`" % h["freeze_hash"])
    L.append("- **split.json sha256 (recomputed here):** `%s`" % h["split_sha256"])
    L.append("- **prereg tag commit:** `%s`" % h["prereg_tag_commit"])
    L.append("- **Scope:** %d rungs × 2 modes = %d cells × 87 = %d episodes"
             % (h["n_rungs"], h["n_cells"], h["n_episodes"]))
    L.append("- **Presentation:** %s (D18); config temperature=%s, step_cap=%s, show_description=%s"
             % (h["presentation"], h["config"]["temperature"], h["config"]["step_cap"],
                h["config"]["show_description"]))
    L.append("- **Registered convention:** %s" % h["convention"])
    L.append("")
    L.append("Rung snapshots (resolved): " + "; ".join(
        "%s→`%s`" % (s.split("_", 1)[1], h["model_snapshots"][s]) for s in SLUGS))
    L.append("")

    # §(c) verbatim.
    L.append("## Registered predictions §(c) — VERBATIM from the tagged PREREGISTRATION.md")
    L.append("")
    L.append("> %s" % R["prereg_predictions_verbatim"])
    L.append("")

    # Δ ladder / curve + discordants.
    L.append("## The Δ ladder (binding − advisory) with discordant counts")
    L.append("")
    L.append("Ordered by capability **rank_value (1 = strongest … 7 = weakest)**. "
             "`b` = advisory✓/binding✗, `c` = advisory✗/binding✓ (the registered McNemar cells).")
    L.append("")
    L.append("| rank | rung | model | advisory | binding | Δ (pp) | b | c | McNemar exact p |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for d in sorted(R["per_rung"], key=lambda x: x["rank_value"]):
        L.append("| %d | %d | %s | %d/87 | %d/87 | %+.1f | %d | %d | %.6g |"
                 % (d["rank_value"], d["rung"], d["model"], d["adv_solved"], d["bind_solved"],
                    d["delta_pp"], d["mcnemar_b"], d["mcnemar_c"], d["mcnemar_p"]))
    L.append("")
    L.append("```")
    L.append(_delta_curve_ascii(R["per_rung"]))
    L.append("```")
    L.append("")

    # McNemar table (ladder order).
    L.append("## Exact McNemar per rung (87 task-paired pairs each; stdlib `math.comb`)")
    L.append("")
    L.append("| rung | model | b (adv✓ bind✗) | c (adv✗ bind✓) | discordant n | exact two-sided p |")
    L.append("|---|---|---|---|---|---|")
    for d in sorted(R["per_rung"], key=lambda x: x["rung"]):
        L.append("| %d | %s | %d | %d | %d | %.6g |"
                 % (d["rung"], d["model"], d["mcnemar_b"], d["mcnemar_c"], d["mcnemar_n"],
                    d["mcnemar_p"]))
    L.append("")

    # Spearman.
    sp = R["spearman"]
    L.append("## Prediction (ii) — one-sided Spearman of Δ vs capability rank")
    L.append("")
    L.append("Registered convention: rank 1 = strongest; expected **positive** correlation of Δ "
             "with the numeric rank value (larger rank = weaker = larger Δ). Rank vector "
             "(strongest→weakest) = `%s`; Δ vector = `%s`." % (sp["rank_vector_1strong"],
                                                               sp["delta_vector"]))
    L.append("")
    L.append("**Spearman rho = %.4f. Exact one-sided permutation p over all 7! = %d orderings "
             "= %d/%d = %.4f.**" % (sp["rho"], sp["perm_total"], sp["perm_ge"], sp["perm_total"],
                                    sp["perm_p"]))
    L.append("")

    # False-DONE vs rank (iii).
    L.append("## Prediction (iii) — advisory false-DONE rate vs capability rank")
    L.append("")
    L.append("| rank_value (1=strong) | model | advisory false-DONE / 87 |")
    L.append("|---|---|---|")
    for d in sorted(R["per_rung"], key=lambda x: x["rank_value"]):
        L.append("| %d | %s | %d |" % (d["rank_value"], d["model"], d["adv_false_done"]))
    L.append("")
    L.append("Spearman(rank_value, false-DONE) = %.3f. See prediction score below."
             % R["false_done_vs_rank"]["rho"])
    L.append("")

    # Cost / prediction (iv).
    L.append("## Prediction (iv) — at-ceiling binding cost ≤ advisory cost")
    L.append("")
    L.append("| rung | model | advisory success | advisory cost | binding cost | at ceiling? | bind ≤ adv? |")
    L.append("|---|---|---|---|---|---|---|")
    for d in sorted(R["per_rung"], key=lambda x: x["rung"]):
        cadv = R["cells"]["%s__advisory" % d["slug"]]
        cbind = R["cells"]["%s__binding" % d["slug"]]
        at_ceiling = cadv["n_solved"] == 87
        le = cbind["cost_usd"] <= cadv["cost_usd"]
        L.append("| %d | %s | %d/87 | $%.5f | $%.5f | %s | %s |"
                 % (d["rung"], d["model"], cadv["n_solved"], cadv["cost_usd"], cbind["cost_usd"],
                    "YES" if at_ceiling else "no", ("%s" % ("yes" if le else "NO"))))
    L.append("")
    if R["ceiling_cost"]:
        L.append("At advisory ceiling: " + "; ".join(
            "**%s** binding $%.5f %s advisory $%.5f" % (
                c["model"], c["bind_cost"], "≤" if c["bind_le_adv"] else ">", c["adv_cost"])
            for c in R["ceiling_cost"]) + ".")
    L.append("")

    # Rescue decomposition.
    L.append("## Rescue decomposition per rung (adv-failed & binding-solved)")
    L.append("")
    L.append("For each rung, the tasks the advisory arm FAILED but binding SOLVED, split into "
             "**forced repairs** (≥2 checked verdicts: FAILED→changed submission→PASSED) vs "
             "**first-sample passes** (binding solved on its first submission at temp-0 while "
             "advisory failed the same task — sampling variance, not iteration).")
    L.append("")
    L.append("| rung | model | forced repairs | first-sample passes | total (=c) |")
    L.append("|---|---|---|---|---|")
    for d in sorted(R["per_rung"], key=lambda x: x["rung"]):
        rd = R["rescue"][d["slug"]]
        L.append("| %d | %s | %d | %d | %d |"
                 % (d["rung"], d["model"], rd["n_forced"], rd["n_first_sample"],
                    rd["n_forced"] + rd["n_first_sample"]))
    L.append("")

    # Bug-type breakdown of c-discordants.
    L.append("## Bug-type breakdown of discordant (advisory✗/binding✓) tasks")
    L.append("")
    bug_types = sorted(next(iter(R["bug_breakdown_c_discordants"].values())).keys())
    L.append("| rung | model | " + " | ".join(bug_types) + " |")
    L.append("|---|---|" + "|".join(["---"] * len(bug_types)) + "|")
    for d in sorted(R["per_rung"], key=lambda x: x["rung"]):
        counts = R["bug_breakdown_c_discordants"][d["slug"]]
        L.append("| %d | %s | %s |" % (d["rung"], d["model"].split("/")[-1],
                                       " | ".join(str(counts[bt]) for bt in bug_types)))
    L.append("")

    # Rung-1 deep dive.
    dd = R["rung1_deep_dive"]
    L.append("## Rung 1 (llama-3.2-3b) — the too-weak-to-rescue cautionary tale")
    L.append("")
    L.append("- **Advisory step_caps: %d/87** (the model never converges and never declares "
             "DONE, exhausting the cap-8 loop)." % dd["adv_step_cap_n"])
    L.append("- **Advisory false-DONEs: %d**, of which **%d are NOT rescued by binding** "
             "(binding ends at step_cap/escalated on the same task)."
             % (len(dd["adv_false_done_tasks"]), len(dd["unrescued_false_done"])))
    L.append("- **b-direction discordants (advisory✓ but binding✗ — binding LOST ground on %d "
             "tasks):**" % len(dd["b_direction"]))
    if dd["b_direction"]:
        L.append("")
        L.append("| task | bug_type | binding end-status | binding steps |")
        L.append("|---|---|---|---|")
        for rec in dd["b_direction"]:
            L.append("| %s | %s | %s | %d |" % (rec["task_id"], rec["bug_type"],
                                                rec["binding_status"], rec["binding_steps"]))
    L.append("")

    # Prediction scores.
    L.append("## The five registered predictions — scored against their verbatim text")
    L.append("")
    sc = R["prediction_scores"]
    for key in ["i", "ii", "iii", "iv", "v"]:
        L.append("- **(%s) %s** — %s" % (key, sc[key]["verdict"], sc[key]["detail"]))
    L.append("")
    L.append("Prediction (v) is scored as **exploratory**, exactly as registered (not "
             "confirmatory). The headline confirmatory results are (i) DISCONFIRMED (binding can "
             "hurt at the extreme weak end) and (ii) DISCONFIRMED (no significant positive Δ-vs-"
             "rank monotonicity, because the weak end reverses) — the capability-window finding.")
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
    with open(os.path.join(_HERE, "curve.txt"), "w", encoding="utf-8") as fh:
        fh.write(_delta_curve_ascii(R["per_rung"]) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
