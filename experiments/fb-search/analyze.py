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

from search import load_jsonl, spearman

REF = "prefix"


def load(paths):
    out = load_jsonl(paths)
    # one record per (candidate, rank-process runs); a repeated scan keeps the last
    uniq = {}
    for r in out:
        uniq[(r["candidate_id"], r["cell"]["targets"])] = r
    return list(uniq.values())


def cost(r):
    return r["predicted"].get("total_operations_mean")


def fmt(x, p=3):
    return "-" if x is None else f"{x:.{p}g}"


def measured(receipts_path: str, selection_path: str, baseline: str) -> None:
    """One row per candidate: measured cold totals on the shared workloads, paired with the baseline
    candidate's runs on the same workloads (geometric mean of the per-workload ratio, with its range)."""
    with open(receipts_path) as fh:
        recs = [json.loads(line) for line in fh if line.strip()]
    picks = {p["candidate_id"]: p for p in json.loads(open(selection_path).read())["picks"]}
    by_cand = defaultdict(dict)
    for r in recs:
        by_cand[r["candidate_id"]][r["workload_id"]] = r
    base_id = next(cid for cid, p in picks.items() if f"n{p['cell']['n']}l{p['cell']['l']}-{p['cell']['family']}"
                   == baseline)
    base = by_cand[base_id]
    print(f"## Measured end-to-end cost (baseline `{base_id}`, {baseline})\n")
    print("Every row is a complete IC pipeline with every target's log verified by scalar replay. `total` is the "
          "mean cold total over the workloads (3 targets each, rps); `speedup` is baseline_total / candidate_total "
          "per workload, geometric mean [min, max] over the paired workloads. `x rho` and `x floor` are the "
          "boundary ratios fixed in the workload records; `S` is total / sqrt(r) in rps.\n")
    print("| candidate | l | family | seed | role | verified | queries (mean) | predicted total | measured total "
          "| speedup vs baseline | x rho | x floor | S |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    rows = []
    for cid, runs in by_cand.items():
        p = picks.get(cid)
        if p is None:
            continue
        common = sorted(set(runs) & set(base))
        sp = [base[w]["total_operations"] / runs[w]["total_operations"] for w in common
              if runs[w]["total_operations"] and base[w]["total_operations"]]
        rows.append((p["cell"]["l"], p["cell"]["family"] != REF, p["cell"]["family"], p["rank"], cid, p, runs, sp))
    for l, _, fam, _, cid, p, runs, sp in sorted(rows):
        rs = list(runs.values())
        ok = sum(1 for r in rs if r["status"] == "complete" and r["verified_scalar"])
        tot = statistics.fmean(r["total_operations"] for r in rs)
        print(f"| `{cid}` | {l} | {fam} | {p['cell']['seed']} | {p['role']} | {ok}/{len(rs)} "
              f"| {statistics.fmean(r['counts']['ordinary_queries'] + r['counts']['descent_attempts'] for r in rs):.0f} "
              f"| {p['predicted']['total_operations_mean']:.3e} | {tot:.3e} "
              f"| {statistics.geometric_mean(sp):.2f} [{min(sp):.2f}, {max(sp):.2f}] "
              f"| {statistics.fmean(r['ratio_to_rho'] for r in rs):.4g} "
              f"| {statistics.fmean(r['ratio_to_floor'] for r in rs):.4g} "
              f"| {statistics.fmean(r['S_rps'] for r in rs):.4g} |")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scans", nargs="*")
    ap.add_argument("--receipts", default="", help="ic-bench receipts to tabulate against --selection")
    ap.add_argument("--selection", default="selected.json")
    ap.add_argument("--baseline", default="n19l5-prefix")
    args = ap.parse_args()
    if args.receipts:
        measured(args.receipts, args.selection, args.baseline)
        return
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
