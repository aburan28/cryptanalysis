#!/usr/bin/env python3
"""Recompute Q1371's packed-index geometry from audited Q1104 inputs."""

from __future__ import annotations

import hashlib
import json
import math
from decimal import Decimal, getcontext
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
N83 = REPO / "experiments/koblitz-n83-index-design-20260929"
Q1104_RUNS = N83 / "runs/q1104_seed_subspace_d10_d11_20261003"
D12 = N83 / "runs/q1104_seed_subspace_d12_20261006"
getcontext().prec = 40


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def model_base(label: str, stage: dict, n: int, expected_mean: str | None = None) -> dict:
    fb = stage["factor_base"]
    B = int(fb["actual_usable_points_B_before_folding"])
    K = int(fb["effective_relation_matrix_columns"])
    states = K * K * n
    state_bits = (states - 1).bit_length()
    descriptor_bits = state_bits + 1 + 7
    record_bytes = 11 + (descriptor_bits + 7) // 8
    root_records = 2 * states
    payload = root_records * record_bytes
    subgroup_order = int(stage["subgroup_order"])
    mean = Decimal(math.comb(B, 5)) / Decimal(subgroup_order)
    if expected_mean is not None:
        assert abs(mean - Decimal(expected_mean)) < Decimal("0.000001")
    return {
        "name": label,
        "field_degree": n,
        "B_actual_usable_before_folding": B,
        "K_effective_columns": K,
        "pair_root_states": states,
        "state_id_bits": state_bits,
        "descriptor_bits": descriptor_bits,
        "record_bytes": record_bytes,
        "assumed_roots_per_state": 2,
        "projected_root_records": root_records,
        "raw_payload_bytes": payload,
        "raw_payload_gib_decimal": str(Decimal(payload) / Decimal(2**30)),
        "mean_distinct_unordered_five_supports_per_uniform_target": str(mean),
        "optimistic_target_queries_for_K_rows": str(Decimal(K) / mean),
        "query_count_assumption": "every support is found and contributes a novel rank-increasing row",
        "measured_natural_query_yield": None,
    }


