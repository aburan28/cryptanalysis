#!/usr/bin/env python3
"""Find the smallest sorted canonical-orbit prefix retaining a frozen witness."""

import hashlib
import json
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    output = HERE / "prefix.json"
    prefix_path = HERE / "witness_prefix_keys_and_logs.bin"
    assert not output.exists() and not prefix_path.exists(), "evidence already exists"
    archive = (HERE / protocol["archive"]).resolve()
    parent_path = (HERE / protocol["parent_base"]).resolve()
    source_path = (HERE / protocol["parent_keys_and_logs"]).resolve()
    assert sha(archive) == protocol["archive_sha256"]
    assert sha(parent_path) == protocol["parent_base_sha256"]
    assert sha(source_path) == protocol["parent_keys_and_logs_sha256"]
    parent = json.loads(parent_path.read_text())
    assert parent["curve_id"] == protocol["curve_id"]
    assert parent["factor_base"]["selected_point_orbits"] == protocol[
        "expected_original_orbits"]
    with tarfile.open(archive, "r:gz") as stream:
        member = stream.extractfile(protocol["archive_member"])
        assert member is not None
        witness_bytes = member.read()
    witness = json.loads(witness_bytes)
    assert witness["curve_id"] == protocol["curve_id"]
    assert witness["factor_base"]["key_and_log_file_sha256"] == sha(source_path)
    relations = witness["verified_public_target_relations"]
    assert len(relations) == 1
    relation = relations[0]
    indices = relation["zero_pair_indices"] + relation["query_pair_indices"]
    assert indices == protocol["expected_witness_indices"]
    assert relation["independent_scalar_replay"] is True
    L = protocol["orbit_size"]
    K = max(index // L for index in indices) + 1
    assert K == protocol["expected_minimum_sorted_prefix_orbits"]
    assert max(indices) >= (K - 1) * L and all(index < K * L for index in indices)
    parent_data = source_path.read_bytes()
    assert len(parent_data) == protocol["record_bytes"] * protocol[
        "expected_original_orbits"]
    prefix = parent_data[:K * protocol["record_bytes"]]
    keys = [int.from_bytes(prefix[i:i + 21], "little")
            for i in range(0, len(prefix), 32)]
    assert keys == sorted(set(keys))
    prefix_path.write_bytes(prefix)
    key_stream = b"".join(prefix[i:i + 21] for i in range(0, len(prefix), 32))
    log_stream = b"".join(prefix[i + 21:i + 32] for i in range(0, len(prefix), 32))
    M = 1 << 32
    Q = 80 * (1 << 29)
    domain = 83 * K * (K - 1)
    assert domain >= M + Q
    record = {
        "kind": "n83_retrospective_witness_preserving_sorted_prefix",
        "status": "derived_pending_independent_sage_replay",
        "curve_id": protocol["curve_id"],
        "candidate_id": None,
        "K": K,
        "actual_usable_points_B_before_folding": K * L,
        "pair_rank_domain": domain,
        "M32_plus_80_R29_margin": domain - M - Q,
        "witness_indices": indices,
        "witness_orbit_indices": [i // L for i in indices],
        "witness_scalar": str(relation["recovered_scalar"]),
        "public_target": witness["public_target"],
        "witness_receipt_sha256": hashlib.sha256(witness_bytes).hexdigest(),
        "protocol_sha256": sha(protocol_path),
        "parent_file_sha256": sha(source_path),
        "prefix_file_sha256": sha(prefix_path),
        "canonical_key_sha256": hashlib.sha256(key_stream).hexdigest(),
        "canonical_log_sha256": hashlib.sha256(log_stream).hexdigest(),
        "derivation_source_sha256": sha(Path(__file__)),
        "interpretation": protocol["interpretation"],
    }
    output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"K": K, "B": K * L, "margin": domain - M - Q,
                      "prefix_sha256": record["prefix_file_sha256"]}))


if __name__ == "__main__":
    main()
