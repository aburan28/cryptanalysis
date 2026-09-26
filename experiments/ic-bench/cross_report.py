#!/usr/bin/env python3
"""Compare normalized binary- and prime-field IC receipts without mixing units.

Absolute operation totals remain in each regime's native unit. Cross-regime
columns are dimensionless ratios to the matched rho controls.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path

def load(paths):
    out=[]
    for p in paths:
        out += [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
    return out

def regime(r):
    return "prime" if r["source_curve_ref"].startswith("EC1P") else "binary"

def fmt(x):
    return "—" if x is None else f"{x:.4g}" if isinstance(x,float) else f"{x:,}"

def table(rs):
    lines=["| regime | profile | targets | verified | total | unit | IC / one-target rho | IC / independent-rho batch | IC / folded batch rho | shared % |",
           "|---|---|--:|---|--:|---|--:|--:|--:|--:|"]
    for r in sorted(rs,key=lambda x:(regime(x),x["profile_id"])):
        w=r.get("warm") or {}; total=r.get("total_operations")
        shared=w.get("shared_operations")
        lines.append(f"| {regime(r)} | `{r['profile_id']}` | {r['counts'].get('targets',0)} | "
          f"{r.get('verified_scalar') is True} | {fmt(total)} | {r.get('operation_unit','?')} | "
          f"{fmt(r.get('ratio_to_rho'))} | {fmt(r.get('ratio_to_independent_rho_batch'))} | "
          f"{fmt(r.get('ratio_to_batch_floor'))} | "
          f"{fmt(100*shared/total) if shared is not None and total else '—'} |")
    lines += ["",
      "Absolute totals are intentionally **not** compared across units. Binary receipts use calibrated rps; "
      "prime-orbit receipts use counted affine group operations. The last three columns are dimensionless. "
      "For many-target claims, the folded batch-rho column is the strict cross-regime control."]
    return lines

def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument("jsonl",type=Path,nargs="+")
    a=ap.parse_args(); print("\\n".join(table(load(a.jsonl))))
if __name__=="__main__": main()
