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

def tex_table_rows(tex_path):
    t = open(tex_path, encoding="utf-8").read()
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
    got = tex_table_rows(os.path.join(HERE, "sections", "04_exp1.tex"))
    if len(got) != len(want):
        errors.append(f"exp1: {len(got)} tex rows, expected {len(want)}")
        return
    for g, w in zip(got, want):
        for gc, wc in zip(g, w):
            check(f"exp1 row {w[0]}", gc.replace("\\%", "%"), wc)

TABLES = {"exp1": exp1}

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
