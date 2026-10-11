#!/usr/bin/env python3
"""Recompute prefix Frobenius overlaps from GF(2) nullspaces, without the map."""

import argparse
import hashlib
import importlib.util
import json
import struct
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / "experiments/ecc2k130-263-w24-exact-base-20261005/runs/w24-b2048-r1"
PARENT = ROOT / "experiments/ecc2k130-263-w24-orbit-columns-20261005"
LINEAR_SOURCE = PARENT / "independent_direct.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_linear():
    spec = importlib.util.spec_from_file_location("w24_linear_replay", LINEAR_SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists()
    start = time.perf_counter()
    config = json.loads((HERE / "CONFIG.json").read_text())
    analysis_path = HERE / "analysis.json"
    analysis = json.loads(analysis_path.read_text())
    assert analysis["status"] == "exact_restriction_pending_independent_direct_replay"
    assert analysis["configuration_sha256"] == sha(HERE / "CONFIG.json")
    assert analysis["analyzer_sha256"] == sha(HERE / "analyze.py")
    parent_independent = json.loads((PARENT / "independent_direct.json").read_text())
    assert parent_independent["status"] == \
        "PASS_INDEPENDENT_DIRECT_AND_PARTITION_GIVEN_RECIPROCAL_ZERO"
    assert parent_independent["verifier_source_sha256"] == sha(LINEAR_SOURCE)
    assert parent_independent["checked_powers"] == 65
    native_path = PARENT / "runs/w24-native/native.json"
    assert sha(native_path) == config["parent_orbit_native_sha256"]
    native = json.loads(native_path.read_text())
    assert native["reciprocal_hits"] == 0
    linear = load_linear()
    bitset = linear.read_base(BASE / "source-masks.bin.gz",
                              config["source_masks_gzip_sha256"],
                              config["source_masks_raw_sha256"],
                              config["source_base_full_signed_classes"])
    cutoff = config["source_prefix_last_mask"]
    assert sum(bitset[:cutoff+1]) == config["source_prefix_signed_classes"]
    basis = [(1 << j) ^ linear.trace(1 << j) for j in range(1, 25)]
    assert all(linear.trace(value) == 0 for value in basis)
    trace_bits = sum(linear.trace(1 << j) << (j - 1) for j in range(1, 25))
    images = basis[:]
    edges = []
    per_power = []
    for power in range(1, 66):
        images = [linear.square(value) for value in images]
        rows = [sum(((images[j] >> bit) & 1) << j for j in range(24))
                for bit in range(25, 131)]
        vectors = linear.nullspace(rows, 24)
        count = 0
        for mask in linear.span(vectors)[1:]:
            if mask > cutoff or not bitset[mask]:
                continue
            image = 0
            for index, element in enumerate(images):
                if mask & (1 << index):
                    image ^= element
            assert image < (1 << 25)
            other = image >> 1
            assert (image & 1) == ((other & trace_bits).bit_count() & 1)
            if other <= cutoff and bitset[other]:
                edges.append((mask, other))
                count += 1
        per_power.append({"power": power, "direct_hits_in_prefix": count,
                          "intersection_dimension": len(vectors)})
    labels, sizes = linear.partition_from_edges(edges)
    full_map_path = PARENT / "runs/w24-native/nontrivial-components.bin"
    assert sha(full_map_path) == config["parent_component_map_sha256"]
    raw = full_map_path.read_bytes()
    selected_labels = [(mask, label) for mask, label in
                       struct.iter_unpack("<II", raw) if mask <= cutoff]
    assert labels == selected_labels
    nontrivial_reps = len({label for _, label in labels})
    selected = config["source_prefix_signed_classes"]
    saved = len(labels) - nontrivial_reps
    assert saved == analysis["source_columns_saved"]
    assert selected - saved == analysis[
        "source_sign_plus_frobenius_potential_columns"]
    assert len(edges) == parent_independent["direct_hits"]
    assert sum(row["direct_hits_in_prefix"] for row in per_power) == len(edges)
    receipt = {
        "schema": "ecc2k130-equal-w24-orbit-direct-verification-v1",
        "status": "PASS_INDEPENDENT_DIRECT_PREFIX_PARTITION_GIVEN_PARENT_RECIPROCAL_ZERO",
        "candidate_id": None,
        "selected_signed_classes": selected,
        "direct_hits": len(edges),
        "nontrivial_masks": len(labels),
        "nontrivial_representatives": nontrivial_reps,
        "saved_columns": saved,
        "potential_source_columns": selected - saved,
        "component_size_histogram": {str(k): v for k, v in sorted(sizes.items())},
        "per_power": per_power,
        "reciprocal_hits_independently_checked": False,
        "reciprocal_zero_inherited_from_parent_full_native_and_portable": True,
        "parent_independent_sha256": sha(PARENT / "independent_direct.json"),
        "parent_linear_source_sha256": sha(LINEAR_SOURCE),
        "parent_component_map_sha256": sha(full_map_path),
        "analysis_sha256": sha(analysis_path),
        "verifier_sha256": sha(Path(__file__)),
        "wall_seconds_unisolated_diagnostic": time.perf_counter() - start,
        "actual_relation_matrix_columns": None,
        "natural_pdp_yield": None,
        "online_wall_time": None,
        "rho_ratio": None,
    }
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({key: receipt[key] for key in
                      ("status", "direct_hits", "saved_columns",
                       "potential_source_columns")}))


if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("assertions must remain enabled")
    main()
