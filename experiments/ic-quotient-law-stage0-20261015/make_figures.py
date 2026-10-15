#!/usr/bin/env python3
"""Figures for the stage-0 report, written from analysis.json only.

    python3 -I make_figures.py analysis.json figures/
    (cd figures && pdflatex probe_law.tex && pdflatex price_product.tex)
"""
import json
import math
import sys
from pathlib import Path

d = json.load(open(sys.argv[1]))
out = Path(sys.argv[2])
out.mkdir(exist_ok=True)

# Figure 1, left: measured / predicted probes per row (one experiment per row).
short = {
    "s23 k1n47 (m=3)": None,  # outside the m=2 claim; drawn separately
}
rows = [r for r in d["price_rows"] if not r["row"].startswith("n83 K600, Tier 1")
        and not r["row"].startswith("n83 K600, reconcile")]  # K600 probe counts are work-identical across its three runs
lines = ["x y lo hi label"]
for i, r in enumerate(rows):
    if r["row"] == "s23 k1n47 (m=3)":
        continue
    lab = r["row"].split(" (")[0].replace("s23 ", "").replace(", BL arm run 38689817618", "").replace(" root index, GHA 37156392134", "")
    lab = lab.replace("n83 ", "").replace("_dense", "d").replace("_regular", "r").replace(" ", "")
    lines.append("%d %.5f %.5f %.5f %s" % (len(lines), r["probe_ratio"], r["probe_ratio_ci95"][0],
                                           r["probe_ratio_ci95"][1], lab))
(out / "probe_ratio.dat").write_text("\n".join(lines) + "\n")
n_rows = len(lines) - 1

lines = ["x cv lo hi nlo nhi label"]
for x in d["probe_distributions"]:
    if "m=3" in x["panel"] or "BL online" in x["panel"]:
        continue
    lab = x["panel"].split(" (")[0].replace("s23 ", "").replace("n61 K500 root index", "n61K500")
    lab = lab.replace("n83 ", "").replace("_dense", "d").replace("_regular", "r").replace(" ", "")
    lines.append("%d %.4f %.4f %.4f %.4f %.4f %s" % (len(lines), x["cv"], x["cv_ci95_bootstrap"][0],
                 x["cv_ci95_bootstrap"][1], x["cv_exponential_null_95"][0], x["cv_exponential_null_95"][1], lab))
(out / "probe_cv.dat").write_text("\n".join(lines) + "\n")
n_cv = len(lines) - 1

tex1 = r"""\documentclass[border=4pt]{standalone}
\usepackage{lmodern}
\usepackage{pgfplots}
\pgfplotsset{compat=1.16}
\begin{document}
\begin{tikzpicture}
\begin{axis}[axis on top, name=left, width=9cm, height=6.2cm, ymode=log, ymin=0.3, ymax=6,
  xmin=0.4, xmax=%(n)d.6, xtick=data, xticklabels from table={probe_ratio.dat}{label},
  x tick label style={rotate=60, anchor=east, font=\scriptsize},
  ylabel={measured / predicted probes}, ytick={0.5,0.7,1,1.3,2,4}, yticklabels={0.5,0.7,1,1.3,2,4},
  title={\small (a) probes per target vs $r/(A\cdot\#\mathrm{states})$}, title style={font=\small}]
\fill[green!12] (axis cs:0.4,0.85) rectangle (axis cs:%(n)d.6,1.15);
\draw[red!60, dashed] (axis cs:0.4,0.7) -- (axis cs:%(n)d.6,0.7);
\draw[red!60, dashed] (axis cs:0.4,1.3) -- (axis cs:%(n)d.6,1.3);
\addplot[only marks, mark=*, mark size=1.8pt, error bars/.cd, y dir=both, y explicit]
  table[x=x, y=y, y error plus expr=\thisrow{hi}-\thisrow{y}, y error minus expr=\thisrow{y}-\thisrow{lo}] {probe_ratio.dat};
\end{axis}
\begin{axis}[axis on top, clip=true, at={(left.east)}, anchor=west, xshift=1.6cm, width=9.4cm, height=6.2cm, ymin=0.4, ymax=2.4,
  xmin=0.4, xmax=%(m)d.6, xtick=data, xticklabels from table={probe_cv.dat}{label},
  x tick label style={rotate=60, anchor=east, font=\scriptsize},
  ylabel={coefficient of variation of probes},
  title={\small (b) probe-count CV vs the exponential model}, title style={font=\small}]
\fill[red!8] (axis cs:0.4,1.5) rectangle (axis cs:%(m)d.6,2.4);
\fill[red!8] (axis cs:0.4,0.4) rectangle (axis cs:%(m)d.6,0.6);
\addplot[only marks, mark=-, mark size=4pt, gray, error bars/.cd, y dir=both, y explicit]
  table[x=x, y expr=(\thisrow{nlo}+\thisrow{nhi})/2, y error plus expr=(\thisrow{nhi}-\thisrow{nlo})/2,
        y error minus expr=(\thisrow{nhi}-\thisrow{nlo})/2] {probe_cv.dat};
\addplot[only marks, mark=square*, mark size=1.6pt, blue!70!black, error bars/.cd, y dir=both, y explicit]
  table[x=x, y=cv, y error plus expr=\thisrow{hi}-\thisrow{cv}, y error minus expr=\thisrow{cv}-\thisrow{lo}] {probe_cv.dat};
\end{axis}
\end{tikzpicture}
\end{document}
""" % {"n": n_rows, "m": n_cv}
(out / "probe_law.tex").write_text(tex1)

