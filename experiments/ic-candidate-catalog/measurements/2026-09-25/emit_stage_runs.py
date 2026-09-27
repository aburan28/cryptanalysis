#!/usr/bin/env python3
"""Convert the two matched N13 SAT stage receipts to contract-v2 run rows."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
CATALOG = HERE.parents[1]
sys.path.insert(0, str(CATALOG))
import analyze  # noqa: E402


def ns(seconds: float) -> int:
    return int(seconds * 1_000_000_000)


def main() -> None:
    output = HERE / "n13_sat_stage_runs.jsonl"
    if output.exists():
        raise SystemExit("output already exists")
    smoke = json.loads((HERE / "n13_sat_50ms.json").read_text())
    short = next(row for row in smoke["rows"] if not row["shifted"])
    long_receipt = json.loads((HERE / "n13_sat_1000ms.json").read_text())
    long = long_receipt["row"]
    source = smoke["sources"]["experiments/shifted-base-geometry/solver_cost.py"]
    assert source == long_receipt["source_sha256"]
    targets = [row["target"] for row in short["records"]]
    assert targets[:len(long["records"])] == [row["target"] for row in long["records"]]
    fixture = {"curve_ref": "shifted-base-geometry/toy13/seed87006",
               "stream_seed": 91001, "declared_query_cap": 32,
               "public_target_points": targets}
    fixture_digest = hashlib.sha256(json.dumps(fixture, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    rows = []
    for proposal_id, budget, item, receipt in (("Q1", 50, short, "n13_sat_50ms.json"),
                                               ("Q2", 1000, long, "n13_sat_1000ms.json")):
        attempts = len(item["records"])
        assert item["solver_statuses"] == {"timeout": attempts}
        phase_wall = {name: 0 for name in analyze.CONTRACT["phase_operations"]}
        phase_wall["setup"] = ns(item["setup_seconds"])
        phase_wall["precompute"] = ns(item["template_seconds"])
        phase_wall["queries"] = ns(item["phases"]["input_generation"])
        phase_wall["pdp"] = ns(item["phases"]["solver_load_solve_lift"])
        phase_wall["relation_check"] = ns(item["phases"].get("row_verification_rank", 0))
        row = {
            "schema_version": analyze.CONTRACT["schema_version"],
            "kind": "stage",
            "status": "budget",
            "termination_reason": item["status"],
            "proposal_id": proposal_id,
            "candidate_id": None,
            "run_id": f"{proposal_id}W{fixture_digest[:12]}R1",
            "workload_id": f"W{fixture_digest[:12]}",
            "pair_block_id": "seed91001",
            "source_curve_ref": fixture["curve_ref"],
            "profile_id": "n13_same_d3_m4",
            "isogeny_route_ref": "none",
            "subgroup_order": "2003",
            "provenance": {
                "workload_fixture_sha256": fixture_digest,
                "source_sha256": source,
                "host_id": "local_macos_arm64",
                "resource_envelope_id": "one_thread_stream_45_seconds",
                "calibration_id": "wall_only_operations_unpriced",
                "raw_receipt": receipt,
                "pdp_budget_ms": budget,
            },
            "counts": {
                "ordinary_queries": attempts,
                "solved_queries": 0,
                "verified_decompositions": 0,
                "verified_relations": 0,
                "novel_rows": 0,
                "effective_columns": item["columns"],
                "final_rank": item["initial_rank"] + item["rank_gain"],
                "pdp_attempts": attempts,
                "pdp_verified": 0,
                "pdp_proved_unsat": 0,
                "pdp_timeout": attempts,
                "pdp_budget": 0,
                "pdp_error": 0,
                "pdp_lift_rejected": 0,
            },
            "phase_operations": {name: None for name in analyze.CONTRACT["phase_operations"]},
            "phase_wall_ns": phase_wall,
            "online_phase_wall_ns": {name: None for name in analyze.CONTRACT["online_target_phases"]},
            "online_wall_ns": None,
            "rho_online_wall_ns": None,
            "rho_verified": None,
            "target_count": None,
            "target_point_sha256": None,
            "precomputation_ready": None,
            "total_operations": None,
            "rho_operations": None,
            "verified_scalar": False,
            "scalar_certificate_ref": None,
            "peak_rss_bytes": None,
            "wall_ns": ns(item["cold_seconds"]),
        }
        analyze.validate_run(row)
        rows.append(row)
    output.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


if __name__ == "__main__":
    main()
