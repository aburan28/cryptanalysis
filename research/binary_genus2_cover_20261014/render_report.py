#!/usr/bin/env python3
"""Document layout only: plot recorded counts, render diagrams and typeset PDF.

No curve arithmetic, research execution, certificate checking, or new results.
"""
import json
import os
from pathlib import Path
import subprocess

os.environ.setdefault("MPLCONFIGDIR", "/tmp/genus2-matplotlib")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

root = Path(__file__).resolve().parent

def normalize_svg(path):
    """Remove insignificant renderer whitespace without changing the visual."""
    path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")

receipt = root / "runs/run-20261014T1442Z/n83-final.json"
data = json.loads(receipt.read_text())
plt.rcParams.update({"svg.fonttype": "none", "font.size": 10})
fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.2), sharey=True)
for a, ax in enumerate(axes):
    rows = [row for row in data["small_field_controls"] if row["a"] == a]
    labels = [row["field_size"] for row in rows]
    ax.plot(labels, [row["elliptic_projective_points"] for row in rows],
            marker="o", color="#346da0", label="elliptic curve E")
    ax.plot(labels, [row["genus2_projective_points"] for row in rows],
            marker="s", color="#26734b", label="genus-two curve C")
    ax.set_title(f"a={a}: exhaustive rational-point counts")
    ax.set_xlabel("field size q (elements)")
    ax.set_ylim(0, 27)
    ax.set_yticks([0, 4, 8, 12, 16, 20, 24])
    ax.grid(axis="y", alpha=0.25)
    ax.legend(loc="upper left", fontsize=9)
axes[0].set_ylabel("smooth-projective curve points (count)")
fig.text(0.5, 0.015, "run-20261014T1442Z · n83-final.json small_field_controls · complete counts; no sampling uncertainty",
         ha="center", fontsize=8)
fig.tight_layout(rect=(0, 0.05, 1, 1))
for extension in ["svg", "pdf", "png"]:
    fig.savefig(root / f"figures/counts.{extension}", dpi=150)
    if extension == "svg":
        normalize_svg(root / "figures/counts.svg")
plt.close(fig)
for extension in ["svg", "pdf"]:
    subprocess.run(["dot", f"-T{extension}", str(root / "figures/transfer.dot"),
                    "-o", str(root / f"figures/transfer.{extension}")], check=True)
    if extension == "svg":
        normalize_svg(root / "figures/transfer.svg")
subprocess.run(["pdflatex", "-halt-on-error", "-interaction=nonstopmode", "report.tex"],
               cwd=root, check=True)
