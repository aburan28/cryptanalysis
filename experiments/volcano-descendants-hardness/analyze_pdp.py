"""Summarise pdp_*.csv: E0 vs descendants vs random-b controls, per (m, l).

    python3 analyze_pdp.py pdp_m3.csv pdp_m4.csv
"""

from __future__ import annotations

import csv
import sys
from collections import Counter, defaultdict
from statistics import median

from scipy.stats import mannwhitneyu

METRICS = ["cpu", "monomials", "max_rows", "pairs_reduced", "zero_reductions"]


def load(paths):
    rows = []
    for p in paths:
        with open(p) as fh:
            rows += list(csv.DictReader(fh))
    return rows


def num(r, k):
    try:
        return float(r[k])
    except (TypeError, ValueError):
        return None


def groups_of(rs):
    g = defaultdict(list)
    for r in rs:
        g[r["group"]].append(r)
        if r["group"] == "descendant":
            g[f"orbit{r['orbit']}"].append(r)
    return g


def main(paths):
    rows = load(paths)
    by_ml = defaultdict(list)
    for r in rows:
        by_ml[(int(r["m"]), int(r["l"]), r.get("basis") or "std")].append(r)
    for (m, l, basis), rs in sorted(by_ml.items()):
        g = groups_of(rs)
        print(f"\n### m = {m}, l = {l}, factor base {basis}\n")
        print("| group | instances | solved+verified | median cpu (s) | median max matrix rows "
              "| median ANF monomials | median pairs | max degree | first degree fall |")
        print("|---|--:|--:|--:|--:|--:|--:|---|---|")
        for name in ("E0", "descendant", "orbit0", "orbit1", "random"):
            xs = g.get(name, [])
            if not xs:
                continue
            ok = sum(r["status"] == "solved" and r["verified"] == "True" for r in xs)
            med = lambda k: median(v for v in (num(r, k) for r in xs) if v is not None)
            hist = lambda k: ", ".join(f"{d}:{c}" for d, c in sorted(Counter(r[k] for r in xs).items()))
            print(f"| {name} | {len(xs)} | {ok} | {med('cpu'):.3g} | {med('max_rows'):.0f} "
                  f"| {med('monomials'):.0f} | {med('pairs_reduced'):.0f} | {hist('max_deg')} | {hist('first_zero_deg')} |")
        print("\nMann-Whitney U two-sided p-values:\n")
        print("| comparison | " + " | ".join(METRICS) + " |")
        print("|---|" + "--:|" * len(METRICS))
        for a, b in (("E0", "descendant"), ("E0", "random"), ("descendant", "random"), ("orbit0", "orbit1")):
            if a not in g or b not in g:
                continue
            ps = []
            for k in METRICS:
                xa = [v for v in (num(r, k) for r in g[a]) if v is not None]
                xb = [v for v in (num(r, k) for r in g[b]) if v is not None]
                ps.append(f"{mannwhitneyu(xa, xb).pvalue:.3g}")
            print(f"| {a} vs {b} | " + " | ".join(ps) + " |")


if __name__ == "__main__":
    main(sys.argv[1:])
