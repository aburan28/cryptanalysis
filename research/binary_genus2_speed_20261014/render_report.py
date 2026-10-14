#!/usr/bin/env python3
"""Layout only: render already-recorded values. No searches or research math."""
import json
import os
import argparse
from pathlib import Path
import subprocess
os.environ.setdefault("MPLCONFIGDIR", "/tmp/genus2-speed-matplotlib")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--run-id", default="run-20261014T2034Z")
parser.add_argument("--study-root", type=Path, default=Path(__file__).resolve().parent)
parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent)
args = parser.parse_args()
root = args.output_dir.resolve()
(root / "figures").mkdir(parents=True, exist_ok=True)
run = args.study_root.resolve() / "runs" / args.run_id
data = json.loads((run / "snapshot.json").read_text())
plt.rcParams.update({"svg.fonttype": "none", "font.size": 10})

def save(fig, name):
    for ext in ("svg", "pdf", "png"):
        path = root / "figures" / f"{name}.{ext}"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        if ext == "svg":
            path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")
    plt.close(fig)

fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.5), sharey=True)
for panel, ax in zip(data["calibration"], axes):
    for x, arm in enumerate(panel["arms"]):
        ax.vlines(x, arm["min_steps_per_second"], arm["max_steps_per_second"], color="#457b9d", linewidth=2)
        ax.scatter([x], [arm["median_steps_per_second"]], color="#1d3557", zorder=3)
    ax.set_xticks([0, 1], ["Elliptic", "Checked Cantor\n+ image conversions"])
    ax.set_title(f"a={panel['a']}, matched prefixes")
    ax.set_yscale("log")
    ax.set_ylim(5000, 2000000)
    ax.set_xlim(-0.5, 1.5)
    ax.grid(axis="y", alpha=0.25)
axes[0].set_ylabel("walk steps / second (log scale)")
fig.text(0.5, -0.02, "Five A/B rounds: median and observed range; L0 VM timings. Prefixes are not full solves.", ha="center", fontsize=8)
fig.tight_layout()
save(fig, "prefix-rates")

refs = {r["directory"]: r for r in data["references"]}
fig, ax = plt.subplots(figsize=(9.2, 3.5))
for arm, color, marker, label in [("elliptic", "#346da0", "o", "Direct elliptic"), ("image_inverse", "#26734b", "s", "Jacobian image inverse to E")]:
    rows = [refs[f"reference-a1-0-ab-{i}-{arm}"]["result"] for i in range(5)]
    ax.plot(range(1, 6), [r["search_seconds"] for r in rows], color=color, marker=marker, label=label)
ax.set_xlabel("paired full-solve round (same target and public seeds)")
ax.set_ylabel("optimized rho search wall time (seconds)")
ax.set_ylim(bottom=0)
ax.set_xticks(range(1, 6))
ax.grid(alpha=0.25)
ax.legend()
fig.text(0.5, -0.02, "a=1 target 0; every run recovered and externally verified the full-order log. L0; no admitted speed ratio.", ha="center", fontsize=8)
fig.tight_layout()
save(fig, "full-reference-rounds")

states = {s["checkpoint"]: s for s in data["checkpoint_snapshots"]}
matched = []
for arm, label in [("elliptic", "Direct E"), ("image_inverse", "Image inverse\nto E"), ("jacobian", "Native checked\nCantor walk")]:
    s = states.get(f"a1-0-{arm}.checkpoint.json")
    if s and s.get("verification", {}).get("jacobian_verified"):
        matched.append((label, s))
if len(matched) == 3:
    fig, ax = plt.subplots(figsize=(9.2, 3.4))
    ax.bar([x[0] for x in matched], [x[1]["search_seconds"] for x in matched], color=["#346da0", "#26734b", "#ad6143"])
    ax.set_yscale("log")
    ax.set_ylabel("completed search wall time (seconds; log scale)")
    ax.grid(axis="y", alpha=0.25)
    fig.text(0.5, -0.02, "One full-subgroup solve per arm, a=1 target 0; same resumable method. L0 descriptive timings.", ha="center", fontsize=8)
    fig.tight_layout()
    save(fig, "matched-full-solve")

