"""Editable source for the follow-up figures.  Reads only results/*.json.

  decision_map.svg/.png     labelled diagram: the eight shipped items, their
                            status (checked / derived / measured) and the
                            common claim boundary
  s4_bench.svg/.png         wall time per regime for the four S4 evaluators
                            (median of 7 rotated trials; min as error bar)
  sss_benchmark.svg/.png    per-fixture medians of three repetitions for
                            SSS, pSIQS and SymPy SIQS (min/max as bars)
The NFS window and pinpointing-constant charts are drawn by their modules.
"""

from __future__ import annotations

import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "..", "results")

CHECKED, DERIVED, MEASURED, BOUNDARY = "#2a78d6", "#7a5bd6", "#2b9d6f", "#b23a3a"


def load(name):
    with open(os.path.join(RES, name)) as fh:
        return json.load(fh)


def decision_map():
    sr = load("selected_resieve.json")
    nfs = load("nfs_density_window.json")
    rr = load("resultant_ranks.json")
    sss = load("sss/summary.json")["summary"]
    s4 = load("s4_two_product.json")
    pin = load("pinpointing.json")
    win = nfs["window_at_gamma_max"]
    idx = next(r for r in load("s4_bench.json")["regimes"] if r["label"] == "indexed_1024")
    ev = {e["name"]: e["total_ms_median"] for e in idx["evaluators"]}
    r_raw, r_monic = ev["raw_fused_7M1S"] / ev["two_product_2M"], ev["monic_fused_3M1S"] / ev["two_product_2M"]
    items = [
        ("1  Selected-resieve correspondence", "lemma", CHECKED,
         f"selected sieve scores = selected entries of XY, inner dim D = sum p<=y;\nrank K = 1 + sum(p-1): checked on 5 prime sets, 40 identity trials;\n"
         f"D <= N^(1/18) caps y at 5 (N=2^64), 29 (2^128), 461 (2^256)"),
        ("2  Batch-smoothness screen", "screen", MEASURED,
         "product/remainder-tree smooth parts, 900 values checked vs trial division;\n~25-37 ns per bit of the batch, flat in y and |W|;\ndominates AVW by D^0.437 inside the preprocessing range (derived)"),
        ("3  NFS density window", "no-go", DERIVED,
         f"0.437g < theta < 0.563g; g <= 1/18 gives {win['theta_low']:.5f} < theta < {win['theta_high']:.5f};\nGNFS theta=1/4 and SNFS theta=1/2 fall outside; AVW S^1.9965 vs batch S^1.75 / S^1.5"),
        ("4  Dyadic heavy-cell reporter", "construction", CHECKED,
         "exact for nonnegative scores; queries <= 1 + 4(M/tau) log2 N on 25 random + 16 sieve instances;\nNFS screen: M/tau = N^(2-o(1)), never beats a plain scan"),
        ("5  SSS five-fixture positive control", "benchmark", MEASURED,
         f"15/15 verified; SSS {sss['sss']['five_fixture_total_of_medians_s']:.3f} s vs pSIQS {sss['psiqs']['five_fixture_total_of_medians_s']:.3f} s (GM {sss['psiqs']['geometric_mean_ratio_to_sss']:.2f}x)\n"
         f"vs SymPy SIQS {sss['ssiqs']['five_fixture_total_of_medians_s']:.3f} s (GM {sss['ssiqs']['geometric_mean_ratio_to_sss']:.2f}x); 30-digit N, shared VM"),
        ("6  Joux advanced pinpointing", "literature", CHECKED,
         f"toy Kummer join q=311, n=5: {pin['toy_kummer_pinpointing']['relations_verified_in_F_q^n']} relations verified;\n"
         "L(1/3) constants: range [3^-2/3, (2/3)^2/3), 1.4422 -> 0.9615 at alpha_low (paper misprint 0.96 vs (2/3)^2/3)"),
        ("7  Growing-resultant ranks + transfers", "obstruction", CHECKED,
         "generic rank C(r+s,r) checked to (4,4)=70; Semaev S4/S5 specialised ranks 6, 15 = generic ceilings;\n"
         "N > (|H|/4)^(18/37) obstruction (derived); trace-zero kills base-field targets; cover needs r not | d"),
        ("8  Two-product S4 evaluator", "evaluator", MEASURED,
         f"R = (F-C)(UL+UR) + (E-B)(VR-VL), 2M per pair; exhaustive over F_p p<=11; Gram rank {s4['optimality']['gram_rank_in_8_features']} => 2 products optimal;\n"
         f"native 2^61-1: {r_raw:.2f}x raw / {r_monic:.2f}x monic fused in the indexed regime; loses when endpoints are not reused"),
    ]
    fig, ax = plt.subplots(figsize=(13.5, 10.2))
    ax.set_xlim(0, 13.5)
    ax.set_ylim(0, 10.2)
    ax.axis("off")
    ax.text(0.3, 9.85, "Speedup-search follow-up (2026-10-06): what ships, with status", fontsize=15, fontweight="bold", va="center")
    ax.text(0.3, 9.5, "Premise: AVW selected thin products, D <= N^(1/18), preprocessing N^2/D^0.063, query D^0.437, separation rank > n^0.437", fontsize=9.5, color="#444", va="center")
    y = 8.78
    for title, kind, col, body in items:
        h = 0.95
        ax.add_patch(FancyBboxPatch((0.3, y - h), 12.9, h - 0.08, boxstyle="round,pad=0.02,rounding_size=0.08", fc="white", ec=col, lw=1.6))
        ax.add_patch(FancyBboxPatch((0.3, y - h), 0.18, h - 0.08, boxstyle="square,pad=0", fc=col, ec=col))
        ax.text(0.62, y - 0.22, title, fontsize=10.5, fontweight="bold", va="center")
        ax.text(12.95, y - 0.22, kind, fontsize=8.5, color=col, va="center", ha="right", style="italic")
        ax.text(0.62, y - 0.62, body, fontsize=7.9, va="center", color="#222", linespacing=1.35)
        y -= h + 0.02
    ax.add_patch(FancyBboxPatch((0.3, 0.25), 12.9, 0.62, boxstyle="round,pad=0.02,rounding_size=0.08", fc="#fbeeee", ec=BOUNDARY, lw=1.6))
    ax.text(0.62, 0.56, "Claim boundary (all items): no faster NFS, FFS, ECDLP, pairing-target attack or complete index-calculus algorithm is claimed from AVW.\n"
            "Items 2, 5, 8 are stage diagnostics on a shared VM (candidate_id null); items 3, 7 are derived from the premise; items 1, 4, 6 are checked algebra.",
            fontsize=8.6, va="center", color="#5a1c1c", linespacing=1.4)
    for i, (lab, col) in enumerate([("checked algebra", CHECKED), ("derived from premise", DERIVED), ("measured (stage diagnostic)", MEASURED)]):
        ax.add_patch(FancyBboxPatch((0.3 + i * 2.1, 9.07), 0.16, 0.16, boxstyle="square,pad=0", fc=col, ec=col))
        ax.text(0.52 + i * 2.1, 9.15, lab, fontsize=7.8, va="center")
    for ext in ("svg", "png"):
        fig.savefig(os.path.join(HERE, f"decision_map.{ext}"), dpi=150, bbox_inches="tight")
    plt.close(fig)


