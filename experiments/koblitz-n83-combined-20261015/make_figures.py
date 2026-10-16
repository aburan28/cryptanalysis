#!/usr/bin/env python3
"""Write result.tex from a run's result.json and render it to PDF and PNG.

Usage: python3 make_figures.py run_github_<id>/panel/result.json

Ratios with 95% bootstrap intervals over targets (slices where marked), on a
log2 axis; the dashed line is parity. The two primary statistics are drawn in
orange; controls in grey. Every number is read from result.json.
"""
import json
import math
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIG = HERE / "figures"


def get(s, key):
    v = s[key]
    if "estimate" in v:
        return v
    return v["means"]


def rows(s):
    ci = lambda k: (s[k]["estimate"], s[k]["ci95"], s[k]["units"])  # noqa: E731
    sub = lambda k, f: (s[k][f]["estimate"], s[k][f]["ci95"], s[k][f]["units"])  # noqa: E731
    return [
        ("PRIMARY R\\_m: better single / combined (means)", ci("primary_R_means"), "p"),
        ("PRIMARY R\\_g: better single / combined (geomeans)", ci("primary_R_geomeans"), "p"),
        ("combined vs lift\\_scan only (means)", sub("primary_LF_vs_L", "means"), ""),
        ("combined vs Feistel only (means)", sub("primary_LF_vs_F", "means"), ""),
        ("combined vs B (means)", sub("primary_LF_vs_B", "means"), ""),
        ("combined vs B (geomeans)", sub("primary_LF_vs_B", "geomeans"), ""),
        ("probes: B / Feistel (means)", ci("primary_F_vs_B_probes"), ""),
        ("A/A combined / combined", ci("primary_aa_LF_over_LFaa"), "c"),
        ("planted lift+full / combined", ci("primary_planted_X_over_LF"), "c"),
        ("tuned rho / combined (means)", sub("rho_gap_rT_over_pLF", "means"), ""),
        ("old 384 held-out R\\_m (secondary)", ci("old_heldout_R_means"), "s"),
    ]


def main():
    path = Path(sys.argv[1]).resolve()
    result = json.loads(path.read_text())
    R = rows(result["statistics"])
    dec = result["decision"]
    x = lambda v: math.log(max(v, 1e-9), 2)  # noqa: E731
    lo_axis, hi_axis = 0.5, 8.0
    n = len(R)
    L = ["% Editable source for result.pdf, written by make_figures.py from " + str(path.relative_to(HERE)),
         "\\documentclass[tikz,border=6pt]{standalone}", "\\usepackage[T1]{fontenc}", "\\begin{document}",
         "\\begin{tikzpicture}[font=\\sffamily\\footnotesize,x=22mm,y=-5.6mm]"]
    for v in (0.5, 1, 2, 4, 8):
        L.append("\\draw[gray!35] (%.4f,-0.6) -- (%.4f,%d); \\node[gray] at (%.4f,%.1f) {%g};"
                 % (x(v), x(v), n, x(v), n + 0.5, v))
    L.append("\\draw[red!70!black,dashed] (0,-0.6) -- (0,%d);" % n)
    L.append("\\node at (0,%.1f) {ratio (log scale); bars: estimate; whiskers: 95\\%% bootstrap};" % (n + 1.3))
    L.append("\\node[anchor=west,font=\\sffamily\\bfseries] at (-9.2,-1.5) {Primary (both lower bounds $>1$): %s; combined vs B: %s; ratchet: %s};"
             % (dec["primary"].replace("_", "\\_"), dec["combined_vs_B"], dec["ratchet"]))
    for i, (label, (est, (lo, hi), units), kind) in enumerate(R):
        colour = {"p": "orange!60", "c": "gray!45", "s": "blue!20"}.get(kind, "blue!30")
        L.append("\\node[anchor=east] at (%.4f,%d) {%s};" % (x(lo_axis) - 0.1, i, label))
        L.append("\\fill[%s] (0,%f) rectangle (%.4f,%f);" % (colour, i - 0.3, x(est), i + 0.3))
        L.append("\\draw (%.4f,%d) -- (%.4f,%d); \\draw (%.4f,%f) -- (%.4f,%f); \\draw (%.4f,%f) -- (%.4f,%f);"
                 % (x(lo), i, x(hi), i, x(lo), i - 0.15, x(lo), i + 0.15, x(hi), i - 0.15, x(hi), i + 0.15))
        L.append("\\node[anchor=west,font=\\sffamily\\scriptsize] at (%.4f,%d) {%.3f [%.3f, %.3f], n=%d};"
                 % (x(hi_axis) + 0.05, i, est, lo, hi, units))
    L += ["\\end{tikzpicture}", "\\end{document}", ""]
    FIG.mkdir(exist_ok=True)
    (FIG / "result.tex").write_text("\n".join(L))
    subprocess.run(["pdflatex", "-interaction=nonstopmode", "result.tex"], cwd=FIG, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["pdftoppm", "-png", "-r", "150", "-singlefile", "result.pdf", "result"], cwd=FIG, check=True)
    for suffix in (".aux", ".log"):
        (FIG / ("result" + suffix)).unlink(missing_ok=True)
    print("figures written to " + str(FIG))


if __name__ == "__main__":
    main()
