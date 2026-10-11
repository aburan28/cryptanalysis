"""Figures for the ECC2K-130 isogeny-class hardness PDF (light mode, print)."""
import csv
import json
import math
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.abspath(os.path.join(HERE, "..", ".."))

# Reference palette, light mode (validated: slots 1-3 pass all-pairs; aqua needs direct labels)
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
SURFACE, INK, INK2, MUTED, GRID = "#ffffff", "#0b0b0b", "#52514e", "#8a8984", "#e6e5e0"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "axes.edgecolor": MUTED,
    "axes.labelcolor": INK2,
    "axes.titlecolor": INK,
    "xtick.color": INK2,
    "ytick.color": INK2,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.6,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.dpi": 220,
    "legend.frameon": False,
})


def save(fig, name):
    fig.savefig(os.path.join(HERE, name), bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)


# ---------- Figure 1: hardness by level ----------
def fig_levels():
    levels = ["E0 (crater, conductor 1)", "Floor, conductor 263\n(262 curves)",
              "Level p\n(p+1 $\\approx 2^{57}$ curves)", "Level 263p\n(262(p+1) $\\approx 2^{65}$ curves)"]
    native = [60.809, 64.326, 64.326, 64.326]
    eff_lo = [60.809, 60.809, 60.809, 60.809]
    eff_hi = [60.809, 60.809, 64.326, 64.326]
    fig, ax = plt.subplots(figsize=(6.6, 2.7))
    ys = list(range(len(levels)))[::-1]
    ax.axvline(60.809, color=MUTED, lw=1, ls=(0, (3, 3)), zorder=1)
    ax.text(60.809, len(levels) - 0.45, "E0 rho $2^{60.81}$", color=INK2, fontsize=8, ha="center", va="bottom")
    for y, n, lo, hi in zip(ys, native, eff_lo, eff_hi):
        if hi > lo:
            ax.plot([lo, hi], [y - 0.12, y - 0.12], color=BLUE, lw=5, solid_capstyle="round", alpha=0.35, zorder=2)
            ax.text((lo + hi) / 2, y - 0.34, "effective: unknown within this range", color=INK2, fontsize=7.5,
                    ha="center", va="top")
        ax.scatter([lo], [y - 0.12], s=58, color=BLUE, edgecolor=SURFACE, linewidth=1.5, zorder=4)
        ax.scatter([n], [y + 0.12], s=58, color=ORANGE, edgecolor=SURFACE, linewidth=1.5, zorder=4)
        ax.text(n + 0.12, y + 0.12, f"{n:.2f}", color=INK2, fontsize=8, va="center")
        if hi == lo:
            ax.text(lo - 0.12, y - 0.12, f"{lo:.2f}", color=INK2, fontsize=8, va="center", ha="right")
    ax.set_yticks(ys)
    ax.set_yticklabels(levels, fontsize=8.5, color=INK)
    ax.set_xlim(59.4, 65.4)
    ax.set_ylim(-0.7, len(levels) - 0.2)
    ax.set_xlabel("log2 of expected Pollard-rho iterations")
    ax.grid(axis="y", visible=False)
    ax.scatter([], [], s=40, color=ORANGE, label="native rho on the curve itself")
    ax.scatter([], [], s=40, color=BLUE, label="effective (best known route)")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.24), ncol=2, fontsize=8)
    save(fig, "fig_levels.png")


