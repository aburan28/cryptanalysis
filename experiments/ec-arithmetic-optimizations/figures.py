#!/usr/bin/env python3
"""Measured-speedup chart for REPORT-2026-10-06 (ec-arithmetic-optimizations).

Every bar is a number quoted verbatim from the committed docs on this tree
(see SOURCES); this script only plots them. Outputs
figures/speedups.pdf and .png (vector PDF for the report).
"""
import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = pathlib.Path(__file__).resolve().parent
OUT_PDF = HERE / "figures" / "speedups.pdf"
OUT_PNG = HERE / "figures" / "speedups.png"

# (label, speedup, source) -- all verified against origin/main 6350e7f7.
BARS = [
    ("grumpy vs BSGS\nwhole-group S", 1.33 / 1.18, "docs/ALGORITHMS.md"),
    ("GLV j1728-26\nvs neg-rho", 1.34, "docs/BENCHMARKS.md"),
    ("Sage point-construct\nvs native binary", 1.56, "sage-binary-batch/README.md"),
    ("Sage native field\nvs python batch", 1.61, "sage-binary-batch/README.md"),
    ("GLV j0-32\nvs neg-rho", 1.71, "docs/BENCHMARKS.md"),
    ("Sage native Frobenius\nvs python map", 2.15, "sage-binary-batch/README.md"),
    ("precomp threads x4\nvs 1 core", 3.9, "docs/BENCHMARKS.md"),
    ("precomp build opts\nvs naive (1 core)", 2.26 / 0.44, "docs/BENCHMARKS.md"),
    ("GPU inv sharing\nmults per step", 99 / 18, "docs/GPU.md"),
    ("batch inversion\naffine add", 232.2 / 21.8, "docs/BENCHMARKS.md"),
    ("Cheon@48b\nvs rho ops", 18.6, "docs/BENCHMARKS.md"),
]

labels = [b[0] for b in BARS]
values = [b[1] for b in BARS]

fig, ax = plt.subplots(figsize=(8.0, 4.6))
bars = ax.barh(labels, values, color="#22c55e", edgecolor="black", linewidth=0.8)
ax.set_xlabel("measured speedup (x, higher is better)")
ax.set_title("EC arithmetic: measured optimization speedups (committed docs, this tree)")
for b, v in zip(bars, values):
    ax.text(v + 0.15, b.get_y() + b.get_height() / 2, f"{v:.2f}x",
            va="center", fontsize=9)
ax.set_xlim(0, max(values) * 1.18)
fig.text(0.5, 0.01,
         "Primary-suite figures; Sage ratios must not be multiplied into cumulative-vs-stock claims. "
         "Not new measurements.",
         ha="center", va="bottom", fontsize=7, color="#374151")
fig.tight_layout(rect=(0, 0.05, 1, 1))
OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT_PDF)
fig.savefig(OUT_PNG, dpi=200)
print(f"wrote {OUT_PDF} and {OUT_PNG}")