def main() -> None:
    d10 = read_json(Q1104_RUNS / "d10_stage_result.json")
    d11 = read_json(Q1104_RUNS / "d11_stage_result.json")
    d12_audit = read_json(D12 / "q1104_d12_exact_count_audit.json")
    d12_stage = read_json(D12 / "d12_stage_result.json")

    assert d10["status"] == d11["status"] == "completed_stage_only"
    assert d12_audit["status"] == "pass_exact_base_geometry_and_combinatorial_audit"
    assert d12_audit["measurements"]["natural_queries"] == 0
    assert d12_audit["measurements"]["verified_natural_relations"] == 0
    assert d12_audit["factor_base"]["actual_usable_points_B_before_folding"] == 337146
    assert d12_audit["factor_base"]["folded_columns_K"] == 2031
    assert d12_audit["root_index_models"]["packed_two_root_per_state_layout"]["raw_sorted_payload_bytes"] == "10955896416"

    bases = [
        model_base("Q1104_d10", d10, 83, "0.0103936"),
        model_base("Q1104_d11", d11, 83, "0.470297"),
        model_base("Q1104_d12", {
            "factor_base": {
                "actual_usable_points_B_before_folding": d12_audit["factor_base"]["actual_usable_points_B_before_folding"],
                "effective_relation_matrix_columns": d12_audit["factor_base"]["folded_columns_K"],
            },
            "subgroup_order": d12_audit["subgroup_order"],
        }, 83, "15.0129583876819001806996"),
    ]

    assert d12_stage["status"] == "completed_stage_only"
    assert bases[0]["raw_payload_bytes"] == 596739456
    assert bases[1]["raw_payload_bytes"] == 2741671936
    assert bases[2]["raw_payload_bytes"] == 10955896416
    assert bases[2]["state_id_bits"] == 29
    assert bases[2]["record_bytes"] == 16

    payload = bases[2]["raw_payload_bytes"]
    bucket_count = 256
    sort_temp_cap = 64 * 2**20
    reserve = (5 * 2**30) // 4
    ssd_buckets = 55
    system_buckets = bucket_count - ssd_buckets
    ssd_payload = (payload * ssd_buckets + bucket_count - 1) // bucket_count
    system_payload = payload - (payload * ssd_buckets // bucket_count)
    ssd_peak = ssd_payload + sort_temp_cap
    system_peak = system_payload + sort_temp_cap

    # Values are a snapshot captured 2026-10-09 with `df -k`.
    disk_free = {
        "ssd_volume_free_bytes": 3866336 * 1024,
        "system_volume_free_bytes": 10002508 * 1024,
    }
    remaining = {
        "ssd_volume_after_projected_peak_bytes": disk_free["ssd_volume_free_bytes"] - ssd_peak,
        "system_volume_after_projected_peak_bytes": disk_free["system_volume_free_bytes"] - system_peak,
    }
    bucket_avg_bytes = (payload + bucket_count - 1) // bucket_count
    model = {
        "proposal_id": "Q1371",
        "candidate_id": None,
        "workload_id": None,
        "run_id": None,
        "curve_id": "EC1N83Ckb1h876c2921cb64",
        "model_kind": "packed_external_bucket_index_and_relation_first_moment",
        "status": "design_projection_only",
        "source_artifacts": {
            "d10_stage_result_sha256": sha256(Q1104_RUNS / "d10_stage_result.json"),
            "d11_stage_result_sha256": sha256(Q1104_RUNS / "d11_stage_result.json"),
            "d12_stage_result_sha256": sha256(D12 / "d12_stage_result.json"),
            "d12_exact_count_audit_sha256": sha256(D12 / "q1104_d12_exact_count_audit.json"),
        },
        "bases": bases,
        "d12_bucket_layout": {
            "key_digest_prefix_bits": 8,
            "bucket_count": bucket_count,
            "final_bucket_average_bytes": bucket_avg_bytes,
            "final_bucket_average_mib": str(Decimal(bucket_avg_bytes) / Decimal(2**20)),
            "per_bucket_sort_memory_cap_bytes": sort_temp_cap,
            "sort_temporary_file_cap_bytes": sort_temp_cap,
            "ssd_bucket_count": ssd_buckets,
            "system_volume_bucket_count": system_buckets,
            "ssd_projected_payload_bytes": ssd_payload,
            "system_projected_payload_bytes": system_payload,
            "ssd_projected_peak_bytes_including_one_sort_temp": ssd_peak,
            "system_projected_peak_bytes_including_one_sort_temp": system_peak,
            "measured_disk_free_snapshot_bytes": disk_free,
            "projected_free_after_peak_bytes": remaining,
            "minimum_reserve_bytes_per_volume": reserve,
            "passes_current_snapshot_reserve": min(remaining.values()) >= reserve,
            "bucket_hash_balance_measured": False,
            "index_build_run": None,
        },
        "resource_policy": {
            "combined_process_tree_rss_cap_bytes": 2 * 2**30,
            "streaming_buffers_cap_bytes": 256 * 2**20,
            "max_open_bucket_files": 64,
            "record_codec_and_digest_wall_time": None,
            "target_random_lookup_wall_time": None,
        },
        "uniform_target_relation_model": {
            "support_definition": "distinct unordered five-point supports",
            "relation_query_times": None,
            "verified_natural_relations": 0,
            "novel_rank_per_query": None,
            "target_dlp": None,
            "rho_pair": None,
        },
        "claim_boundary": "Exact input geometry and storage arithmetic plus uniform-target first moments. Not measured ordinary relation yield, a built index, solver performance, DLP, or speedup.",
    }
    (HERE / "resource_model.json").write_text(json.dumps(model, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
