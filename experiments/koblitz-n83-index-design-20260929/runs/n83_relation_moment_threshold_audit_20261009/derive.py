#!/usr/bin/env python3
"""Recompute N83 unordered m-summand relation first-moment thresholds."""

from __future__ import annotations

import hashlib
import json
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
ORDER = 2417851639230796216685689
BASES = [
    {
        "proposal_id": "Q1104-d10",
        "evidence_status": "measured_stage_result",
        "B": 78684,
        "K": 474,
        "base_construction_wall_ns": 208299458,
        "peak_rss_bytes": 23822336,
        "source": "experiments/koblitz-n83-index-design-20260929/runs/q1104_seed_subspace_d10_d11_20261003/d10_stage_result.json",
        "source_sha256": "36accab5ab01ce15ccfedeb3090aaf14ac1792a3f3cb5f910885b4b0e534912f",
    },
    {
        "proposal_id": "Q1104-d11",
        "evidence_status": "measured_stage_result",
        "B": 168656,
        "K": 1016,
        "base_construction_wall_ns": 462316833,
        "peak_rss_bytes": 25509888,
        "source": "experiments/koblitz-n83-index-design-20260929/runs/q1104_seed_subspace_d10_d11_20261003/d11_stage_result.json",
        "source_sha256": "96c73b1b8a4f43304e5b73a731fad056eeb18ef19e7f0ba962b2883670486684",
    },
]


def ratio(B: int, m: int) -> dict[str, str | int]:
    numerator = comb(B, m)
    return {
        "m": m,
        "B": B,
        "numerator_C_B_m": str(numerator),
        "denominator_r": str(ORDER),
        "mean_decimal": f"{numerator / ORDER:.15g}",
        "markov_hit_probability_upper_bound": f"{min(1, numerator / ORDER):.15g}",
    }


def threshold(m: int) -> dict[str, str | int]:
    lo, hi = 1, 1_000_000_000
    while lo < hi:
        mid = (lo + hi) // 2
        if comb(mid, m) >= ORDER:
            hi = mid
        else:
            lo = mid + 1
    return {
        "m": m,
        "minimum_B_with_mean_at_least_one": lo,
        "mean_at_B_decimal": f"{comb(lo, m) / ORDER:.15g}",
        "mean_at_B_minus_one_decimal": f"{comb(lo - 1, m) / ORDER:.15g}",
    }


def verify_sources() -> None:
    for base in BASES:
        source = Path(base["source"])
        if not source.is_absolute():
            source = ROOT / source
        actual = hashlib.sha256(source.read_bytes()).hexdigest()
        assert actual == base["source_sha256"], (base["source"], actual)


def main() -> None:
    verify_sources()
    record = {
        "schema": "n83-relation-moment-audit-v1",
        "kind": "analytic_unordered_relation_first_moment",
        "curve_id": "EC1N83Ckb1h876c2921cb64",
        "field": "GF(2^83)",
        "subgroup_order": str(ORDER),
        "candidate_id": None,
        "workload_id": None,
        "run_id": None,
        "formula": "E[number of unordered m-subsets summing to a uniform target] = binomial(B,m)/r",
        "thresholds": [threshold(m) for m in (4, 5)],
        "factor_base_records": [
            {**base, "moments": [ratio(base["B"], m) for m in (4, 5)]}
            for base in BASES
        ],
        "interpretation": (
            "These are first moments, not measured natural-query hit rates. "
            "min(1, mean) is only a Markov upper bound on hit probability. "
            "The Q1104 rows have measured base-construction costs, while "
            "ordinary-query relation yield remains unmeasured."
        ),
    }
    (HERE / "relation_moment_thresholds.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(record["thresholds"], indent=2))
    for base in record["factor_base_records"]:
        print(base["proposal_id"], json.dumps(base["moments"], sort_keys=True))


if __name__ == "__main__":
    main()
