#!/usr/bin/env python3
"""Validate bounded N83 encoding receipts and emit a stage-only ledger."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PROTOCOL = HERE / "shifted_pdp_protocol.json"
PUBLIC = HERE.parent / "hamming-ic-e2e-20260929/runs/n83_w34_sat_fixture_v1/public_input.json"
RUNS = HERE / "runs"
ACCEPTED = {
    "shifted_m7_d12": "shifted_m7_d12_s3_encoding_v2",
    "shifted_m8_d11": "shifted_m8_d11_s3_encoding_v1",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def main() -> None:
    protocol = load(PROTOCOL)
    public = load(PUBLIC)
    assert sha(PUBLIC) == protocol["public_input_sha256"]
    branch_x = str(public["ordinary"]["raw_target_fiber"][0]["x"])
    failure = load(RUNS / "shifted_m7_d12_s3_encoding_v1/guard_failure.json")
    assert failure["status"] == "INVALID_GUARD" and failure["promotable"] is False
    rows = []
    for label, folder_name in ACCEPTED.items():
        folder = RUNS / folder_name
        inner_path, outer_path = folder / "receipt.json", folder / "outer_receipt.json"
        inner, outer = load(inner_path), load(outer_path)
        assert inner["status"] == outer["status"] == "ENCODING_COMPLETE"
        assert outer["guard"] is None and outer["exit_code"] == 0
        assert outer["inner_receipt_sha256"] == sha(inner_path)
        assert inner["protocol_sha256"] == outer["protocol_sha256"] == sha(PROTOCOL)
        assert inner["public_input_sha256"] == sha(PUBLIC)
        assert inner["branch_target_x_decimal"] == branch_x
        assert inner["curve_id"] == outer["curve_id"] == protocol["curve_id"]
        assert inner["geometry_sha256"] == next(
            option["geometry_sha256"] for option in protocol["options"]
            if option["label"] == label)
        assert outer["peak_process_tree_rss_bytes_sampled"] < \
            protocol["max_process_tree_rss_bytes"]
        assert outer["external_wall_ns"] < protocol["max_total_wall_seconds"] * 10**9
        assert inner["xcnf_bytes"] > 0 and len(inner["xcnf_sha256"]) == 64
        xcnf = folder / "branch.xcnf"
        if xcnf.is_file():
            assert xcnf.stat().st_size == inner["xcnf_bytes"]
            assert sha(xcnf) == inner["xcnf_sha256"]
        rows.append({
            "label": label, "candidate_id": None,
            "status": "ENCODING_COMPLETE", "curve_id": protocol["curve_id"],
            "public_input_sha256": sha(PUBLIC),
            "branch_target_x_decimal": branch_x,
            "inner_receipt_sha256": sha(inner_path),
            "outer_receipt_sha256": sha(outer_path),
            "factor_coordinates": inner["nominal_factor_boolean_coordinates"],
            "middle_coordinates": inner["unrestricted_middle_boolean_coordinates"],
            "s3_constraints": inner["s3_constraints"],
            "variables": inner["circuit"]["variables"],
            "cnf_clauses": inner["circuit"]["cnf_clauses"],
            "xor_rows": inner["circuit"]["xor_rows"],
            "xcnf_bytes": inner["xcnf_bytes"],
            "xcnf_sha256": inner["xcnf_sha256"],
            "build_wall_ns_exploratory": inner["circuit_build_wall_ns_exploratory"],
            "write_wall_ns_exploratory": inner["xcnf_write_wall_ns_exploratory"],
            "external_wall_ns_exploratory": outer["external_wall_ns"],
            "peak_process_tree_rss_bytes_sampled": outer["peak_process_tree_rss_bytes_sampled"],
            "sat_status": None, "verified_decompositions": None,
            "ordinary_query_yield": None, "novel_rank": None,
            "target_dlp_verified": None, "rho_online_wall_ns": None,
            "online_speedup": None,
        })
    output = {
        "schema_version": 1, "kind": "n83_shifted_s3_encoding_stage_ledger",
        "protocol_sha256": sha(PROTOCOL), "source_sha256": sha(Path(__file__)),
        "invalid_guard_attempt": "shifted_m7_d12_s3_encoding_v1",
        "rows": rows,
        "claim_boundary": protocol["claim_boundary"],
    }
    (HERE / "encoding_screen.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"rows": len(rows), "status": "VALIDATED"}))


if __name__ == "__main__":
    main()
