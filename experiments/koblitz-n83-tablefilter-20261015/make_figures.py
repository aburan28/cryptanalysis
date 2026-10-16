#!/usr/bin/env python3
"""Figures of the root-table filter experiment (lookup diagnosis and the two-level table diagram).

Each figure is an editable TikZ source (`figures/<name>.tex`) rendered with
pdflatex to `figures/<name>.pdf` and with pdftoppm to `figures/<name>.png`
(the machinery of `claude/n83-probe-pipeline`'s `make_figures.py`).

* `lookup_diagnosis`: in-situ marginal lookup ns/probe of the probe
  pipeline over the 4 GiB 32-byte table, the 2 GiB 16-byte table and the
  32 MiB filter in front of it, with 2 MiB (THP) and 4 KiB pages; and the
  lookup-only loops with and without prefetch. From
  `analysis/profile_local.json` (cloud-agent VM, diagnostic only).
* `two_level_table`: the scan loop over the two-level table and the slot
  layout.

The Tier 1 result figure is owed after the run.
"""

import json
import math
import sys
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIG = HERE / "figures"


def render(name, body):
    FIG.mkdir(exist_ok=True)
    (FIG / (name + ".tex")).write_text(body)
    subprocess.run(["pdflatex", "-interaction=nonstopmode", name + ".tex"], cwd=FIG, check=True,
                   stdout=subprocess.DEVNULL)
    subprocess.run(["pdftoppm", "-png", "-r", "150", "-singlefile", name + ".pdf", name], cwd=FIG, check=True)
    for suffix in (".aux", ".log"):
        (FIG / (name + suffix)).unlink(missing_ok=True)


def bars(lines, title, x0, y0, rows, scale, axis_max, step, unit):
    """Horizontal paired bars (THP dark, 4 KiB light) with a value label each."""
    lines.append(r"\node[anchor=west,font=\sffamily\bfseries] at (%.2f,%.2f) {%s};" % (x0, y0, title))
    y = y0 - 0.75
    for label, thp, small in rows:
        lines.append(r"\node[anchor=east,align=right,font=\sffamily\scriptsize] at (%.2f,%.2f) {%s};" %
                     (x0 + 4.3, y - 0.1, label))
        for value, color, dy in ((thp, "blue!65", 0.0), (small, "blue!25", -0.32)):
            w = value * scale
            lines.append(r"\fill[%s] (%.3f,%.2f) rectangle (%.3f,%.2f);" % (color, x0 + 4.5, y + dy, x0 + 4.5 + w,
                                                                         y + dy - 0.28))
            lines.append(r"\node[anchor=west,font=\sffamily\scriptsize] at (%.3f,%.2f) {%.0f};" %
                         (x0 + 4.55 + w, y + dy - 0.14, value))
        y -= 0.9
    lines.append(r"\draw (%.2f,%.2f) -- (%.3f,%.2f);" % (x0 + 4.5, y + 0.3, x0 + 4.5 + axis_max * scale, y + 0.3))
    for t in range(0, axis_max + 1, step):
        lines.append(r"\draw (%.3f,%.2f) -- (%.3f,%.2f) node[below,font=\sffamily\scriptsize] {%d};" %
                     (x0 + 4.5 + t * scale, y + 0.3, x0 + 4.5 + t * scale, y + 0.2, t))
    lines.append(r"\node[font=\sffamily\scriptsize] at (%.3f,%.2f) {%s};" %
                 (x0 + 4.5 + axis_max * scale / 2, y - 0.4, unit))
    return y - 0.9


