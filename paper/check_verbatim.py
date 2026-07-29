"""Verbatim checker for the LaTeX conversion.

Usage: python3 check_verbatim.py --section "1. Abstract" --tex sections/01_abstract.tex

Extracts the named section from paper/source.txt, strips LaTeX markup from the
converted .tex file, normalizes both to plain word sequences, and diffs them.
Exit 0 only when the word sequences match exactly, apart from lines listed in
an optional exceptions file (paper/exceptions/<texname>.txt, one approved
replacement per line in the form  OLD>>>NEW  applied to the source text).
"""
import argparse, difflib, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))

def extract_section(source_path, heading):
    text = open(source_path, encoding="utf-8").read()
    lines = text.split("\n")
    start = None
    for i, ln in enumerate(lines):
        if ln.strip() == heading:
            start = i + 1
            break
    if start is None:
        sys.exit(f"section heading {heading!r} not found in source")
    end = len(lines)
    for j in range(start, len(lines)):
        if re.match(r"^\d+\.\s+\S", lines[j]) and not re.match(r"^\d+\.\s*$", lines[j]):
            # a numbered top-level heading ends the section, but numbered list
            # items inside a section also match, so require the next heading to
            # be one of the known section titles
            if re.match(r"^\d+\. (Abstract|Question|Setup|Experiment|The mechanism|Limitations|What this means)", lines[j]):
                end = j
                break
    return "\n".join(lines[start:end])

def detex(tex_path):
    t = open(tex_path, encoding="utf-8").read()
    t = re.sub(r"(?<!\\)%.*", "", t)                       # comments
    t = re.sub(r"\\begin\{table\}.*?\\end\{table\}", " ", t, flags=re.S)
    # run-in headings and list labels end with a colon in the tex where the
    # source text ends them with a full stop: an approved presentation change
    t = re.sub(r"(\\(?:paragraph\*?|textbf|textit|emph)\{[^}]*):\}", r"\1.}", t)
    t = re.sub(r"\\(section|subsection)\*?\{[^}]*\}", " ", t)
    t = re.sub(r"\\paragraph\*?\{([^}]*)\}", r"\1", t)
    t = re.sub(r"\\(textbf|textit|emph|texttt|url|mbox)\{([^}]*)\}", r"\2", t)
    t = re.sub(r"\\includegraphics(\[[^\]]*\])?\{[^}]*\}", " ", t)
    t = re.sub(r"\\caption\{[^}]*\}", " ", t)
    t = re.sub(r"\\label\{[^}]*\}", " ", t)
    t = re.sub(r"\\(begin|end)\{[^}]*\}(\[[^\]]*\])?", " ", t)
    t = t.replace("\\%", "%").replace("\\&", "&").replace("\\_", "_").replace("\\#", "#")
    t = t.replace("\\$", "\x00")                            # protect literal dollars
    t = re.sub(r"\$([^$]*)\$", r"\1", t)                    # inline math to its content
    t = t.replace("\x00", "$")
    t = t.replace("\\times", "×").replace("\\Delta", "Δ").replace("\\rho", "rho")
    t = t.replace("\\geq", "≥").replace("\\leq", "≤").replace("\\rightarrow", "→")
    t = t.replace("---", "—").replace("--", "–")
    t = t.replace("``", '"').replace("''", '"')
    t = re.sub(r"\\\\(\[[^]]*\])?", " ", t)
    t = re.sub(r"\\[A-Za-z]+\*?", " ", t)                   # any remaining command
    t = t.replace("^{-", "^-")
    t = t.replace("{", " ").replace("}", " ").replace("~", " ")
    t = re.sub(r"\s+([.,;:])", r"\1", t)
    return t

def normalize(s):
    s = s.replace("\u2019", "'").replace("\u2018", "'")
    s = s.replace("\u201c", '"').replace("\u201d", '"')
    s = s.replace("\u2013", "-").replace("\u2014", "-").replace("\u2212", "-")
    s = s.replace("\ufb01", "fi").replace("\ufb02", "fl")
    s = s.replace("\u207b\u2076", "^-6")
    for d, r in zip("\u2070\u00b9\u00b2\u00b3\u2074\u2075\u2076\u2077\u2078\u2079", "0123456789"):
        s = s.replace(d, "^" + r)
    s = re.sub(r"\s+", " ", s).strip()
    return s.split(" ")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--section", required=True)
    ap.add_argument("--tex", required=True)
    ap.add_argument("--source", default=os.path.join(HERE, "source.txt"))
    args = ap.parse_args()

    src = extract_section(args.source, args.section)

    exc_path = os.path.join(HERE, "exceptions",
                            os.path.basename(args.tex).replace(".tex", ".txt"))
    n_exc = 0
    if os.path.exists(exc_path):
        for line in open(exc_path, encoding="utf-8"):
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            old, sep, new = line.partition(">>>")
            if not sep:
                sys.exit(f"bad exception line: {line!r}")
            old = old.replace("\\n", "\n")
            new = new.replace("\\n", "\n")
            if old not in src:
                sys.exit(f"exception OLD text not found in source: {old!r}")
            src = src.replace(old, new)
            n_exc += 1

    a = normalize(src)
    b = normalize(detex(args.tex))

    if a == b:
        print(f"VERBATIM OK: {len(a)} words match ({n_exc} approved exceptions applied)")
        return 0
    print(f"MISMATCH: source {len(a)} words, tex {len(b)} words")
    sm = difflib.SequenceMatcher(a=a, b=b)
    shown = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        print(f"  {tag}: source[{i1}:{i2}] {' '.join(a[i1:i2])[:100]!r}"
              f"  ->  tex[{j1}:{j2}] {' '.join(b[j1:j2])[:100]!r}")
        shown += 1
        if shown >= 20:
            print("  ... further differences suppressed")
            break
    return 1

if __name__ == "__main__":
    sys.exit(main())
