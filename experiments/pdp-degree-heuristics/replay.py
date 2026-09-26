#!/usr/bin/env python3
"""Recompute a sample of receipts with the current code and compare deterministic fields.

    python3 replay.py results/m2.jsonl results/sym_m2.jsonl --sample 12

Operation counts, degree histograms, exact yields, factor-base digests and workload IDs
are deterministic for a given source state; wall times are not compared.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import profile as prof  # noqa: E402
from toycurve import ToyCurve  # noqa: E402


def fields(card: dict) -> dict:
    out = {
        "factor_base_sha256": card["factor_base_sha256"],
        "workload_id": card["workload_id"],
        "exact_yield": card["yield"]["exact"],
    }
    for mode in card["point_decomposition"].get("modes", ["xl"]):
        out[f"{mode}_D_hist"] = card["degrees"][mode]["D_solve_hist"]
        out[f"{mode}_planted_hist"] = card["degrees"][mode]["planted_D_solve_hist"]
        out[f"{mode}_ops_mean"] = card["cost"][mode]["ops_per_attempt_mean"]
    return out


def recompute(card: dict) -> dict:
    cell = card["cell"]
    limits = card["point_decomposition"]["limits"]
    form = cell.get("formulation", "direct")
    cfg = {
        "n": cell["n"], "m": cell["m"], "l": cell["l"], "family": cell["family"], "seed": cell["seed"],
        "limits": limits, "modes": card["point_decomposition"].get("modes", ["xl", "mxl"]),
        "formulation": form, "max_solutions": 1 << 16 if form != "direct" else 4096,
    }
    C = ToyCurve(cell["n"])
    wid, wrec, targets = prof.workload(C, card["workload"]["seed"], card["workload"]["target_count"])
    struct = prof.task_structure(cfg)
    records = [prof.task_target(cfg, "ordinary", i, t) for i, t in enumerate(targets)]
    # receipts before planted_attempts was recorded used the sweep settings
    tried = card["counts"].get("planted_attempts") or (8 if cell["m"] == 2 else 2 if cell["l"] == 5 else 6)
    records += [prof.task_target(cfg, "planted", i, None) for i in range(tried)]
    return prof.summarize(cfg, struct, records, wid, wrec, 0)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("results", nargs="+", type=Path)
    ap.add_argument("--sample", type=int, default=10)
    ap.add_argument("--max-ops", type=float, default=2e5, help="replay only receipts cheaper than this per query")
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    cards = [json.loads(line) for p in args.results for line in p.read_text().splitlines() if line.strip()]
    cards = [c for c in cards if c.get("schema") == "pdp-degree-profile/1"
             and all((c["cost"][m]["ops_per_attempt_mean"] or 0) < args.max_ops for m in c["point_decomposition"].get("modes", ["xl"]))]
    picks = random.Random(args.seed).sample(cards, min(args.sample, len(cards)))
    bad = 0
    for c in picks:
        a, b = fields(c), fields(recompute(c))
        diff = {k: (a[k], b[k]) for k in a if a[k] != b[k]}
        bad += bool(diff)
        print(("OK  " if not diff else "DIFF") + f" {c['label']} m={c['cell']['m']}" + (f" {diff}" if diff else ""), flush=True)
    print(f"{len(picks) - bad}/{len(picks)} receipts reproduced")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