def s4_bench():
    d = load("s4_bench.json")
    regimes = d["regimes"]
    names = [e["name"] for e in regimes[0]["evaluators"]]
    labels = {"raw_fused_7M1S": "raw fused 7M+1S (no endpoint work)", "monic_fused_3M1S": "monic fused 3M+1S", "rank_six_dot_6M": "rank-six dot 6M", "two_product_2M": "two-product 2M"}
    cols = ["#999999", "#2a78d6", "#7a5bd6", "#2b9d6f"]
    fig, ax = plt.subplots(figsize=(10.5, 4.6))
    w = 0.2
    for k, n in enumerate(names):
        med = [next(e for e in r["evaluators"] if e["name"] == n)["total_ms_median"] for r in regimes]
        mn = [next(e for e in r["evaluators"] if e["name"] == n)["total_ms_min"] for r in regimes]
        xs = [i + (k - 1.5) * w for i in range(len(regimes))]
        ax.bar(xs, med, w, color=cols[k], label=labels[n], yerr=[[m - lo for m, lo in zip(med, mn)], [0] * len(med)], capsize=2, error_kw={"lw": 0.8})
    ax.set_xticks(range(len(regimes)))
    import math as _m
    ax.set_xticklabels([f"{r['label']}\n|L|=2^{int(_m.log2(r['nL']))}, |R|=2^{int(_m.log2(r['nR']))}" for r in regimes], fontsize=8)
    ax.set_ylabel("ms for 2^20 pairs (precompute + pair loop), median of 7")
    ax.set_title(f"Two-product S4 evaluator, p = 2^61-1, {d['host']['cpu']} (shared VM, exploratory wall time)", fontsize=10)
    ax.legend(fontsize=8, frameon=False)
    ax.grid(axis="y", alpha=0.3)
    ax.text(0.01, -0.3, "Bars: median total; whisker down to the minimum trial. All four evaluators agree on every pair in every regime (checksums). Stage diagnostic; candidate_id null.", transform=ax.transAxes, fontsize=7.5, color="#444")
    for ext in ("svg", "png"):
        fig.savefig(os.path.join(HERE, f"s4_bench.{ext}"), dpi=150, bbox_inches="tight")
    plt.close(fig)


