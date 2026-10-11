#!/usr/bin/env python3
"""Assumption-status summary chart for REPORT-2026-10-06.

Counts are read from ic_assumptions.dot (assumption ellipses by fill color,
legend excluded), not hand-typed, so the figure cannot drift from the graph.
Outputs figures/assumption_status.pdf and .png (vector PDF for the report).
"""
import pathlib
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = pathlib.Path(__file__).resolve().parent
DOT = HERE / "ic_assumptions.dot"
OUT_PDF = HERE / "figures" / "assumption_status.pdf"
OUT_PNG = HERE / "figures" / "assumption_status.png"

# fillcolor -> (label, bar color) matching the DOT legend
STATUS = {
    "#bbf7d0": ("proved /\nchecked", "#22c55e"),
    "#fef9c3": ("heuristic +\nmeasured", "#eab308"),
    "#fed7aa": ("open", "#f97316"),
    "#fecaca": ("refuted", "#ef4444"),
    "#ddd6fe": ("conditional", "#8b5cf6"),
}

text = DOT.read_text()
counts: dict[str, int] = {k: 0 for k in STATUS}
for m in re.finditer(r'fillcolor="(#[0-9a-f]{6})"', text):
    c = m.group(1).lower()
    if c in counts:
        counts[c] += 1
# Legend contributes one ellipse per status; exclude it.
for k in counts:
    counts[k] -= 1
assert all(v >= 0 for v in counts.values()), counts
total = sum(counts.values())
assert total == 32, f"expected 32 assumptions, got {total}: {counts}"

labels = [STATUS[k][0] for k in STATUS]
values = [counts[k] for k in STATUS]
colors = [STATUS[k][1] for k in STATUS]

fig, ax = plt.subplots(figsize=(7.5, 3.2))
bars = ax.bar(labels, values, color=colors, edgecolor="black", linewidth=0.8)
ax.set_ylabel("assumptions (n=32)")
ax.set_title("IC-for-ECDLP assumption graph: status summary (from DOT source)")
ax.set_ylim(0, max(values) + 2)
for b, v in zip(bars, values):
    ax.text(b.get_x() + b.get_width() / 2, v + 0.25, str(v), ha="center", fontsize=11)
fig.text(
    0.5,
    0.01,
    "Green proved/checked; yellow heuristic+measured; orange open; red refuted; violet conditional. Counts from DOT source, not new measurements.",
    ha="center",
    va="bottom",
    fontsize=7,
    color="#374151",
)
fig.tight_layout(rect=(0, 0.06, 1, 1))
OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT_PDF)
fig.savefig(OUT_PNG, dpi=200)
print(f"counts={counts} total={total}")
print(f"wrote {OUT_PDF} and {OUT_PNG}")