# ---------- Figure 2: volcano schematic ----------
def fig_volcano():
    fig, ax = plt.subplots(figsize=(6.6, 4.0))
    ax.set_xlim(0, 10)
    ax.set_ylim(-0.1, 6.2)
    ax.axis("off")
    box = dict(boxstyle="round,pad=0.25", fc=SURFACE, ec="none")
    ax.add_patch(Circle((5, 5.55), 0.3, color=BLUE, zorder=3))
    ax.text(5.45, 5.55, "E0: End = $O_K$, j = 1\nKoblitz curve; Frobenius $\\tau$ of degree 2",
            fontsize=8.5, va="center", color=INK)
    for cx in (2.6, 7.4):
        ax.add_patch(FancyArrowPatch((5 + (cx - 5) * 0.1, 5.22), (cx + (5 - cx) * 0.15, 3.85), arrowstyle="-|>",
                                     mutation_scale=10, color=INK2, lw=1, zorder=2))
    ax.text(5, 4.55, "264 isogenies of degree 263 from E0:\n2 back to E0, 262 down to the floor",
            ha="center", va="center", fontsize=7.8, color=INK2, bbox=box, zorder=4)
    for cx, lab in [(2.6, "orbit A: A000 … A130"), (7.4, "orbit B: B000 … B130")]:
        for i in range(131):
            a = 2 * math.pi * i / 131
            ax.add_patch(Circle((cx + 1.45 * math.cos(a), 3.35 + 0.42 * math.sin(a)), 0.035, color=BLUE,
                                alpha=0.85, zorder=3))
        ax.text(cx, 3.35, lab, ha="center", va="center", fontsize=8, color=INK)
    ax.text(5, 2.62, "262 floor curves: End = Z + 263$\\cdot O_K$; j has degree 131 over $F_2$, so no $\\tau$\n"
                     "horizontal cycles: $\\ell$ = 2 (Frobenius shift), $\\ell$ = 11 within an orbit, $\\ell$ = 29 across orbits",
            ha="center", va="top", fontsize=7.8, color=INK2, linespacing=1.5)
    ax.text(5, 1.55, "steps of degree p = 146505763881528721: kernel points exist only over $F_{q^r}$, r $\\approx 2^{53.4}$",
            ha="center", va="center", fontsize=7.8, color=INK2)
    for x0, lab in [(0.1, "level p (End = Z + p$\\cdot O_K$)\np + 1 $\\approx 2^{57.0}$ curves, none known"),
                    (5.1, "level 263p (End = Z[$\\pi$])\n262(p + 1) $\\approx 2^{65.1}$ curves, none known")]:
        ax.add_patch(FancyBboxPatch((x0, 0.05), 4.8, 0.95, boxstyle="round,pad=0.02,rounding_size=0.08",
                                    fc=SURFACE, ec=MUTED, lw=1, ls=(0, (3, 2))))
        ax.text(x0 + 2.4, 0.52, lab, ha="center", va="center", fontsize=7.8, color=INK2, linespacing=1.4)
    save(fig, "fig_volcano.png")


# ---------- Figure 3: toy ratios ----------
def fig_toy():
    rows = json.load(open(os.path.join(HERE, "toy_a.json")))
    tb = json.load(open(os.path.join(WORK, "toy-b", "summary.json")))
    fl, e0, tr = tb["i_floor_neg"], tb["ii_E0_tau_neg"], tb["iii_transport_then_E0_tau_neg"]
    rb = fl["work_mean"] / e0["work_mean"]
    rb_se = rb * math.hypot(fl["work_se"] / fl["work_mean"], e0["work_se"] / e0["work_mean"])
    tb_r = tr["work_mean"] / e0["work_mean"]
    tb_se = tb_r * math.hypot(tr["work_se"] / tr["work_mean"], e0["work_se"] / e0["work_mean"])
    ns = [r["n"] for r in rows]
    fig, ax = plt.subplots(figsize=(6.6, 3.0))
    xs = [n / 10 for n in range(80, 1900)]
    ax.plot(xs, [math.sqrt(x) for x in xs], color=MUTED, lw=1.2, ls=(0, (4, 3)), zorder=1)
    ax.text(150, math.sqrt(150) - 1.6, r"$\sqrt{n}$ (predicted)", color=INK2, fontsize=8, ha="center")
    ax.axhline(1, color=MUTED, lw=1, ls=(0, (1, 2)), zorder=1)
    ax.errorbar(ns, [r["i_over_ii_merge"][0] for r in rows], yerr=[1.96 * r["i_over_ii_merge"][1] for r in rows],
                fmt="o", color=BLUE, ms=6, mec=SURFACE, mew=1.2, elinewidth=1.2, capsize=0, zorder=3)
    ax.errorbar([179], [rb], yerr=[1.96 * rb_se], fmt="D", color=BLUE, mfc=SURFACE, ms=6, mew=1.5, elinewidth=1.2,
                capsize=0, zorder=3)
    ax.errorbar(ns, [r["iii_over_ii_merge"][0] for r in rows], yerr=[1.96 * r["iii_over_ii_merge"][1] for r in rows],
                fmt="o", color=AQUA, ms=6, mec=SURFACE, mew=1.2, elinewidth=1.2, capsize=0, zorder=3)
    ax.errorbar([179], [tb_r], yerr=[1.96 * tb_se], fmt="D", color=AQUA, mfc=SURFACE, ms=6, mew=1.5,
                elinewidth=1.2, capsize=0, zorder=3)
    ax.text(62, 9.4, "rho on a floor curve ÷ rho on E0", color=INK, fontsize=8.5)
    ax.text(62, 1.6, "(transport to E0, then rho) ÷ rho on E0", color=INK, fontsize=8.5)
    ax.text(179, rb + 1.2, f"n = 179\nindependent code\n{rb:.1f}", color=INK2, fontsize=7.5, ha="center", va="bottom")
    ax.set_xlim(0, 195)
    ax.set_ylim(0, 18.5)
    ax.set_xlabel(r"extension degree n of the toy field $F_{2^n}$")
    ax.set_ylabel("ratio of mean rho iterations")
    ax.plot([], [], "o", color=MUTED, label="toy A (Floyd rho, 5 fields)")
    ax.plot([], [], "D", color=MUTED, mfc=SURFACE, label="toy B (r-adding + distinguished points)")
    ax.legend(loc="upper left", fontsize=8)
    save(fig, "fig_toy.png")
    return {"toy_b_ratio": rb, "toy_b_se": rb_se, "toy_b_transport": tb_r, "toy_b_transport_se": tb_se}


