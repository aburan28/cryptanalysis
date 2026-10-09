#!/usr/bin/env python3
"""Exact pair-index build dimensions for the N53 multiplier closure."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GEOMETRY = HERE.parent / "ic-ideas-20261007/results/a1_n53_k600_followup_final.json"
RUST = Path("/Volumes/SSD990/crypto/examples/koblitz_orbit_dlp_slice_ic_fastindex.rs")


def index_budget(representatives: int, n: int):
    cells = representatives*representatives*n
    # The frozen builder stores one 24-byte State for each S3 root cell and
    # two 16-byte root-entry pairs before constructing the hash tables.  All
    # distinct-x pairs from actual curve points have rational S3 roots.  With
    # full generic Frobenius orbits, only the K same-representative/shift-zero
    # cells can have equal x-coordinates.
    guaranteed_generic = cells-representatives
    return {"folded_representatives": representatives,
            "s3_root_calls": cells,
            "generic_distinct_x_cells_lower_bound": guaranteed_generic,
            "state_bytes_lower_bound": 24*guaranteed_generic,
            "two_root_entry_bytes_lower_bound": 32*guaranteed_generic,
            "combined_pre_merge_bytes_lower_bound": 56*guaranteed_generic}


def main():
    geo = json.loads(GEOMETRY.read_text())
    assert geo["status"] == "COMPLETE" and geo["field_degree"] == 53
    assert geo["seed_folded_columns"] == 600
    assert geo["multiplier_classes_after_sign_frobenius"] == 10
    assert geo["closure_folded_columns"] == 6000
    equal_size_seed_count = geo["seed_folded_columns"] // 10
    cases = {"frozen_244_seed": index_budget(244, 53),
             "600_seed": index_budget(600, 53),
             "600_seed_full_closure": index_budget(6000, 53),
             "60_seed_ten_class_equal_geometry": index_budget(600, 53)}
    result = {"schema_version": 1, "proposal_id": "A1",
              "candidate_id": None, "run_id": None,
              "curve_id": geo["curve_id"],
              "multiplier_classes_after_sign_frobenius": 10,
              "full_closure_index_call_factor_vs_seed":
                  cases["600_seed_full_closure"]["s3_root_calls"] /
                  cases["600_seed"]["s3_root_calls"],
              "equal_geometry_seed_folded_columns": equal_size_seed_count,
              "equal_geometry_independent_log_columns": equal_size_seed_count,
              "cases": cases,
              "scope": "frozen fastindex4 pair-index build resource lower bound; no measured natural-query yield",
              "geometry_receipt_sha256": hashlib.sha256(GEOMETRY.read_bytes()).hexdigest(),
              "frozen_fastindex_source_sha256": hashlib.sha256(RUST.read_bytes()).hexdigest(),
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    output = HERE / "a1_fastindex_budget.json"
    if output.exists():
        raise FileExistsError(output)
    output.write_text(json.dumps(result, sort_keys=True, indent=2)+"\n")
    print(json.dumps({"full_closure_calls":
                          cases["600_seed_full_closure"]["s3_root_calls"],
                      "full_closure_pre_merge_GB_lower_bound":
                          cases["600_seed_full_closure"]["combined_pre_merge_bytes_lower_bound"]/1e9},
                     sort_keys=True))


if __name__ == "__main__":
    main()
