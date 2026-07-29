"""Verify every value in data/*.csv against the repository's deterministic
analysis outputs (results.json of v1, v2, v3) — the source of truth.

Prints every discrepancy and exits nonzero if any value disagrees.
"""
import csv, json, math, os, sys

CANDIDATES = [
    os.environ.get("REPO_BASE"),
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    os.path.expanduser("~/Desktop/Experiment_binding_agent/binding-feedback-experiment"),
    "/mnt/user-data/uploads/Experiment_binding_agent/binding-feedback-experiment",
]
BASE = next(c for c in CANDIDATES if c and os.path.isdir(c))
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

v1 = json.load(open(f"{BASE}/phase6_analysis/results.json"))
v2 = json.load(open(f"{BASE}/v2_ladder/analysis/results.json"))
v3 = json.load(open(f"{BASE}/v3_window/analysis/results.json"))

errors = []
checked = 0
def check(where, field, csv_val, truth_val, tol=0.051):
    global checked
    checked += 1
    if truth_val is None:
        errors.append(f"{where} :: {field}: TRUTH LOOKUP FAILED (csv={csv_val!r})")
        return
    try:
        ok = math.isclose(float(csv_val), float(truth_val), abs_tol=tol)
    except (TypeError, ValueError):
        ok = str(csv_val) == str(truth_val)
    if not ok:
        errors.append(f"{where} :: {field}: csv={csv_val!r} truth={truth_val!r}")

def rows(name):
    with open(os.path.join(DATA, name)) as f:
        return list(csv.DictReader(f))

SLUG = {"GPT-4.1": "gpt-4.1", "Gemini-2.5-Flash-Lite": "gemini-2.5-flash-lite",
        "GPT-4o-mini": "gpt-4o-mini", "Claude-3-Haiku": "claude-3-haiku",
        "Qwen2.5-7B": "qwen", "Llama-3.1-8B": "llama-3.1-8b",
        "Llama-3.2-3B": "llama-3.2-3b"}

# ---------------- exp1_results.csv vs v1 cells
v1cells = list(v1["cells"].values()) if isinstance(v1["cells"], dict) else v1["cells"]
def v1cell(model, mode):
    for c in v1cells:
        name = (c.get("model") or c.get("model_resolved") or "")
        if model in name and c["mode"] == mode:
            return c
    return {}

for r in rows("exp1_results.csv"):
    c = v1cell(r["model"], r["mode"]); w = f'exp1 {r["model"]}/{r["mode"]}'
    solved = c.get("n_solved", c.get("solved"))
    n = c.get("n", 87)
    check(w, "solved", r["solved"], solved)
    if r["mode"] == "advisory":
        check(w, "false_done", r["false_done"], c.get("false_done", 0))
    else:
        # binding has no false-DONE by construction (done is ignored); field absent in truth
        check(w, "false_done", r["false_done"], c.get("false_done", 0) or 0)
    check(w, "mean_steps", r["mean_steps"], c.get("mean_steps"), tol=0.006)
    check(w, "cost_usd", r["cost_usd"], c.get("cost_usd"), tol=0.00006)
    check(w, "success_pct", r["success_pct"], 100*float(solved)/float(n), tol=0.051)

# ---------------- exp2_ladder.csv vs v2 cells + per_rung + rescue
v2cells = list(v2["cells"].values())
def v2cell(model, mode):
    s = SLUG[model]
    for c in v2cells:
        if s in c["model_resolved"].lower() and c["mode"] == mode:
            return c
    return {}
def v2rung(model):
    s = SLUG[model]
    for p in v2["per_rung"]:
        if s in json.dumps(p).lower():
            return p
    return {}
def v2rescue(model):
    s = SLUG[model]
    for slug, x in v2["rescue"].items():
        if s in slug.lower():
            return x
    return None

for r in rows("exp2_ladder.csv"):
    m = r["model"]; w = f"exp2 {m}"
    a, b_ = v2cell(m, "advisory"), v2cell(m, "binding")
    p = v2rung(m)
    check(w, "advisory_solved", r["advisory_solved"], a.get("n_solved"))
    check(w, "binding_solved", r["binding_solved"], b_.get("n_solved"))
    check(w, "adv_false_done", r["adv_false_done"], a.get("false_done"))
    declared = 87 - a.get("step_cap", 0)
    true_done = declared - a.get("false_done", 0)
    check(w, "adv_true_done", r["adv_true_done"], true_done)
    check(w, "adv_cap_pass", r["adv_cap_pass"], a.get("n_solved") - true_done)
    check(w, "adv_cap_fail", r["adv_cap_fail"],
          a.get("step_cap", 0) - (a.get("n_solved") - true_done))
    check(w, "bind_escalated", r["bind_escalated"], b_.get("escalated"))
    check(w, "bind_step_cap", r["bind_step_cap"], b_.get("step_cap"))
    check(w, "resub_rejected", r["resub_rejected"], b_.get("resub_rejected"))
    check(w, "delta_pp", r["delta_pp"], p.get("delta_pp"))
    check(w, "b", r["b"], p.get("mcnemar_b"))
    check(w, "c", r["c"], p.get("mcnemar_c"))
    check(w, "mcnemar_p", r["mcnemar_p"], p.get("mcnemar_p"), tol=1e-6)
    resc = v2rescue(m)
    if resc is None:
        errors.append(f"{w} :: rescue row not found")
    else:
        check(w, "forced_repairs", r["forced_repairs"], len(resc.get("forced", [])))
        check(w, "first_sample", r["first_sample"], len(resc.get("first_sample", [])))