# ---------- Figure 4: IC density z-scores ----------
def fig_ic():
    cls = json.load(open(os.path.join(WORK, "index-calculus", "per_curve.json")))
    null = json.load(open(os.path.join(WORK, "index-calculus", "null_per_curve.json")))
    zc = [v["zscores"][s][k] for v in cls.values() for s in ("canon", "rand1", "rand2", "rand3")
          for k in ("k8", "k10", "k12", "k14", "k16")]
    zn = [v["zscores"][s][k] for v in null.values() for s in ("canon", "rand1", "rand2", "rand3")
          for k in ("k8", "k10", "k12", "k14", "k16")]
    bins = [x / 4 for x in range(-20, 21)]
    fig, ax = plt.subplots(figsize=(6.6, 2.7))
    ax.hist(zn, bins=bins, density=True, histtype="step", color=ORANGE, lw=2, label=f"526 random curves ({len(zn):,} cells)")
    ax.hist(zc, bins=bins, density=True, histtype="step", color=BLUE, lw=2, label=f"263 isogeny-class curves ({len(zc):,} cells)")
    xs = [x / 50 for x in range(-250, 251)]
    ax.plot(xs, [math.exp(-x * x / 2) / math.sqrt(2 * math.pi) for x in xs], color=MUTED, lw=1, ls=(0, (4, 3)),
            label="standard normal")
    e0 = cls["E0"]["zscores"]["canon"]["k16"]
    ax.axvline(e0, color=INK2, lw=1)
    ax.text(e0 + 0.08, 0.5, f"E0, canonical subspace, k = 16: z = {e0:+.2f}", fontsize=7.5, color=INK2)
    ax.set_xlim(-4.2, 4.2)
    ax.set_ylim(0, 0.56)
    ax.set_xlabel("z-score of rational-x density (k = 8 … 16, four subspaces per curve)")
    ax.set_ylabel("density")
    ax.legend(loc="upper left", fontsize=7.5, bbox_to_anchor=(0, 1.02))
    save(fig, "fig_ic.png")
    return {"n_class_cells": len(zc), "n_null_cells": len(zn)}


if __name__ == "__main__":
    fig_levels()
    fig_volcano()
    info = fig_toy()
    info.update(fig_ic())
    json.dump(info, open(os.path.join(HERE, "figure_info.json"), "w"), indent=1)
    print(info)
