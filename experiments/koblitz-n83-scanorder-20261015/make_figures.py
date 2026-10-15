#!/usr/bin/env python3
"""Write the TikZ figure sources and render them to PDF and PNG.

Usage:
  python3 make_figures.py                      # receipt figures (before the run)
  python3 make_figures.py run_github_<id>/panel/result.json   # adds result.tex

* `scan_blocks.tex` is written from `analysis/receipt_blocks.json`: one bar
  per archived baseline scan (BL-arm run 38689817618), drawn in left-orbit
  block coordinates from the start state's offset to the hit state, with the
  block boundaries every 49,800 states (16,533,600 probes).
* `scan_order.tex` is a static schematic of the two state orders.
* `result.tex` (only with a result.json) draws every frozen ratio with its
  95% bootstrap interval; a missing statistic is drawn as "n/a".
"""

import json
import math
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIG = HERE / "figures"


def render(name):
    subprocess.run(["pdflatex", "-interaction=nonstopmode", name + ".tex"], cwd=FIG, check=True,
                   stdout=subprocess.DEVNULL)
    subprocess.run(["pdftoppm", "-png", "-r", "150", "-singlefile", name + ".pdf", name], cwd=FIG, check=True)
    for suffix in (".aux", ".log"):
        (FIG / (name + suffix)).unlink(missing_ok=True)


def scan_blocks():
    data = json.loads((HERE / "analysis" / "receipt_blocks.json").read_text())
    block = data["exact"]["states_per_left_block"]
    law_states = data["exact"]["law_states"]
    rows = sorted(data["rows"], key=lambda r: r["probes"])
    lines = [
        "% Editable source for scan_blocks.pdf, written by make_figures.py from analysis/receipt_blocks.json",
        "% (receipt_blocks.py over BL-arm run 38689817618). x: position in left-orbit blocks of 49,800 states.",
        "\\documentclass[tikz,border=6pt]{standalone}", "\\usepackage[T1]{fontenc}", "\\begin{document}",
        "\\begin{tikzpicture}[font=\\sffamily\\footnotesize,x=42mm,y=-5.2mm]",
    ]
    n = len(rows)
    for b in range(0, 4):
        lines.append("\\draw[%s] (%d,-0.8) -- (%d,%d);" % ("black!60" if b else "black!30", b, b, n))
        if b < 3:
            lines.append("\\node[gray] at (%.2f,%.1f) {start block + %d};" % (b + 0.5, n + 0.5, b))
    lines.append("\\fill[green!25] (0,-0.75) rectangle (%.4f,-0.35);" % (law_states / block))
    lines.append("\\node[anchor=west,font=\\sffamily\\scriptsize] at (%.4f,-0.55) {law mean: %d states (%.2f M probes)};"
                 % (law_states / block + 0.02, round(law_states), data["exact"]["law_probes"] / 1e6))
    for i, r in enumerate(rows):
        x0 = r["start_offset_in_block"] / block
        x1 = x0 + r["states_scanned"] / block
        tail = r["probes"] > 14e6
        colour = "red!70!black" if tail else ("orange!80!black" if r["point_id"] == "q0" else "blue!60!black")
        lines.append("\\node[anchor=east] at (-0.03,%d) {%s};" % (i, r["point_id"].upper() if r["point_id"] == "q0" else r["point_id"]))
        lines.append("\\draw[line width=2.2pt,%s] (%.4f,%d) -- (%.4f,%d);" % (colour, x0, i, x1, i))
        lines.append("\\fill[%s] (%.4f,%d) circle (1.4pt);" % (colour, x0, i))
        lines.append("\\draw[%s,thick] (%.4f,%f) -- (%.4f,%f);" % (colour, x1, i - 0.3, x1, i + 0.3))
        lines.append("\\node[anchor=west,font=\\sffamily\\scriptsize] at (3.05,%d) {%.2f M probes, %.2f$\\times$ law, left %d$\\to$%d};"
                     % (i, r["probes"] / 1e6, r["probes_over_law"], r["start_left_orbit"], r["hit_left_orbit"]))
    lines.append("\\node[anchor=west,font=\\sffamily\\scriptsize,align=left] at (0,%.1f) {dot: start state (public-point hash mod S);"
                 " bar end: hit state, checked against the relation's x-codes (17/17).\\\\ Red: the three fresh points above 14M probes."
                 " Every hit-free stretch here is a run of consecutive states in one or two left blocks.};" % (n + 1.6))
    lines += ["\\end{tikzpicture}", "\\end{document}", ""]
    (FIG / "scan_blocks.tex").write_text("\n".join(lines))


