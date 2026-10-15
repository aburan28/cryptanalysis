#!/usr/bin/env python3
"""Figures of the probe-pipeline experiment (diagnostic profile and the pipeline diagram).

Each figure is an editable TikZ source (`figures/<name>.tex`) rendered with
pdflatex to `figures/<name>.pdf` and with pdftoppm to `figures/<name>.png`
(the machinery of `claude/n83-scan-order`'s `make_figures.py`).

* `probe_profile`: per-probe time of each probe-path component, stacked, for
  the combined loop (inline lookup) and the pipelined loop, from
  `analysis/profile_local.json` (cloud-agent VM, diagnostic only), with each
  component's callgrind instructions per probe in the legend.
* `probe_pipeline`: the two loop structures.

The Tier 1 result figure is owed after the run.
"""

import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIG = HERE / "figures"
ORDER = (("root_solve", "root solve", "blue!55"), ("conversion", "conversion", "orange!70"),
         ("canonicalization", "canonicalization", "green!50!black!60"), ("lookup", "lookup", "red!60"))


def render(name, body):
    FIG.mkdir(exist_ok=True)
    (FIG / (name + ".tex")).write_text(body)
    subprocess.run(["pdflatex", "-interaction=nonstopmode", name + ".tex"], cwd=FIG, check=True,
                   stdout=subprocess.DEVNULL)
    subprocess.run(["pdftoppm", "-png", "-r", "150", "-singlefile", name + ".pdf", name], cwd=FIG, check=True)
    for suffix in (".aux", ".log"):
        (FIG / (name + suffix)).unlink(missing_ok=True)


def profile_tex(p):
    comps = {c["component"]: c for c in p["components"]}
    rows = [("combined loop (pC)", [comps[k]["ns_per_probe"] for k, _, _ in ORDER]),
            ("pipelined loop (pP)", [comps[k]["ns_per_probe"] for k, _, _ in ORDER[:3]] +
             [p["pipelined_lookup_ns_per_probe"]])]
    s = 0.022  # cm per ns
    lines = ["% Editable source for probe_profile.pdf, written by make_figures.py from analysis/profile_local.json",
             r"\documentclass[border=6pt]{standalone}", r"\usepackage{tikz}", r"\begin{document}",
             r"\begin{tikzpicture}[font=\sffamily\small]",
             r"\node[anchor=west,font=\sffamily\bfseries] at (0,3.2) {n=83 K600 probe path, ns per probe "
             r"(diagnostic: cloud-agent VM, target w11, %d probes)};" % p["probes"]]
    for i, (label, parts) in enumerate(rows):
        y = 2.0 - 1.1 * i
        lines.append(r"\node[anchor=east] at (3.8,%.2f) {%s};" % (y + 0.35, label))
        x = 4.0
        for (key, _, color), v in zip(ORDER, parts):
            w = v * s
            lines.append(r"\fill[%s] (%.3f,%.2f) rectangle (%.3f,%.2f);" % (color, x, y, x + w, y + 0.7))
            if w > 0.7:
                lines.append(r"\node[white] at (%.3f,%.2f) {%.0f};" % (x + w / 2, y + 0.35, v))
            x += w
        lines.append(r"\node[anchor=west] at (%.3f,%.2f) {%.0f ns};" % (x + 0.1, y + 0.35, sum(parts)))
    lines.append(r"\draw (4,0.6) -- (%.3f,0.6);" % (4 + 500 * s))
    for t in range(0, 501, 100):
        lines.append(r"\draw (%.3f,0.6) -- (%.3f,0.5) node[below,font=\sffamily\scriptsize] {%d};" %
                     (4 + t * s, 4 + t * s, t))
    lines.append(r"\node at (%.3f,-0.2) {ns per probe (minimum of %d rounds)};" % (4 + 250 * s, p["rounds"]))
    x = 0
    for key, label, color in ORDER:
        lines.append(r"\fill[%s] (%.2f,-1.0) rectangle ++(0.3,0.3);" % (color, x))
        lines.append(r"\node[anchor=west] at (%.2f,-0.85) {%s, %.0f instr/probe};" %
                     (x + 0.35, label, comps[key]["instructions_per_probe"]))
        x += 5.2
    lines.append(r"\node[anchor=west,font=\sffamily\scriptsize,text=black!70] at (0,-1.6) {Instructions: callgrind, "
                 r"one pass on a constructed K=40 base (66,400 probes). Times: profiler variants on the K600 table, "
                 r"THP via glibc tunable. Not a speedup claim.};")
    lines += [r"\end{tikzpicture}", r"\end{document}"]
    return "\n".join(lines) + "\n"


def diagram_tex():
    return r"""% Editable source for probe_pipeline.pdf, written by make_figures.py
\documentclass[border=6pt]{standalone}
\usepackage{tikz}
\usetikzlibrary{positioning,arrows.meta}
\begin{document}
\begin{tikzpicture}[font=\sffamily\small, b/.style={draw, rounded corners, minimum height=0.8cm, align=center},
                    >={Stealth}]
\node[anchor=west,font=\sffamily\bfseries] at (-0.2,2.1) {One index state: 2n = 166 candidates, about 332 partner probes};
\node[anchor=west,font=\sffamily\bfseries] at (-0.2,1.3) {combined (pC): one probe at a time};
\node[b, fill=blue!15] (r1) at (1.3,0.4) {batched\\root solve};
\node[b, fill=orange!20, right=0.4 of r1] (c1) {to\_normal};
\node[b, fill=green!15, right=0.4 of c1] (k1) {lift\_scan};
\node[b, fill=red!20, right=0.4 of k1] (l1) {table lookup\\(waits for DRAM)};
\node[b, fill=black!5, right=0.4 of l1] (h1) {hit: lift,\\relation check};
\draw[->] (r1) -- (c1); \draw[->] (c1) -- (k1); \draw[->] (k1) -- (l1); \draw[->] (l1) -- (h1);
\draw[->] (l1.south) to[bend left=25] node[below,font=\sffamily\scriptsize] {next partner} (c1.south);
\node[anchor=west,font=\sffamily\bfseries] at (-0.2,-1.3) {pipelined (pP): all keys first, then all lookups, same order};
\node[b, fill=blue!15] (r2) at (1.3,-2.2) {batched\\root solve};
\node[b, fill=yellow!20, right=0.4 of r2] (k2) {to\_normal + lift\_scan\\+ prefetch home slot, x332};
\node[b, fill=red!20, right=0.4 of k2] (l2) {lookups x332\\(lines in flight)};
\node[b, fill=black!5, right=0.4 of l2] (h2) {hit: lift,\\relation check};
\draw[->] (r2) -- (k2); \draw[->] (k2) -- (l2); \draw[->] (l2) -- (h2);
\node[anchor=west,font=\sffamily\scriptsize,text=black!70,align=left] at (-0.2,-3.4) {Same probe counter, lookup,
lift, relation check and first-hit return: probes, relation and scalar are pC's.\\ Extra work: only the keys after
the successful probe in the final state (at most 4n - 1 canonicalizations).};
\end{tikzpicture}
\end{document}
"""


def main():
    p = json.loads((HERE / "analysis" / "profile_local.json").read_text())
    render("probe_profile", profile_tex(p))
    render("probe_pipeline", diagram_tex())


if __name__ == "__main__":
    main()
