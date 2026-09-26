#!/usr/bin/env python3
"""Summarize fb-search scans: the seed distribution of predicted end-to-end cost per (n, l, family),
family ratios, the gain from picking the best of K seeds, and which structural features explain
the prediction.  Every number here is a prediction (see search.py); measured runs are joined by
`search.py check`.

    python3 analyze.py results/scan-n19m2.jsonl [more.jsonl] > results/summary.md
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict

from search import spearman

REF = "prefix"


def load(paths):
    out = []
    for p in paths:
        with open(p) as fh:
            out += [json.loads(line) for line in fh if line.strip()]
    # one record per (candidate, rank-process runs); a repeated scan keeps the last
    uniq = {}
    for r in out:
        uniq[(r["candidate_id"], r["cell"]["targets"])] = r
    return list(uniq.values())


def cost(r):
    return r["predicted"].get("total_operations_mean")


def fmt(x, p=3):
    return "-" if x is None else f"{x:.{p}g}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scans", nargs="+")
    ap.add_argument("--best-of", type=int, nargs="+", default=[1, 8, 48])
    args = ap.parse_args()
    recs = [r for r in load(args.scans) if cost(r) is not None]
    groups = defaultdict(list)
    for r in recs:
        c = r["cell"]
        groups[(c["n"], c["l"], c["family"])].append(r)

    print("## Predicted cold cost by factor base (3 targets, m = 2)\n")
    print("All costs are predictions in rps: exact rank-process queries times the probed price per query, "
          "plus probed fixed costs. `ops` is the median over seeds, with [min, max]; `vs prefix` is the "
          "median over seeds divided by the prefix base's prediction.\n")
    print("| n | l | family | seeds | B median | columns | p_dec median | E[queries] median | ops median [min, max] "
          "| vs prefix | best seed | best vs median | x rho |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for (n, l, fam), rs in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2] != REF, kv[0][2])):
        ops = sorted(cost(r) for r in rs)
        med = statistics.median(ops)
        ref = groups.get((n, l, REF))
        ref_ops = statistics.median(cost(r) for r in ref) if ref else None
        best = min(rs, key=cost)
        print(f"| {n} | {l} | {fam} | {len(rs)} | {statistics.median(r['stage']['fb_points'] for r in rs):g} "
              f"| {statistics.median(r['stage']['effective_columns'] for r in rs):g} "
              f"| {statistics.median(r['stage']['p_decomposable'] for r in rs):.4g} "
              f"| {statistics.median(r['predicted']['queries_mean'] for r in rs):.4g} "
              f"| {med:.3e} [{ops[0]:.2e}, {ops[-1]:.2e}] "
              f"| {fmt(med / ref_ops if ref_ops else None)} | s{best['cell']['seed']} | {ops[0] / med:.3f} "
              f"| {statistics.median(r['predicted']['ratio_to_rho'] for r in rs):.4g} |")

    print("\n## Best dimension per n\n")
    print("| n | family | best l (median seed) | median ops | best l (best seed) | best ops | best candidate |")
    print("|---|---|---|---|---|---|---|")
    by_nf = defaultdict(list)
    for (n, l, fam), rs in groups.items():
        by_nf[(n, fam)].append((l, rs))
    for (n, fam), items in sorted(by_nf.items()):
        med_l, med_ops = min(((l, statistics.median(cost(r) for r in rs)) for l, rs in items), key=lambda t: t[1])
        best = min((r for _, rs in items for r in rs), key=cost)
        print(f"| {n} | {fam} | {med_l} | {med_ops:.3e} | {best['cell']['l']} | {cost(best):.3e} "
              f"| `{best['candidate_id']}` (s{best['cell']['seed']}) |")

    print("\n## What explains the prediction within a cell\n")
    print("Spearman rank correlation, over the seeds of one (n, l, family), between predicted cost and "
          "each feature (negative = larger feature, cheaper).\n")
    feats = {
        "fb_points": lambda r: r["stage"]["fb_points"],
        "p_dec": lambda r: r["stage"]["p_decomposable"],
        "columns": lambda r: r["stage"]["effective_columns"],
        "rank deficit": lambda r: r["stage"]["effective_columns"] - (r["stage"]["achievable_rank"] or 0),
        "column-rate CV": lambda r: r["stage"]["column_rate_cv"],
        "min column rate": lambda r: r["stage"]["min_column_rate"],
        "dim V^(2)": lambda r: r["stage"]["product_profile"][1],
    }
    print("| n | l | family | " + " | ".join(feats) + " |")
    print("|---|---|---|" + "---|" * len(feats))
    for (n, l, fam), rs in sorted(groups.items()):
        if len(rs) < 8:
            continue
        y = [cost(r) for r in rs]
        cells = []
        for f in feats.values():
            x = [f(r) for r in rs]
            rho = spearman(x, y) if len(set(x)) > 1 else None
            cells.append("-" if rho is None or math.isnan(rho) else f"{rho:+.2f}")
        print(f"| {n} | {l} | {fam} | " + " | ".join(cells) + " |")


if __name__ == "__main__":
    main()