def diagnosis_tex(p):
    situ = {r["variant"]: r for r in p["in_situ_lookup"]}
    only = p["lookup_only_ns_per_probe"]
    lines = ["% Editable source for lookup_diagnosis.pdf, written by make_figures.py from analysis/profile_local.json",
             r"\documentclass[border=6pt]{standalone}", r"\usepackage{tikz}", r"\begin{document}",
             r"\begin{tikzpicture}[font=\sffamily\small]"]
    rows = [("4 GiB table, 32-byte slots\\\\combined loop (pC)", situ["inline_lookup"]),
            ("4 GiB table, 32-byte slots\\\\probe pipeline (pP)", situ["pipelined_lookup"]),
            ("2 GiB table, 16-byte slots\\\\same pipeline (pK)", situ["compact_pipelined"]),
            ("32 MiB filter + 16-byte slots\\\\two-level table (pT)", situ["filter_pipelined"])]
    y = bars(lines, "In-situ lookup cost, marginal ns per probe (over keys alone, %.0f ns)" %
             p["compute_ns_per_probe_roots_conv_canon"], 0, 0,
             [(label, r["lookup_ns_per_probe_thp"], r["lookup_ns_per_probe_4k"]) for label, r in rows],
             0.018, 450, 50, "ns per probe (median of %d rounds, %d probes, target w11)" % (p["rounds"], p["probes"]))
    rows2 = [("4 GiB table, no prefetch", "lookup_independent"), ("4 GiB table, prefetched", "lookup_prefetched_base"),
             ("2 GiB 16-byte, no prefetch", "lookup_independent_compact"),
             ("2 GiB 16-byte, prefetched", "lookup_prefetched_compact"),
             ("32 MiB filter, no prefetch", "lookup_independent_filter"),
             ("32 MiB filter, prefetched", "lookup_prefetched_filter")]
    y = bars(lines, "Lookup-only loops over the same keys (batches of one state's 332 keys)", 0, y,
             [(label, only[k]["thp"], only[k]["4k"]) for label, k in rows2], 0.05, 140, 20, "ns per lookup")
    lines.append(r"\fill[blue!65] (0,%.2f) rectangle ++(0.3,0.25); \node[anchor=west,font=\sffamily\scriptsize] at "
                 r"(0.35,%.2f) {2 MiB pages (THP via glibc tunable; the runner's default)};" % (y, y + 0.12))
    lines.append(r"\fill[blue!25] (7.2,%.2f) rectangle ++(0.3,0.25); \node[anchor=west,font=\sffamily\scriptsize] at "
                 r"(7.55,%.2f) {4 KiB pages};" % (y, y + 0.12))
    lines.append(r"\node[anchor=west,font=\sffamily\scriptsize,text=black!70] at (0,%.2f) {Diagnostic: cloud-agent "
                 r"VM (shared Intel Xeon guest), profiler variants of the derived producer. Not a speedup claim.};" %
                 (y - 0.45))
    lines += [r"\end{tikzpicture}", r"\end{document}"]
    return "\n".join(lines) + "\n"


def diagram_tex():
    return r"""% Editable source for two_level_table.pdf, written by make_figures.py
\documentclass[border=6pt]{standalone}
\usepackage{tikz}
\usetikzlibrary{positioning,arrows.meta}
\begin{document}
\begin{tikzpicture}[font=\sffamily\small, b/.style={draw, rounded corners, minimum height=0.8cm, align=center},
                    >={Stealth}]
\node[anchor=west,font=\sffamily\bfseries] at (-0.2,2.0) {One index state, about 332 partner probes, in the pipeline's order};
\node[b, fill=blue!15] (r) at (1.0,1.0) {batched\\root solve};
\node[b, fill=yellow!20, right=0.35 of r] (k) {to\_normal + lift\_scan\\+ prefetch filter word, x332};
\node[b, fill=green!15, right=0.35 of k] (f) {filter test x332\\(about 97.6\% rejected);\\prefetch survivors' slots};
\node[b, fill=red!20, right=0.35 of f] (l) {exact 16-byte lookup\\of each survivor\\(about 8 per state)};
\node[b, fill=black!5, right=0.35 of l] (h) {hit: lift,\\relation check};
\draw[->] (r) -- (k); \draw[->] (k) -- (f); \draw[->] (f) -- (l); \draw[->] (l) -- (h);
\node[anchor=west,font=\sffamily\bfseries] at (-0.2,-0.4) {Filter: 2\textsuperscript{22} words of 64 bits (32 MiB, 16 huge pages), 5 bits per key in one word};
\draw[fill=green!10] (0,-1.5) rectangle (12,-0.9);
\foreach \x in {0.6,1.2,...,11.4} { \draw (\x,-1.5) -- (\x,-0.9); }
\node[font=\sffamily\scriptsize] at (6,-1.8) {word = top 22 bits of h(key); bits = five 6-bit groups of h's low 30 bits; hit iff all five set};
\node[anchor=west,font=\sffamily\bfseries] at (-0.2,-2.5) {Slot: one 128-bit word, 2\textsuperscript{27} slots (2 GiB), same hash and linear probing as the 32-byte table};
\draw[fill=red!10] (0,-3.5) rectangle (7.47,-2.9) node[midway] {key: 83-bit normal-basis word};
\draw[fill=orange!15] (7.47,-3.5) rectangle (11.43,-2.9) node[midway] {value: 4 fields x 11 bits};
\draw[fill=black!15] (11.43,-3.5) rectangle (11.52,-2.9);
\node[font=\sffamily\scriptsize,anchor=west] at (11.6,-3.2) {occupied};
\node[font=\sffamily\scriptsize] at (0,-3.75) {0}; \node[font=\sffamily\scriptsize] at (7.47,-3.75) {83};
\node[font=\sffamily\scriptsize] at (11.43,-3.75) {127};
\node[anchor=west,font=\sffamily\scriptsize,text=black!70,align=left] at (-0.2,-4.5) {No false negatives, so a
rejected key is absent; a false positive only costs a lookup that misses. Survivors are consumed in probe order\\
with the probe counter set to their position: probes, relation and scalar are the pipeline's on every target.};
\end{tikzpicture}
\end{document}
"""


