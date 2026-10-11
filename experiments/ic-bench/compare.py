#!/usr/bin/env python3
"""Check a benchmark CSV against the committed baseline.

    python3 compare.py baseline/ci.csv out/ci.csv [--tolerance 0.05] [--summary out/summary.md]

Rows pair on (bench_cell, workload_id).  The check fails when

  * a new run is not a complete verified DLP (status != complete or verified != True);
  * a baseline cell is missing from the new CSV, or its workload changed;
  * the candidate ID is unchanged but a deterministic column differs (same code and inputs
    must reproduce every counter: anything else is nondeterminism);
  * the total operations of a cell grew by more than --tolerance (a regression), or the
    geometric mean over all cells did.

With a changed candidate ID (code or factor base changed) every counter may move; the
table reports the ratio, flags improvements beyond the tolerance, and asks for a new
baseline (`bench.py run --suite <suite> --record`).  Wall time is reported, never gated.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

DETERMINISTIC_PREFIXES = ("ops_", "count_")
DETERMINISTIC = ("status", "verified", "targets_verified", "fb_points", "effective_columns", "achievable_rank",
                 "final_rank", "ordinary_queries", "pdp_verified", "pdp_proved_unsat", "pdp_budget",
                 "pdp_lift_rejected", "verified_relations", "novel_rows", "descent_attempts", "total_operations",
                 "rho_operations", "calibration_id")


def read(path: Path) -> list[dict]:
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


def deterministic_fields(row: dict) -> list[str]:
    return [k for k in row if k.startswith(DETERMINISTIC_PREFIXES) or k in DETERMINISTIC]


def fmt_ratio(x: float | None) -> str:
    return "—" if x is None else f"{x:.4f}"


def compare(base: list[dict], new: list[dict], tolerance: float) -> tuple[list[str], list[str], list[str]]:
    """(failures, notes, markdown lines)."""
    failures, notes = [], []
    bmap = {(r["bench_cell"], r["workload_id"]): r for r in base}
    nmap = {(r["bench_cell"], r["workload_id"]): r for r in new}
    ncells = {r["bench_cell"]: r for r in new}
    lines = ["| cell | status | candidate | total ops (base → new) | ratio | queries (base → new) | wall s (new) | verdict |",
             "|---|---|---|--:|--:|--:|--:|---|"]
    ratios = []
    for r in new:
        if r["status"] != "complete" or r["verified"] != "True":
            failures.append(f"{r['bench_cell']}: status {r['status']}, verified {r['verified']} (run {r['run_id']})")
    for key, b in sorted(bmap.items()):
        cell = key[0]
        n = nmap.get(key)
        if n is None:
            if cell in ncells:
                failures.append(f"{cell}: workload changed ({key[1]} -> {ncells[cell]['workload_id']}); re-record the baseline")
            else:
                failures.append(f"{cell}: missing from the new run")
            continue
        same = b["candidate_id"] == n["candidate_id"]
        bt = int(b["total_operations"]) if b["total_operations"] else None
        nt = int(n["total_operations"]) if n["total_operations"] else None
        ratio = nt / bt if bt and nt else None
        verdict = "same"
        if same:
            diffs = [f for f in deterministic_fields(b) if b.get(f) != n.get(f)]
            if diffs:
                failures.append(f"{cell}: same candidate {n['candidate_id']} but {', '.join(diffs[:6])} differ (nondeterminism)")
                verdict = "NONDETERMINISTIC"
        if ratio is not None:
            ratios.append(ratio)
            if ratio > 1 + tolerance:
                failures.append(f"{cell}: total operations {bt} -> {nt} (x{ratio:.4f}) exceeds tolerance {tolerance}")
                verdict = "REGRESSION"
            elif ratio < 1 - tolerance:
                notes.append(f"{cell}: improvement x{ratio:.4f}")
                verdict = "improvement"
            elif not same:
                verdict = "changed, within tolerance"
        if not same and verdict != "REGRESSION":
            notes.append(f"{cell}: candidate changed {b['candidate_id']} -> {n['candidate_id']}")
        lines.append(f"| {cell} | {n['status']} | {'same' if same else 'changed'} | {bt} → {nt} | {fmt_ratio(ratio)} "
                     f"| {b['ordinary_queries']} → {n['ordinary_queries']} | {int(n['wall_ns']) / 1e9:.1f} | {verdict} |")
    for key in sorted(set(nmap) - set(bmap)):
        notes.append(f"{key[0]}: new cell (workload {key[1]}), not in the baseline")
    if ratios:
        gm = math.exp(sum(math.log(x) for x in ratios) / len(ratios))
        lines.append(f"\nGeometric mean total-operations ratio over {len(ratios)} cells: **{gm:.4f}**")
        if gm > 1 + tolerance:
            failures.append(f"geometric-mean total operations x{gm:.4f} exceeds tolerance {tolerance}")
    return failures, notes, lines


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("baseline", type=Path)
    ap.add_argument("new", type=Path)
    ap.add_argument("--tolerance", type=float, default=0.05, help="relative growth in total operations that fails")
    ap.add_argument("--summary", type=Path, help="write the markdown report here too (e.g. $GITHUB_STEP_SUMMARY)")
    args = ap.parse_args()
    failures, notes, lines = compare(read(args.baseline), read(args.new), args.tolerance)
    text = ["## IC benchmark vs baseline", "", f"Baseline `{args.baseline}`, tolerance {args.tolerance:.0%}.", "", *lines, ""]
    if notes:
        text += ["### Notes", *[f"- {n}" for n in notes], ""]
    text += ["### Result", "**FAIL**" if failures else "**PASS**", *[f"- {f}" for f in failures], ""]
    out = "\n".join(text)
    print(out)
    if args.summary:
        with args.summary.open("a") as fh:
            fh.write(out + "\n")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