def sss_benchmark():
    s = load("sss/summary.json")
    summ = s["summary"]
    fix = s["fixtures"]
    algs = [("sss", "SSS (Hittmeir)", "#2b9d6f"), ("psiqs", "bundled pSIQS", "#2a78d6"), ("ssiqs", "SymPy SIQS", "#7a5bd6")]
    fig, ax = plt.subplots(figsize=(9.0, 4.4))
    w = 0.26
    for k, (key, lab, col) in enumerate(algs):
        med = summ[key]["per_fixture_median_s"]
        lo = summ[key]["per_fixture_min_s"]
        hi = summ[key]["per_fixture_max_s"]
        xs = [i + (k - 1) * w for i in range(len(fix))]
        ax.bar(xs, med, w, color=col, label=f"{lab}: total {summ[key]['five_fixture_total_of_medians_s']:.3f} s, GM ratio {summ[key]['geometric_mean_ratio_to_sss']:.2f}x", yerr=[[m - a for m, a in zip(med, lo)], [b - m for m, b in zip(med, hi)]], capsize=2, error_kw={"lw": 0.8})
    ax.set_xticks(range(len(fix)))
    ax.set_xticklabels([f"fixture {i}\n{str(n)[:8]}…" for i, n in enumerate(fix)], fontsize=8)
    ax.set_ylabel("seconds per factorisation (median of 3 fresh processes)")
    ax.set_yscale("log")
    ax.set_title("SSS positive control: five 30-digit semiprimes, verified factors in 15/15 runs per algorithm", fontsize=10)
    ax.legend(fontsize=8, frameon=False)
    ax.grid(axis="y", alpha=0.3, which="both")
    ax.text(0.01, -0.28, "Whiskers: min/max of 3 repetitions. Upstream rev 8dbaf6d…; python 3.12.3, gmpy2 2.3.2, sympy 1.14.0; shared 4-vCPU VM, no isolation receipt.", transform=ax.transAxes, fontsize=7.5, color="#444")
    for ext in ("svg", "png"):
        fig.savefig(os.path.join(HERE, f"sss_benchmark.{ext}"), dpi=150, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    decision_map()
    s4_bench()
    sss_benchmark()
    print("wrote decision_map, s4_bench, sss_benchmark (svg+png)")
