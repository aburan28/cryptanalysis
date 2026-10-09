#!/usr/bin/env python3
"""Freeze the exact Q1104 d12 base for a sampled canonical-root pilot."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
N83 = HERE.parent
ROOT = N83.parents[1]
SOURCE = N83 / "Q1370_D10_CANONICAL_FULL_ENUMERATION_CONTINUATION_20261009/inputs"
D12 = N83 / "runs/q1104_seed_subspace_d12_20261006"
INPUTS = HERE / "inputs"
RUN = HERE / "runs/q1373_d12_root_cardinality_1m_sample_20261009"

SAMPLE_STATES = 1_000_000
RSS_CAP_MIB = 2048
WALL_CAP_SECONDS = 300
N = 83
KEY_BYTES = 21


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main() -> None:
    INPUTS.mkdir(parents=True, exist_ok=True)
    RUN.mkdir(parents=True, exist_ok=True)

    d12_stage_path = D12 / "d12_stage_result.json"
    d12_replay_path = D12 / "independent_sage_replay.json"
    d12_keys_path = D12 / "d12_canonical_orbit_keys.bin"
    stage = json.loads(d12_stage_path.read_text())
    replay = json.loads(d12_replay_path.read_text())
    factor = stage["factor_base"]
    K = int(factor["effective_relation_matrix_columns"])
    if stage.get("status") != "completed_stage_only" or replay.get("status") != "pass":
        raise ValueError("Q1104 d12 base and independent replay must both pass")
    if sha(d12_keys_path) != factor["canonical_orbit_key_file_sha256"]:
        raise ValueError("Q1104 d12 canonical-key receipt does not match the file")
    key_bytes = d12_keys_path.read_bytes()
    if len(key_bytes) != K * KEY_BYTES:
        raise ValueError("Q1104 d12 canonical-key file width or count is incorrect")
    keys = [int.from_bytes(key_bytes[offset:offset + KEY_BYTES], "little")
            for offset in range(0, len(key_bytes), KEY_BYTES)]
    if keys != sorted(set(keys)):
        raise ValueError("Q1104 d12 canonical keys are not sorted and unique")

    bridge = json.loads((SOURCE / "n83_onb_poly_bridge.json").read_text())
    if bridge.get("status") != "PASS" or bridge.get("curve_id") != stage["curve_id"]:
        raise ValueError("Q1370 ONB-to-polynomial bridge does not match Q1104 d12")
    cycle = bridge["onb_gamma_frobenius_coordinate_cycle"]
    images = [int(value) for value in bridge["onb_to_poly_basis_images"]]
    if len(cycle) != N or len(images) != N:
        raise ValueError("Q1370 bridge basis vectors or Frobenius cycle are incomplete")

    reps = []
    for key in keys:
        x_cycle = key >> N
        x_coords = sum(((x_cycle >> position) & 1) << coordinate
                       for position, coordinate in enumerate(cycle))
        x_poly = 0
        while x_coords:
            low = x_coords & -x_coords
            x_poly ^= images[low.bit_length() - 1]
            x_coords ^= low
        if not 0 <= x_poly < (1 << N):
            raise ValueError("mapped representative exceeds the GF(2^83) encoding")
        reps.append(x_poly)
    if len(reps) != K or len(set(reps)) != K:
        raise ValueError("d12 polynomial x representatives are not distinct")

    copy_map = {
        "native_s3_root_canonical": SOURCE / "native_s3_root_canonical",
        "native_s3_root_canonical.rs": SOURCE / "native_s3_root_canonical.rs",
        "build_receipt.json": SOURCE / "build_receipt.json",
        "n83_onb_poly_bridge.json": SOURCE / "n83_onb_poly_bridge.json",
        "ordinary_parent_manifest.json": SOURCE / "ordinary_parent_manifest.json",
        "d12_stage_result.json": d12_stage_path,
        "d12_independent_sage_replay.json": d12_replay_path,
        "d12_canonical_orbit_keys.bin": d12_keys_path,
    }
    for name, path in copy_map.items():
        shutil.copy2(path, INPUTS / name)
    reps_path = INPUTS / "d12_x_representatives_poly.bin"
    reps_path.write_bytes(b"".join(value.to_bytes(16, "little") for value in reps))

    parent = json.loads((INPUTS / "ordinary_parent_manifest.json").read_text())
    protocol = {
        "kind": "n83_q1373_d12_sampled_canonical_root_cardinality_protocol",
        "proposal_id": "Q1373",
        "candidate_id": None,
        "workload_id": parent["workload_id"],
        "run_id": None,
        "curve_id": stage["curve_id"],
        "stage_id": "n83_d12_canonical_root_cardinality_sample_20261009",
        "target_count": 1,
        "target_poly_xy": parent["target_poly_xy"],
        "input_law": "same frozen ordinary public subgroup target used by Q1370; this stage samples pair-root index states",
        "base_proposal_id": "Q1104_d12",
        "actual_usable_points_B": int(factor["actual_usable_points_B_before_folding"]),
        "folded_columns_K": K,
        "total_quotient_pair_states": K * K * N,
        "pair_state_cap": SAMPLE_STATES,
        "sampling": "native generator deterministic coprime stride without replacement over the full pair-state domain",
        "orientations_per_state": 1,
        "index_s3_window_size": 4096,
        "target_s3_window_schedule": [1, 16, 64, 256, 1024, 4096],
        "peak_rss_cap_mib": RSS_CAP_MIB,
        "native_wall_cap_seconds": WALL_CAP_SECONDS,
        "interpretation": "sampled root-cardinality and target-lookup diagnostic; not a full index build, complete query, natural relation-yield estimate, or DLP",
        "inputs_sha256": {
            "native_source": sha(INPUTS / "native_s3_root_canonical.rs"),
            "native_binary": sha(INPUTS / "native_s3_root_canonical"),
            "native_build_receipt": sha(INPUTS / "build_receipt.json"),
            "basis_bridge": sha(INPUTS / "n83_onb_poly_bridge.json"),
            "q1104_d12_stage": sha(INPUTS / "d12_stage_result.json"),
            "q1104_d12_replay": sha(INPUTS / "d12_independent_sage_replay.json"),
            "q1104_d12_keys": sha(INPUTS / "d12_canonical_orbit_keys.bin"),
            "d12_polynomial_representatives": sha(reps_path),
        },
    }
    manifest = {
        "kind": "q1373_n83_d12_sampled_canonical_root_manifest",
        "proposal_id": "Q1373",
        "candidate_id": None,
        "run_id": None,
        "stage_id": protocol["stage_id"],
        "workload_id": protocol["workload_id"],
        "curve_id": stage["curve_id"],
        "field_degree": N,
        "polynomial_low_terms": [0, 2, 4, 7],
        "subgroup_order": stage["subgroup_order"],
        "target_count": 1,
        "target_poly_xy": protocol["target_poly_xy"],
        "actual_usable_points_B": protocol["actual_usable_points_B"],
        "representative_count_K": K,
        "folded_columns_K": K,
        "factor_base_enumerated_set_sha256": factor["enumerated_set_sha256"],
        "representatives_file_sha256": sha(reps_path),
        "representative_encoding": "16-byte little-endian polynomial x values decoded from exact Q1104 d12 signed-Frobenius keys",
        "parent_factor_base_proposal_id": "Q1104",
        "pair_state_cap": SAMPLE_STATES,
        "peak_rss_cap_mib": RSS_CAP_MIB,
        "orientations_per_state": 1,
        "index_s3_window_size": 4096,
        "target_s3_window_schedule": [1, 16, 64, 256, 1024, 4096],
        "stage_protocol_sha256": None,
        "native_source_sha256": sha(INPUTS / "native_s3_root_canonical.rs"),
        "native_binary_sha256": sha(INPUTS / "native_s3_root_canonical"),
    }
    write_json(HERE / "protocol.json", protocol)
    manifest["stage_protocol_sha256"] = sha(HERE / "protocol.json")
    write_json(HERE / "manifest.json", manifest)
    receipt = {
        "kind": "q1373_frozen_input_receipt",
        "status": "PASS",
        "protocol_sha256": sha(HERE / "protocol.json"),
        "manifest_sha256": sha(HERE / "manifest.json"),
        "input_sha256": protocol["inputs_sha256"],
        "base_B": protocol["actual_usable_points_B"],
        "base_K": K,
        "sample_states": SAMPLE_STATES,
        "full_states": K * K * N,
        "workload_id": protocol["workload_id"],
    }
    write_json(HERE / "freeze_receipt.json", receipt)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
