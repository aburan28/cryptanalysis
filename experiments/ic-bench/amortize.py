#!/usr/bin/env python3
"""Report exact multi-target prefix economics from ic-bench JSONL receipts.

One run with K targets pays the relation database once and records every target's
marginal operation cost. This tool reconstructs exact prefix costs at
1,2,4,...,K and compares them with independent per-target rho and the fairer
Kuhn-Struik distinguished-point batch-rho expectation, including the same
sign/Frobenius quotient used by the binary IC factor-base columns.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def fmt(x, digits=4):
    if x is None:
        return "—"
    if isinstance(x, int):
        return f"{x:,}"
    return f"{x:.{digits}g}"


def validate_receipt(rec: dict, require_power: int | None = None) -> None:
    if rec.get("status") != "complete" or rec.get("verified_scalar") is not True:
        raise ValueError(f"{rec.get('run_id')}: amortization requires a complete verified DLP")
    warm = rec.get("warm") or {}
    per = warm.get("per_target_operations")
    prefixes = warm.get("prefixes")
    if not isinstance(per, list) or not per:
        raise ValueError(f"{rec.get('run_id')}: missing per-target operation ledger")
    if not isinstance(prefixes, list) or not prefixes:
        raise ValueError(f"{rec.get('run_id')}: missing prefix accounting")
    if warm["target_operations"] != sum(per):
        raise ValueError(f"{rec.get('run_id')}: target operation total does not match per-target ledger")
    if warm["shared_operations"] + warm["target_operations"] != rec["total_operations"]:
        raise ValueError(f"{rec.get('run_id')}: shared + marginal does not equal total")
    if require_power is not None and len(per) < 1 << require_power:
        raise ValueError(
            f"{rec.get('run_id')}: has {len(per)} targets, need at least 2^{require_power}"
        )


def markdown(rec: dict) -> list[str]:
    warm = rec["warm"]
    c = rec["cell"]
    lines = [
        f"## {rec['bench_cell']}",
        "",
        f"Candidate: {rec['candidate_id']}  ",
        f"Workload series: {rec['workload_series_id']}  ",
        f"n={c['n']}, m={c['m']}, l={c['l']}, factor base={c['family']}, "
        f"targets={warm['k']:,}.",
        "",
        f"Shared IC work: **{warm['shared_operations']:,}** rps. "
        f"Mean measured target work: **{fmt(warm['mean_target_operations'])}** rps.",
        "",
        "| targets | IC total | IC/target | marginal mean | shared % | IC / independent rho | IC / batch rho | IC / folded batch rho |",
        "|--:|--:|--:|--:|--:|--:|--:|--:|",
    ]
    for p in warm["prefixes"]:
        lines.append(
            f"| {p['targets']:,} | {fmt(p['ic_operations'])} | "
            f"{fmt(p['amortized_operations_per_target'])} | {fmt(p['mean_target_operations'])} | "
            f"{fmt(100 * p['shared_fraction'], 3) if p['shared_fraction'] is not None else '—'} | "
            f"{fmt(p['ic_over_independent_rho'])} | {fmt(p['ic_over_batch_rho'])} | "
            f"{fmt(p['ic_over_folded_batch_rho'])} |"
        )
    lines += [
        "",
        "Ratios are IC/rho, so below 1 means the IC run used fewer calibrated operations. "
        "The independent-rho column solves every target separately. The batch-rho columns "
        "use the analytic Kuhn-Struik distinguished-point expectation; the folded column "
        "uses r/(2n) sign/Frobenius classes and is the stricter comparison.",
        "",
        f"Observed-mean break-even against **independent** per-target rho: "
        f"{fmt(warm.get('break_even_targets_vs_independent_rho'))} targets. "
        "This is a projection from the measured marginal mean, not a batch-rho crossover.",
        "",
    ]
    return lines


def json_summary(rec: dict) -> dict:
    return {
        "candidate_id": rec["candidate_id"],
        "bench_cell": rec["bench_cell"],
        "workload_series_id": rec["workload_series_id"],
        "n": rec["cell"]["n"],
        "m": rec["cell"]["m"],
        "l": rec["cell"]["l"],
        "family": rec["cell"]["family"],
        "targets": rec["warm"]["k"],
        "shared_operations": rec["warm"]["shared_operations"],
        "mean_target_operations": rec["warm"]["mean_target_operations"],
        "break_even_targets_vs_independent_rho":
            rec["warm"].get("break_even_targets_vs_independent_rho"),
        "prefixes": rec["warm"]["prefixes"],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("jsonl", type=Path)
    ap.add_argument("--require-max-power", type=int, default=None,
                    help="fail unless every receipt contains at least 2^P targets")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    receipts = [json.loads(line) for line in args.jsonl.read_text().splitlines() if line.strip()]
    if not receipts:
        raise SystemExit("no receipts")
    for rec in receipts:
        validate_receipt(rec, args.require_max_power)
    if args.json:
        print(json.dumps([json_summary(rec) for rec in receipts], indent=2, sort_keys=True))
    else:
        lines = ["# IC multi-target amortization", ""]
        for rec in receipts:
            lines += markdown(rec)
        print("\n".join(lines))


if __name__ == "__main__":
    main()