def result_tex(path):
    res = json.loads(path.read_text())
    s = res["statistics"]

    def pick(k, label, kind="", f=None):
        v = s[k] if f is None else s[k][f]
        if "estimate" in v:
            return (label, v["estimate"], v["ci95"], s["primary_units"], kind)
        return (label, v["means"]["estimate"], v["means"]["ci95"], s["primary_units"], kind)

    R = [pick("primary_R_means", "PRIMARY R\\_m: pipeline / filter table (means)", "p"),
         pick("primary_R_geomeans", "R\\_g (geomeans)"),
         pick("primary_R_means_slice_bootstrap", "R\\_m, slice bootstrap"),
         pick("primary_probes_P_over_T", "probes pipeline / filter (must be 1)"),
         pick("primary_aa_T_over_Taa", "A/A filter / filter", "c"),
         pick("primary_planted_X_over_T", "planted filter+table lookups / filter", "c"),
         pick("cold_P_over_T", "cold (setup + online) pipeline / filter"),
         pick("secondary_P_over_K", "pipeline / compact slots only"),
         pick("secondary_K_over_T", "compact only / filter"),
         pick("secondary_T_over_T29", "32 MiB filter / 64 MiB filter"),
         pick("rho_gap_rT_over_pT", "tuned rho / filter table (means)"),
         pick("rho_gap_rT_over_pP", "tuned rho / pipeline (means)"),
         pick("old_fresh16_P_over_T", "16 fresh pipeline / filter (means)", "s")]
    R[-1] = R[-1][:3] + (16,) + R[-1][4:]  # the old Q0 + fresh block: 16 fresh points
    x = lambda v: math.log(max(v, 1e-9), 2)  # noqa: E731
    lo_axis, hi_axis, n = 0.5, 16.0, len(R)
    L = ["% Editable source for result.pdf, written by make_figures.py from the run's result.json",
         "\\documentclass[tikz,border=6pt]{standalone}", "\\usepackage[T1]{fontenc}", "\\begin{document}",
         "\\begin{tikzpicture}[font=\\sffamily\\footnotesize,x=18mm,y=-5.6mm]"]
    for v in (0.5, 1, 2, 4, 8, 16):
        L.append("\\draw[gray!35] (%.4f,-0.6) -- (%.4f,%d); \\node[gray] at (%.4f,%.1f) {%g};" % (x(v), x(v), n, x(v), n + 0.5, v))
    L.append("\\draw[red!70!black,dashed] (0,-0.6) -- (0,%d);" % n)
    L.append("\\node at (0,%.1f) {ratio (log scale); bars: estimate; whiskers: 95\\%% bootstrap};" % (n + 1.3))
    L.append("\\node[anchor=west,font=\\sffamily\\bfseries] at (-9.5,-1.5) {Primary: %s};" % res["decision"]["primary"])
    for i, (label, est, (lo, hi), units, kind) in enumerate(R):
        col = {"p": "orange!60", "c": "gray!45", "s": "blue!20"}.get(kind, "blue!30")
        L.append("\\node[anchor=east] at (%.4f,%d) {%s};" % (x(lo_axis) - 0.1, i, label))
        L.append("\\fill[%s] (0,%f) rectangle (%.4f,%f);" % (col, i - 0.3, x(est), i + 0.3))
        L.append("\\draw (%.4f,%d) -- (%.4f,%d); \\draw (%.4f,%f) -- (%.4f,%f); \\draw (%.4f,%f) -- (%.4f,%f);"
                 % (x(lo), i, x(hi), i, x(lo), i - 0.15, x(lo), i + 0.15, x(hi), i - 0.15, x(hi), i + 0.15))
        L.append("\\node[anchor=west,font=\\sffamily\\scriptsize] at (%.4f,%d) {%.4f [%.4f, %.4f], n=%d};" % (x(hi_axis) + 0.05, i, est, lo, hi, units))
    L += ["\\end{tikzpicture}", "\\end{document}", ""]
    return "\n".join(L)


def main():
    if len(sys.argv) > 1:
        render("result", result_tex(Path(sys.argv[1]).resolve()))
    p = json.loads((HERE / "analysis" / "profile_local.json").read_text())
    render("lookup_diagnosis", diagnosis_tex(p))
    render("two_level_table", diagram_tex())


if __name__ == "__main__":
    main()
