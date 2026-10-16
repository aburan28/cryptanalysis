#!/usr/bin/env python3
"""Compare normalized binary- and prime-field IC receipts without mixing units or rho conventions.

    python3 cross_report.py results/a.jsonl prime/prime.jsonl [--variant generous|with_setup]

Absolute operation totals remain in each regime's native unit (binary: calibrated
rps; prime: counted affine group operations). The ratio columns are dimensionless,
and every one of them is recomputed here from the receipt's subgroup order, target
count and automorphisms under ONE named rho variant of tools/rho_reference.py, so a
binary and a prime ratio in the same table always share a rho convention. (The
receipts' own stored ratios do not: bench.py stores `generous`, prime_bridge.py
stores `with_setup`.)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import rho_reference  # noqa: E402


def load(paths):
    out = []
    for p in paths:
        out += [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
    return out


def regime(r):
    return "prime" if r["source_curve_ref"].startswith("EC1P") else "binary"


def fmt(x):
    return "—" if x is None else f"{x:.4g}" if isinstance(x, float) else f"{x:,}"


def automorphisms(rec) -> int:
    ref = rec.get("rho_reference") or {}
    if "automorphisms" in ref:
        return int(ref["automorphisms"])
    if regime(rec) == "prime":
        return int(rec["native_prime_report"]["factor_base"]["automorphism_order"])
    return 2 * int(rec["cell"]["n"])  # Koblitz over F_2^n: negation and the n Frobenius powers


def unit_per_group_operation(rec) -> int:
    """Price of one group operation in the receipt's unit (prime: 1; binary: the rps ec_add weight)."""
    ref = rec.get("rho_reference") or {}
    if "unit_per_group_operation" in ref:
        return ref["unit_per_group_operation"]
    if regime(rec) == "prime":
        return 1
    # Older binary receipts: rho_operations = round(sqrt(pi r / 2)) * w_ec_add exactly.
    group_ops = round(rho_reference.single_target_group_operations(int(rec["subgroup_order"])))
    w, rem = divmod(int(rec["rho_operations"]), group_ops)
    if rem:
        raise ValueError(f"{rec.get('run_id')}: cannot recover the group-operation price from rho_operations")
    return w


def ratios(rec, variant: str) -> dict:
    """IC / one-target rho, IC / independent-rho batch and IC / folded batch rho under `variant`."""
    total = rec.get("total_operations")
    r, k = int(rec["subgroup_order"]), int(rec["counts"].get("targets", 0))
    if total is None or k < 1:
        return {"single": None, "independent": None, "folded": None}
    u = unit_per_group_operation(rec)
    single = round(rho_reference.batch_group_operations(r, 1, 1, variant)) * u
    folded = round(rho_reference.batch_group_operations(r, k, automorphisms(rec), variant)) * u
    return {"single": total / single, "independent": total / (k * single), "folded": total / folded}


def table(rs, variant: str = "generous"):
    if variant not in rho_reference.VARIANTS:
        raise ValueError(f"unknown rho variant {variant!r}")
    lines = [f"Rho reference for every ratio column: **{variant}** — {rho_reference.model(variant)}.", "",
             "| regime | profile | targets | verified | total | unit | IC / one-target rho | "
             "IC / independent-rho batch | IC / folded batch rho | shared % |",
             "|---|---|--:|---|--:|---|--:|--:|--:|--:|"]
    for r in sorted(rs, key=lambda x: (regime(x), x["profile_id"])):
        w = r.get("warm") or {}
        total = r.get("total_operations")
        shared = w.get("shared_operations")
        q = ratios(r, variant)
        lines.append(f"| {regime(r)} | `{r['profile_id']}` | {r['counts'].get('targets', 0)} | "
                     f"{r.get('verified_scalar') is True} | {fmt(total)} | {r.get('operation_unit', '?')} | "
                     f"{fmt(q['single'])} | {fmt(q['independent'])} | {fmt(q['folded'])} | "
                     f"{fmt(100 * shared / total) if shared is not None and total else '—'} |")
    lines += ["",
              "Absolute totals are intentionally **not** compared across units. Binary receipts use calibrated rps; "
              "prime-orbit receipts use counted affine group operations. The last four columns are dimensionless, "
              f"and all three rho ratios use the `{variant}` variant on both regimes. "
              "For many-target claims, the folded batch-rho column is the strict cross-regime control."]
    return lines


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("jsonl", type=Path, nargs="+")
    ap.add_argument("--variant", choices=rho_reference.VARIANTS, default="generous",
                    help="rho convention applied to every ratio (default: generous, the one most favourable to rho)")
    a = ap.parse_args()
    print("\n".join(table(load(a.jsonl), a.variant)))


if __name__ == "__main__":
    main()
