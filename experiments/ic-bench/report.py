#!/usr/bin/env python3
"""Paired factor-base comparison table from a benchmark CSV.

    python3 report.py baseline/ci.csv [--baseline-family prefix]

Within each (n, m, l, workload) group the baseline family is the reference arm; every
other family is paired with it on the same curve, workload, solver, limits and
calibration, with the factor base as the declared variable.  speedup = baseline total /
candidate total in the calibrated unit.  Across workloads the table gives the geometric
mean and, from three workloads up, a bootstrap 95% interval over workloads.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import random
from collections import defaultdict
from pathlib import Path


def geomean(xs: list[float]) -> float:
    return math.exp(sum(math.log(x) for x in xs) / len(xs))


def bootstrap(xs: list[float], seed: str) -> list[float] | None:
    if len(xs) < 3:
        return None
    rng = random.Random(int.from_bytes(hashlib.sha256(seed.encode()).digest()[:8], "big"))
    draws = sorted(geomean(rng.choices(xs, k=len(xs))) for _ in range(4000))
    return [draws[99], draws[3899]]


def table(rows: list[dict], baseline_family: str) -> list[str]:
    groups = defaultdict(dict)
    for r in rows:
        groups[(int(r["n"]), int(r["m"]), int(r["l"]), r["mode"], r["workload_id"])][r["family"]] = r
    lines = ["| n | m | l | workload | arm | candidate | verified | fb | columns | queries | total ops | "
             "ratio to rho | ratio to floor | S (ec_add eq.) | speedup vs baseline |",
             "|--:|--:|--:|---|---|---|---|--:|--:|--:|--:|--:|--:|--:|--:|"]
    speedups = defaultdict(list)
    for key in sorted(groups):
        arms = groups[key]
        base = arms.get(baseline_family)
        for fam in sorted(arms, key=lambda f: (f != baseline_family, f)):
            r = arms[fam]
            total = int(r["total_operations"]) if r["total_operations"] else None
            sp = None
            if base is not None and total and base["total_operations"]:
                sp = int(base["total_operations"]) / total
                if fam != baseline_family:
                    speedups[(key[:4], fam)].append(sp)
            lines.append(
                f"| {key[0]} | {key[1]} | {key[2]} | {key[4]} | {fam}{' (baseline)' if fam == baseline_family else ''} "
                f"| `{r['candidate_id']}` | {r['verified']} | {r['fb_points']} | {r['effective_columns']} "
                f"| {r['ordinary_queries']} | {total if total is not None else 'unknown'} | {r['ratio_to_rho'] or '—'} "
                f"| {r['ratio_to_floor'] or '—'} | {r['S_ec_add'] or '—'} | {f'{sp:.3f}' if sp else '—'} |"
            )
    lines += ["", "| n | m | l | arm vs baseline | workloads | geometric-mean speedup | 95% bootstrap over workloads |",
              "|--:|--:|--:|---|--:|--:|---|"]
    for (cell, fam), xs in sorted(speedups.items()):
        ci = bootstrap(xs, f"{cell}|{fam}")
        lines.append(f"| {cell[0]} | {cell[1]} | {cell[2]} | {fam} vs {baseline_family} | {len(xs)} | {geomean(xs):.3f} "
                     f"| {f'[{ci[0]:.3f}, {ci[1]:.3f}]' if ci else 'fewer than 3 workloads'} |")
    return lines


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", type=Path)
    ap.add_argument("--baseline-family", default="prefix")
    args = ap.parse_args()
    with args.csv.open(newline="") as fh:
        rows = list(csv.DictReader(fh))
    print("\n".join(table(rows, args.baseline_family)))


if __name__ == "__main__":
    main()