# Figure 2: the n=83 price product, the idea's inferred prices against the measured ones.
bl = [r for r in d["price_rows"] if r["row"].startswith("n83 K600, BL arm")][0]
idea = {"c_probe": 375.0, "c_state": 2100.0, "c_step": 40.0, "formula": 231.0}
meas = {"c_probe": bl["c_probe_ns"], "c_state": bl["c_state_ns"], "c_step": bl["c_step_ns"],
        "formula": bl["formula_ratio"]}
lines = ["x idea meas label"]
for i, k in enumerate(["c_probe", "c_state", "c_step", "formula"]):
    lines.append("%d %.4f %.4f %s" % (i + 1, idea[k], meas[k], k.replace("_", "")))
lines.append("5 nan %.4f measured" % bl["ic_over_bl_measured"])
(out / "price_product.dat").write_text("\n".join(lines) + "\n")
lo, hi = bl["ic_over_bl_measured_ci95"]
tex2 = r"""\documentclass[border=4pt]{standalone}
\usepackage{lmodern}
\usepackage{pgfplots}
\pgfplotsset{compat=1.16}
\begin{document}
\begin{tikzpicture}
\begin{axis}[width=11cm, height=6.5cm, ymode=log, ybar=2pt, bar width=9pt, ymin=10, ymax=1e6,
  xtick={1,2,3,4,5}, xticklabels={{$c_{\rm probe}$ (ns)},{$c_{\rm state}$ (ns)},{$c_{\rm step}$ (ns)},
  {formula $\frac{c_{\rm probe}c_{\rm state}}{2.1\,c_{\rm step}^2}$},{measured IC/BL}},
  x tick label style={font=\scriptsize, align=center, text width=2.2cm},
  legend style={font=\scriptsize, at={(0.02,0.98)}, anchor=north west},
  title={\small n=83 K600, BL arm run 38689817618: the price product, inferred vs measured}]
\addplot[fill=orange!60] table[x=x, y=idea] {price_product.dat};
\addplot[fill=blue!55] table[x=x, y=meas] {price_product.dat};
\legend{idea's inferred prices (notes.md), this run's measured prices}
\draw[black, thick] (axis cs:5.12,%(lo).3f) -- (axis cs:5.12,%(hi).3f);
\end{axis}
\end{tikzpicture}
\end{document}
""" % {"lo": lo, "hi": hi}
(out / "price_product.tex").write_text(tex2)
print("rows", n_rows, "cv panels", n_cv)
