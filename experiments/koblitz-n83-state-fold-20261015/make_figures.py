#!/usr/bin/env python3
"""Write figures/result.tex from a run's result.json and render it to PDF and PNG.

Usage: python3 make_figures.py run_github_<id>/panel/result.json

Ratios (mean of the first arm over the second) with 95% bootstrap intervals
over the 16 points, on a log2 axis; the dashed line is parity. The primary is
orange, controls grey. Every number is read from result.json.
"""
import json
import math
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIG = HERE / "figures"
ROWS = [
    ("PRIMARY cold cB / cF", "primary_cold_cB_over_cF", "p"),
    ("setup cB / cF", "setup_cB_over_cF", ""),
    ("index build cB / cF", "index_build_cB_over_cF", ""),
    ("online cB / cF", "online_cB_over_cF", ""),
    ("peak RSS cB / cF", "peak_rss_cB_over_cF", ""),
    ("cold cBL / cFL (lift single arm)", "cold_cBL_over_cFL", ""),
    ("cold cBF / cFF (Feistel single arm)", "cold_cBF_over_cFF", ""),
    ("cold better single / cF", "cold_better_single_over_cF", ""),
    ("cold cF / cFI (lift in build)", "cold_cF_over_cFI", ""),
    ("A/A cF / cFaa", "aa_cold_cF_over_cFaa", "c"),
    ("planted cX / cF", "planted_cold_cX_over_cF", "c"),
    ("cold gap cF / tuned rho", "cold_gap_cF_over_rT", ""),
    ("cold gap cB / tuned rho", "cold_gap_cB_over_rT", ""),
]


def main():
    path = Path(sys.argv[1]).resolve()
    res = json.loads(path.read_text())
    s = res["statistics"]
    x = lambda v: math.log(max(v, 1e-9), 2)  # noqa: E731
    lo_axis, hi_axis, n = 0.5, 32.0, len(ROWS)
    L = ["% Editable source for result.pdf, written by make_figures.py from " + str(path.relative_to(HERE)),
         "\\documentclass[tikz,border=6pt]{standalone}", "\\usepackage[T1]{fontenc}", "\\begin{document}",
         "\\begin{tikzpicture}[font=\\sffamily\\footnotesize,x=14mm,y=-5.6mm]"]
    for v in (0.5, 1, 2, 4, 8, 16, 32):
        L.append("\\draw[gray!35] (%.4f,-0.6) -- (%.4f,%d); \\node[gray] at (%.4f,%.1f) {%g};" % (x(v), x(v), n, x(v), n + 0.5, v))
    L.append("\\draw[red!70!black,dashed] (0,-0.6) -- (0,%d);" % n)
    L.append("\\node at (0,%.1f) {ratio (log scale); bars: estimate; whiskers: 95\\%% bootstrap over 16 points};" % (n + 1.3))
    L.append("\\node[anchor=west,font=\\sffamily\\bfseries] at (-9.3,-1.5) {Primary verdict: %s};" % res["decision"])
    for i, (label, key, kind) in enumerate(ROWS):
        st = s[key]
        est, (lo, hi), units = st["estimate"], st["ci95"], st["n"]
        col = {"p": "orange!60", "c": "gray!45"}.get(kind, "blue!30")
        L.append("\\node[anchor=east] at (%.4f,%d) {%s};" % (x(lo_axis) - 0.1, i, label))
        L.append("\\fill[%s] (0,%f) rectangle (%.4f,%f);" % (col, i - 0.3, x(est), i + 0.3))
        L.append("\\draw (%.4f,%d) -- (%.4f,%d); \\draw (%.4f,%f) -- (%.4f,%f); \\draw (%.4f,%f) -- (%.4f,%f);"
                 % (x(lo), i, x(hi), i, x(lo), i - 0.15, x(lo), i + 0.15, x(hi), i - 0.15, x(hi), i + 0.15))
        L.append("\\node[anchor=west,font=\\sffamily\\scriptsize] at (%.4f,%d) {%.4f [%.4f, %.4f], n=%d};" % (x(hi_axis) + 0.05, i, est, lo, hi, units))
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