ROWS = [
    ("B's 16 fresh points (primary: section 23 ratio of means)", None),
    ("online, left-major / Feistel (primary)", "fresh_primary_B_over_P"),
    ("online, ratio of geometric means", "fresh_geomean_B_over_P"),
    ("online, median per-point ratio", "fresh_median_B_over_P"),
    ("probes, section 23", "fresh_probes_B_over_P"),
    ("A/A: left-major / left-major", "fresh_aa_B_over_Baa"),
    ("planted: left-major / half-skip", "fresh_planted_B_over_H"),
    ("Held-out 384 points (secondary, powered)", None),
    ("online, section 23", "heldout_B_over_P"),
    ("online, ratio of geometric means", "heldout_geomean_B_over_P"),
    ("probes, section 23", "heldout_probes_B_over_P"),
    ("Q0 (one target, 8 blocks)", None),
    ("left-major / Feistel", "q0_B_over_P"),
    ("A/A", "q0_aa_B_over_Baa"),
    ("planted", "q0_planted_B_over_H"),
    ("Distance to tuned rho (rho online / IC online)", None),
    ("fresh, left-major (old baseline)", "rho_gap_fresh_rT_over_B"),
    ("fresh, Feistel", "rho_gap_fresh_rT_over_P"),
    ("Q0, left-major", "rho_gap_q0_rT_over_B"),
    ("Q0, Feistel", "rho_gap_q0_rT_over_P"),
]


def result(path):
    result = json.loads(path.read_text())
    stats, decision = result["statistics"], result["decision"]
    lo_axis, hi_axis = 0.125, 8.0
    x = lambda v: math.log(max(v, 1e-9), 2)  # noqa: E731
    lines = [
        "% Editable source for result.pdf, written by make_figures.py from",
        "% " + str(path.relative_to(HERE)) + ". Ratios with 95% bootstrap intervals over targets (or blocks);",
        "% log2 axis; dashed line = parity.",
        "\\documentclass[tikz,border=6pt]{standalone}", "\\usepackage[T1]{fontenc}", "\\begin{document}",
        "\\begin{tikzpicture}[font=\\sffamily\\footnotesize,x=16mm,y=-5.6mm]",
    ]
    for v in (0.125, 0.25, 0.5, 1, 2, 4, 8):
        lines.append("\\draw[gray!35] (%.4f,-0.6) -- (%.4f,%d); \\node[gray] at (%.4f,%.1f) {%g};"
                     % (x(v), x(v), len(ROWS), x(v), len(ROWS) + 0.5, v))
    lines.append("\\draw[red!70!black,dashed] (0,-0.6) -- (0,%d);" % len(ROWS))
    lines.append("\\node at (0,%.1f) {ratio (log scale); bars: estimate; whiskers: 95\\%% bootstrap};" % (len(ROWS) + 1.2))
    lines.append("\\node[anchor=west,font=\\sffamily\\bfseries] at (-8.6,-1.5) {Primary: %s; held-out: %s; ratchet: %s};"
                 % (decision["online_fresh_primary"], decision["heldout_secondary"].replace("_", "\\_"),
                    decision["ratchet"].replace("_", "\\_")))
    for i, (label, key) in enumerate(ROWS):
        if key is None:
            lines.append("\\node[anchor=west,font=\\sffamily\\bfseries] at (-8.6,%d) {%s};" % (i, label))
            continue
        lines.append("\\node[anchor=east] at (%.4f,%d) {%s};" % (x(lo_axis) - 0.1, i, label))
        stat = stats.get(key)
        if not stat:
            lines.append("\\node[anchor=west] at (%.4f,%d) {n/a};" % (x(1), i))
            continue
        est, (lo, hi) = stat["estimate"], stat["ci95"]
        colour = "orange!55" if "primary" in key else "gray!45" if ("aa" in key or "planted" in key) else "blue!30"
        lines.append("\\fill[%s] (0,%f) rectangle (%.4f,%f);" % (colour, i - 0.3, x(est), i + 0.3))
        lines.append("\\draw (%.4f,%d) -- (%.4f,%d); \\draw (%.4f,%f) -- (%.4f,%f); \\draw (%.4f,%f) -- (%.4f,%f);"
                     % (x(lo), i, x(hi), i, x(lo), i - 0.15, x(lo), i + 0.15, x(hi), i - 0.15, x(hi), i + 0.15))
        lines.append("\\node[anchor=west,font=\\sffamily\\scriptsize] at (%.4f,%d) {%.3f [%.3f, %.3f], n=%d};"
                     % (x(hi_axis) + 0.05, i, est, lo, hi, stat["units"]))
    lines += ["\\end{tikzpicture}", "\\end{document}", ""]
    (FIG / "result.tex").write_text("\n".join(lines))


def main():
    FIG.mkdir(exist_ok=True)
    scan_blocks()
    names = ["scan_blocks", "scan_order"]
    if len(sys.argv) > 1:
        result(Path(sys.argv[1]).resolve())
        names.append("result")
    for name in names:
        render(name)
    print("figures written to " + str(FIG))


if __name__ == "__main__":
    main()
