#!/usr/bin/env python3
"""Figures for README.md from the profile receipts (needs matplotlib).

    python3 figures.py results/*.jsonl
"""

from __future__ import annotations

import argparse
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import heuristics as H  # noqa: E402

COLORS = {
    "prefix": "#1b9e77", "geometric": "#66a61e", "geomtrace": "#e6ab02", "invariant": "#a6761d",
    "normal": "#7570b3", "kertrace": "#e7298a", "random": "#d95f02",
}


def excess_vs_degree(rows: list[dict], out: Path, mode: str) -> None:
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    rng = __import__("random").Random(1)
    for fam in H.FAMILY_ORDER + ["geomtrace"]:
        pts = [(r["excess"], r["D"]) for r in rows if r["family"] == fam and r["D"] is not None and not r["censored"]]
        if not pts:
            continue
        xs = [e + rng.uniform(-0.25, 0.25) for e, _ in pts]
        ys = [d + rng.uniform(-0.06, 0.06) for _, d in pts]
        ax.scatter(xs, ys, s=12, alpha=0.7, color=COLORS.get(fam, "grey"), label=fam)
    rule = H.fit_threshold_rule(rows).get(2)
    if rule:
        es = sorted({r["excess"] for r in rows})
        grid = [x / 4 for x in range(4 * min(es), 4 * max(es) + 1)]
        ax.step(grid, [rule["rule"]["base"] + sum(1 for t in rule["rule"]["thresholds"] if e < t) for e in grid],
                where="post", color="black", lw=1.2, label="fitted rule")
    ax.set_xlabel("linearization excess  e = n − dim V − dim V^(2)")
    ax.set_ylabel(f"mean solving degree ({mode})")
    ax.set_title("Two summands: the product profile sets the solving degree")
    ax.legend(fontsize=7, ncol=2, loc="upper right")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)


def cost_vs_l(rows: list[dict], out: Path, n: int, mode: str) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8))
    per = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r["n"] == n:
            per[r["family"]][r["l"]].append(r)
    for fam, byl in per.items():
        ls = sorted(byl)
        att = [H.geomean([x["ops"] for x in byl[l]]) for l in ls]
        rel = [H.geomean([x["ops_rel"] for x in byl[l]]) for l in ls]
        axes[0].plot(ls, att, "o-", color=COLORS.get(fam, "grey"), label=fam, ms=4)
        pts = [(l, v) for l, v in zip(ls, rel) if v]
        if pts:
            axes[1].plot([p[0] for p in pts], [p[1] for p in pts], "o-", color=COLORS.get(fam, "grey"), label=fam, ms=4)
    for ax, title in zip(axes, ("word operations per PDP query", "word operations per relation (÷ exact yield)")):
        ax.set_yscale("log")
        ax.set_xlabel("factor-base dimension l")
        ax.set_title(title, fontsize=10)
        ax.grid(alpha=0.3, which="both")
    axes[0].legend(fontsize=7)
    fig.suptitle(f"n = {n}, two summands, {mode}", fontsize=10)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("results", nargs="+", type=Path)
    ap.add_argument("--outdir", type=Path, default=HERE / "figures")
    args = ap.parse_args()
    cards = H.load(args.results)
    args.outdir.mkdir(exist_ok=True)
    rows = [H.features(c, "mxl") for c in cards if c["cell"]["m"] == 2 and c["cell"].get("formulation", "direct") == "direct"]
    excess_vs_degree(rows, args.outdir / "excess_vs_degree_m2.png", "MXL")
    rows_xl = [H.features(c, "xl") for c in cards if c["cell"]["m"] == 2 and c["cell"].get("formulation", "direct") == "direct"]
    excess_vs_degree(rows_xl, args.outdir / "excess_vs_degree_m2_xl.png", "XL")
    for n in (23, 41):
        cost_vs_l(rows, args.outdir / f"cost_vs_l_n{n}_m2.png", n, "MXL")
    print("wrote", sorted(p.name for p in args.outdir.glob("*.png")))


if __name__ == "__main__":
    main()