completed_targets = [i for i in range(8) if all(
    (states.get(f"a1-{i}-{arm}.checkpoint.json", {}).get("verification") or {}).get("jacobian_verified")
    for arm in ("elliptic", "image_inverse", "jacobian"))]
fig, ax = plt.subplots(figsize=(9.2, 3.2))
for offset, arm, color, label in [(-0.24, "elliptic", "#346da0", "Direct E"),
    (0, "image_inverse", "#26734b", "Image inverse to E"),
    (0.24, "jacobian", "#ad6143", "Checked Cantor + conversions")]:
    ax.bar([i + offset for i in range(len(completed_targets))],
        [states[f"a1-{i}-{arm}.checkpoint.json"]["search_seconds"] for i in completed_targets],
        width=0.23, color=color, label=label)
ax.set_xticks(range(len(completed_targets)), [f"Q_{i}" for i in completed_targets])
ax.set_yscale("log")
ax.set_ylabel("completed search wall time (seconds; log scale)")
ax.set_xlabel("independent a=1 public target; matched resumable walks")
ax.grid(axis="y", alpha=0.25)
ax.legend(fontsize=8, loc="upper left", bbox_to_anchor=(1.01, 1))
fig.text(0.5, -0.03, f"{args.run_id}: both-group verification receipts; L0 observations, no admitted speed ratio.", ha="center", fontsize=8)
fig.tight_layout()
save(fig, "matched-targets")

# All numerical entries below are copied from the native summary.
lines = []
for panel in data["calibration"]:
    for arm in panel["arms"]:
        name = "elliptic" if arm["arm"] == "elliptic" else "checked Cantor"
        lines.append(f"{panel['a']} & {name} & {arm['median_steps_per_second']:,.0f} & {arm['min_steps_per_second']:,.0f}--{arm['max_steps_per_second']:,.0f} " + chr(92) * 2)
(root / "calibration-table.tex").write_text(
    r"\begin{tabular}{rlrr}\toprule" + "\n" +
    r"$a$ & Arm & Median steps/s & Observed range\\\midrule" + "\n" +
    "\n".join(lines) + "\n" + r"\bottomrule\end{tabular}" + "\n")
lines = []
for arm, label in [("elliptic", "Direct E"), ("image_inverse", "Image inverse to E"), ("jacobian", "Native checked Cantor")]:
    s = states.get(f"a1-0-{arm}.checkpoint.json")
    if s and s.get("verification", {}).get("jacobian_verified"):
        lines.append(f"{label} & {s['steps']:,} & {s['search_seconds']:.3f} & verified " + chr(92) * 2)
    else:
        lines.append(f"{label} & --- & --- & pending " + chr(92) * 2)
(root / "matched-table.tex").write_text(
    r"\begin{tabular}{lrrl}\toprule" + "\n" +
    r"Matched resumable arm & Steps & Search seconds & Status\\\midrule" + "\n" +
    "\n".join(lines) + "\n" + r"\bottomrule\end{tabular}" + "\n")
lines = []
for i in completed_targets:
    rows = [states[f"a1-{i}-{arm}.checkpoint.json"] for arm in ("elliptic", "image_inverse", "jacobian")]
    lines.append(f"$Q_{i}$ & {rows[0]['steps']:,} & " + " & ".join(f"{s['search_seconds']:.3f}" for s in rows) + " " + chr(92) * 2)
(root / "matched-targets-table.tex").write_text(
    r"\begin{tabular}{lrrrr}\toprule" + "\n" +
    r"Target & Steps in each arm & E (s) & Inverse/E (s) & Cantor (s)\\\midrule" + "\n" +
    "\n".join(lines) + "\n" + r"\bottomrule\end{tabular}" + "\n")
subprocess.run(["pdflatex", "-halt-on-error", "-interaction=nonstopmode", "report.tex"], cwd=root, check=True)
