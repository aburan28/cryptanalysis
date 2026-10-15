#!/usr/bin/env python3
"""Write figures/result.tex from an archived receipt and render PDF and PNG.

Usage: python3 make_figures.py run_github_<id>/panel/result.json

Rows: every frozen ratio with its 95% bootstrap interval (stage primary,
secondary, A/A and planted; online Q0 primary, variant-B secondaries, A/A and
planted; fresh section 23 and median; tuned rho over IC, old and new). A
missing statistic is drawn as "n/a", never as a value. The static figures
(`online_path.tex`, `rotation_counts.tex`) are rendered too.
"""

import json
import math
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIG = HERE / "figures"
ROWS = [
    ("Stage level (E-1, frozen pairs): variant B / lift\\_scan", None),
    ("canonicalization phase (primary)", "stage_primary_canon_B_over_A"),
    ("target stage (secondary)", "stage_secondary_target_stage_B_over_A"),
    ("A/A: canonicalization phase, B / B", "stage_aa_canon"),
    ("A/A: target stage, B / B", "stage_aa_target_stage"),
    ("planted: B + discarded B / B", "stage_planted_canon_x2_over_B"),
    ("Online level (one-target IC interval): full scan / lift\\_scan", None),
    ("Q0, 8 blocks (primary)", "online_q0_primary_full_over_lift"),
    ("16 fresh points, section 23 (primary)", "online_fresh_primary_full_over_lift"),
    ("16 fresh points, median per-point ratio", "online_fresh_secondary_median"),
    ("Q0: variant B / lift\\_scan", "online_q0_gap_over_lift"),
    ("Q0: full / variant B", "online_q0_full_over_gap"),
    ("Q0 A/A: full / full", "online_q0_aa"),
    ("Q0 planted: full + discarded full / full", "online_q0_planted_x2_over_full"),
    ("Distance to tuned rho (rho online / IC online)", None),
    ("Q0, old baseline (full)", "rho_gap_q0_means_rT_over_full"),
    ("Q0, new (lift\\_scan)", "rho_gap_q0_means_rT_over_lift"),
    ("fresh, old baseline (full)", "rho_gap_fresh_rT_over_full"),
    ("fresh, new (lift\\_scan)", "rho_gap_fresh_rT_over_lift"),
]


def render(name):
    subprocess.run(["pdflatex", "-interaction=nonstopmode", name + ".tex"], cwd=FIG, check=True,
                   stdout=subprocess.DEVNULL)
    subprocess.run(["pdftoppm", "-png", "-r", "150", "-singlefile", name + ".pdf", name], cwd=FIG, check=True)
    for suffix in (".aux", ".log"):
        (FIG / (name + suffix)).unlink(missing_ok=True)


def main():
    result_path = Path(sys.argv[1]).resolve()
    result = json.loads(result_path.read_text())
    stats, decision = result["statistics"], result["decision"]
    lo_axis, hi_axis = 0.25, 4.0
    x = lambda v: math.log(v, 2)  # noqa: E731
    lines = [
        "% Editable source for result.pdf, written by make_figures.py from",
        "% " + str(result_path.relative_to(HERE)) + ". Ratios with 95% paired bootstrap intervals",
        "% (frozen protocol.json statistics); log2 axis; dashed line = parity.",
        "\\documentclass[tikz,border=6pt]{standalone}", "\\usepackage[T1]{fontenc}", "\\begin{document}",
        "\\begin{tikzpicture}[font=\\sffamily\\footnotesize,x=22mm,y=-5.6mm]",
    ]
    for v in (0.25, 0.5, 1, 2, 4):
        lines.append("\\draw[gray!35] (%.4f,-0.6) -- (%.4f,%d); \\node[gray] at (%.4f,%.1f) {%g};"
                     % (x(v), x(v), len(ROWS), x(v), len(ROWS) + 0.5, v))
    lines.append("\\draw[red!70!black,dashed] (0,-0.6) -- (0,%d);" % len(ROWS))
    lines.append("\\node at (0,%.1f) {ratio (log scale); bars: estimate; whiskers: 95\\%% bootstrap};" % (len(ROWS) + 1.2))
    lines.append("\\node[anchor=west,font=\\sffamily\\bfseries] at (-6.3,-1.5) {Online verdict: %s; stage verdict: %s; ratchet: %s};"
                 % (decision["online"], decision["stage"], decision["ratchet"].replace("_", "\\_")))
    for i, (label, key) in enumerate(ROWS):
        if key is None:
            lines.append("\\node[anchor=west,font=\\sffamily\\bfseries] at (-6.3,%d) {%s};" % (i, label))
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
    for name in ("result", "online_path", "rotation_counts"):
        render(name)
    print("figures written to " + str(FIG))


if __name__ == "__main__":
    main()