# ---------------- exp3_cells.csv vs v3 per_cell + rescue
def v3cell(model, tier):
    s = SLUG[model]
    for slug, c in v3["per_cell"].items():
        base, _, t = slug.rpartition("__")
        if s in base.lower() and t == tier:
            return c
    return {}
def v3rescue(model, tier):
    s = SLUG[model]
    for slug, x in v3["rescue"].items():
        base, _, t = slug.rpartition("__")
        if s in base.lower() and t == tier:
            return x
    return None

for r in rows("exp3_cells.csv"):
    m, t = r["model"], r["tier"]; w = f"exp3 {m}/{t}"
    c = v3cell(m, t)
    n = float(r["tasks"])
    check(w, "advisory_solved", r["advisory_solved"], c.get("adv_solved"))
    check(w, "binding_solved", r["binding_solved"], c.get("bind_solved"))
    check(w, "adv_false_done", r["adv_false_done"], c.get("adv_false_done"))
    check(w, "b", r["b"], c.get("mcnemar_b", len(c.get("b_tasks", [])) if "b_tasks" in c else None))
    check(w, "c", r["c"], c.get("mcnemar_c", len(c.get("c_tasks", [])) if "c_tasks" in c else None))
    check(w, "mcnemar_p", r["mcnemar_p"], c.get("mcnemar_p"), tol=1e-8)
    check(w, "delta_pp", r["delta_pp"],
          100*(float(c.get("bind_solved", 0)) - float(c.get("adv_solved", 0)))/n)
    resc = v3rescue(m, t)
    if resc is None:
        errors.append(f"{w} :: rescue row not found")
    else:
        check(w, "forced_repairs", r["forced_repairs"], len(resc.get("forced", [])))
        check(w, "first_sample", r["first_sample"], len(resc.get("first_sample", [])))

# ---------------- exp3_matrix.csv vs delta_matrix + false_done_surface / v2
def dmrow(model):
    s = SLUG[model]
    for x in v3["delta_matrix"]:
        if s in x["model"].lower():
            return x
    return {}
fds = v3["false_done_surface"]
def fdrow(model):
    s = SLUG[model]
    it = fds if isinstance(fds, list) else list(fds.values())
    if isinstance(fds, dict):
        for slug, x in fds.items():
            if s in slug.lower():
                return x
        return {}
    for x in it:
        if s in json.dumps(x).lower():
            return x
    return {}

for r in rows("exp3_matrix.csv"):
    m, k = r["model"], int(r["k"]); w = f"matrix {m}/k{k}"
    check(w, "delta_pp", r["delta_pp"], dmrow(m).get(f"k{k}"))
    fd = fdrow(m)
    val = fd.get(f"k{k}")
    if isinstance(val, dict):
        val = val.get("rate", val.get("pct"))
    check(w, "false_done_rate_pct", r["false_done_rate_pct"], val, tol=0.051)

# ---------------- mediator_scatter.csv
for r in rows("mediator_scatter.csv"):
    m, t, exp = r["model"], r["tier"], r["experiment"]
    w = f"scatter {exp} {m}/{t}"
    if exp == "v2":
        a, b_ = v2cell(m, "advisory"), v2cell(m, "binding")
        check(w, "false_done_rate_pct", r["false_done_rate_pct"],
              100*a.get("false_done")/87.0, tol=0.051)
        check(w, "delta_pp", r["delta_pp"],
              100*(b_.get("n_solved")-a.get("n_solved"))/87.0, tol=0.051)
    else:
        c = v3cell(m, t)
        check(w, "false_done_rate_pct", r["false_done_rate_pct"],
              c.get("adv_false_done_rate"), tol=0.051)
        n = 60.0 if t == "k1" else 48.0
        check(w, "delta_pp", r["delta_pp"],
              100*(float(c.get("bind_solved", 0))-float(c.get("adv_solved", 0)))/n, tol=0.051)

print(f"values checked: {checked}; discrepancies: {len(errors)}")
for e in errors:
    print("  DIFF", e)
sys.exit(1 if errors else 0)
