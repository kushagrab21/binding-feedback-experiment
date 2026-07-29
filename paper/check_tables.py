"""Table checker for the LaTeX conversion.

Usage: python3 check_tables.py exp1

Parses the tabular rows of the named table in the converted .tex file and
verifies every printed cell against the figure-pipeline CSVs in
../writeup_figures/data/, which are themselves verified against the
experiment results files by writeup_figures/verify_data.py.
Exit 0 only when every cell matches.
"""
import csv, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "writeup_figures", "data")

def rows(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

def tex_table_rows(tex_path, label=None):
    t = open(tex_path, encoding="utf-8").read()
    envs = re.findall(r"\\begin\{table\}(.*?)\\end\{table\}", t, flags=re.S)
    if label is not None:
        envs = [e for e in envs if f"\\label{{{label}}}" in e]
        if len(envs) != 1:
            errors.append(f"{label}: {len(envs)} tables carry this label, expected 1")
            return []
        t = envs[0]
    body = re.findall(r"\\midrule(.*?)\\bottomrule", t, flags=re.S)
    out = []
    for block in body:
        for line in block.split("\\\\"):
            line = line.strip()
            if not line or line.startswith("%"):
                continue
            cells = [re.sub(r"\\[A-Za-z]+|[{}$]", "", c).strip()
                     for c in line.split("&")]
            out.append(cells)
    return out

errors = []
def check(where, got, want):
    if got != want:
        errors.append(f"{where}: tex has {got!r}, CSV says {want!r}")

def exp1():
    r = rows("exp1_results.csv")
    get = lambda m, mode: next(x for x in r if x["model"] == m and x["mode"] == mode)
    def cell(m, mode):
        c = get(m, mode)
        pct = float(c["success_pct"])
        pct_s = f"{pct:.1f}%" if pct != 100.0 else "100%"
        return f"{c['solved']}/{c['total']} ({pct_s})"
    def delta(m):
        d = float(get(m, "binding")["success_pct"]) - float(get(m, "advisory")["success_pct"])
        return f"+{d:.1f} pp"
    want = [
        ["weak (gpt-4o-mini)", cell("gpt-4o-mini", "advisory"),
         cell("gpt-4o-mini", "binding"), delta("gpt-4o-mini")],
        ["strong (gpt-4.1)", cell("gpt-4.1", "advisory"),
         cell("gpt-4.1", "binding"), delta("gpt-4.1")],
    ]
    got = tex_table_rows(os.path.join(HERE, "sections", "04_exp1.tex"), "tab:exp1")
    if len(got) != len(want):
        errors.append(f"exp1: {len(got)} tex rows, expected {len(want)}")
        return
    for g, w in zip(got, want):
        for gc, wc in zip(g, w):
            check(f"exp1 row {w[0]}", gc.replace("\\%", "%"), wc)


def fmt_p(p):
    p = float(p)
    return "1" if p == 1 else f"{p:.2g}"

def exp2():
    r = sorted(rows("exp2_ladder.csv"), key=lambda x: int(x["rank"]))
    want = []
    for x in r:
        d = float(x["delta_pp"])
        want.append([x["rank"], x["model"], f"{x['advisory_solved']}/87",
                     f"{x['binding_solved']}/87", f"{d:+.1f}",
                     x["b"], x["c"], fmt_p(x["mcnemar_p"])])
    got_ladder = tex_table_rows(os.path.join(HERE, "sections", "05_exp2.tex"), "tab:ladder")
    if len(got_ladder) != 7:
        errors.append(f"exp2 ladder: {len(got_ladder)} rows found, expected 7"); return
    for g, w in zip(got_ladder, want):
        for gc, wc in zip(g, w):
            check(f"exp2 ladder rank {w[0]}", gc, str(wc))

def exp2exits():
    r = sorted(rows("exp2_ladder.csv"), key=lambda x: int(x["rank"]))
    want = []
    for x in r:
        d = float(x["delta_pp"])
        want.append([x["model"], x["adv_true_done"], x["adv_false_done"],
                     x["adv_cap_pass"], x["adv_cap_fail"], x["bind_solved"],
                     x["bind_escalated"], x["bind_step_cap"], f"{d:+.1f}"])
    got_exits = tex_table_rows(os.path.join(HERE, "sections", "05_exp2.tex"), "tab:exits")
    if len(got_exits) != 7:
        errors.append(f"exp2 exits: {len(got_exits)} rows found, expected 7"); return
    for g, w in zip(got_exits, want):
        for gc, wc in zip(g, w):
            check(f"exp2 exits {w[0]}", gc, str(wc))


def p_matches(tex_s, val):
    tex_s = tex_s.strip()
    try:
        tv = float(tex_s)
    except ValueError:
        return False
    if "e" in tex_s.lower():
        return abs(tv - val) <= 0.05 * abs(tv) + 1e-12
    if "." in tex_s:
        nd = len(tex_s.split(".")[1])
        return round(val, nd) == tv
    return tv == val

def exp3matrix():
    order = ["GPT-4.1", "Gemini-2.5-Flash-Lite", "GPT-4o-mini", "Claude-3-Haiku",
             "Qwen2.5-7B", "Llama-3.1-8B"]
    r = rows("exp3_matrix.csv")
    def d(m, k):
        x = next(y for y in r if y["model"] == m and int(y["k"]) == k)
        return f"{float(x['delta_pp']):+.1f}"
    want = [[m, d(m, 0), d(m, 1), d(m, 2)] for m in order]
    got = tex_table_rows(os.path.join(HERE, "sections", "06_exp3.tex"), "tab:matrix")
    if len(got) != 6:
        errors.append(f"exp3 matrix: {len(got)} rows, expected 6"); return
    for g, w in zip(got, want):
        for gc, wc in zip(g, w):
            check(f"exp3 matrix {w[0]}", gc, wc)

def exp3cells():
    r = rows("exp3_cells.csv")
    got = tex_table_rows(os.path.join(HERE, "sections", "06_exp3.tex"), "tab:cells")
    if len(got) != 12:
        errors.append(f"exp3 cells: {len(got)} rows, expected 12"); return
    for g in got:
        m, tier = g[0], g[1]
        x = next((y for y in r if y["model"] == m and y["tier"] == tier), None)
        if x is None:
            errors.append(f"exp3 cells: no CSV row for {m} {tier}"); continue
        n = x["tasks"]
        check(f"exp3 {m} {tier} advisory", g[2], f"{x['advisory_solved']}/{n}")
        check(f"exp3 {m} {tier} binding", g[3], f"{x['binding_solved']}/{n}")
        check(f"exp3 {m} {tier} delta", g[4], f"{float(x['delta_pp']):+.1f}")
        check(f"exp3 {m} {tier} b", g[5], x["b"])
        check(f"exp3 {m} {tier} c", g[6], x["c"])
        if not p_matches(g[7], float(x["mcnemar_p"])):
            errors.append(f"exp3 {m} {tier} p: tex {g[7]!r} vs CSV {x['mcnemar_p']}")

TABLES = {"exp1": exp1, "exp2": exp2, "exp2exits": exp2exits,
          "exp3matrix": exp3matrix, "exp3cells": exp3cells}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in TABLES:
        sys.exit(f"usage: check_tables.py [{'|'.join(TABLES)}]")
    TABLES[sys.argv[1]]()
    if errors:
        print(f"TABLE MISMATCH ({len(errors)}):")
        for e in errors:
            print("  " + e)
        sys.exit(1)
    print(f"TABLE OK: every cell of {sys.argv[1]} matches the CSV")
