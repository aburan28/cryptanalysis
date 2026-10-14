#!/usr/bin/env python3
"""Freeze equal-size source/native W24 mask policies without duplicating streams."""

import argparse
import gzip
import hashlib
import json
import struct
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CONFIG = HERE / "CONFIG.json"
W24 = ROOT / "experiments/ecc2k130-263-w24-exact-base-20261005"
ROUTE = ROOT / "experiments/koblitz-polynomial-w-pair-20260925/ecc2k130_degree263_route_manifest.json"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def control_indices(domain, policy, count, size):
    selected = []
    used = set()
    counter = 0
    while len(selected) < count:
        payload = f"{domain}:{policy}:{counter}".encode("utf-8")
        index = int.from_bytes(hashlib.sha256(payload).digest(), "big") % size
        if index not in used:
            selected.append(index)
            used.add(index)
        counter += 1
    return selected, counter


def scan(path, compressed_sha, raw_sha, expected_count, selected_count,
         indices):
    if sha256(path) != compressed_sha:
        raise ValueError(f"wrong gzip hash: {path}")
    raw_digest = hashlib.sha256()
    selected_digest = hashlib.sha256()
    selected_positions = set(indices)
    selected_masks = {}
    previous = 0
    count = 0
    last_selected = None
    first_excluded = None
    with gzip.open(path, "rb") as stream:
        while chunk := stream.read(1 << 20):
            if len(chunk) % 4:
                raise ValueError("partial uint32 mask in stream")
            raw_digest.update(chunk)
            take = max(0, min(selected_count - count, len(chunk) // 4))
            selected_digest.update(chunk[:4 * take])
            for (mask,) in struct.iter_unpack("<I", chunk):
                if not 0 < mask < (1 << 24) or mask <= previous:
                    raise ValueError("invalid or unordered W24 mask")
                if count in selected_positions:
                    selected_masks[count] = mask
                if count == selected_count - 1:
                    last_selected = mask
                if count == selected_count:
                    first_excluded = mask
                previous = mask
                count += 1
    if count != expected_count or raw_digest.hexdigest() != raw_sha:
        raise ValueError("wrong raw count or hash")
    if len(selected_masks) != len(indices):
        raise ValueError("control selection incomplete")
    return {
        "full_signed_columns": count,
        "selected_signed_columns": selected_count,
        "selected_usable_points_B": 2 * selected_count,
        "full_raw_sha256": raw_digest.hexdigest(),
        "selected_mask_stream_sha256": selected_digest.hexdigest(),
        "last_selected_mask": last_selected,
        "first_excluded_mask": first_excluded,
        "last_full_mask": previous,
        "control_indices_selection_order": indices,
        "control_masks_selection_order": [selected_masks[index] for index in indices],
        "encoded_point_set_sha256": None,
        "effective_relation_matrix_columns": None,
    }


def main():
    if not __debug__:
        raise SystemExit("assertions must remain enabled")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("output already exists")
    config = json.loads(CONFIG.read_text())
    if sha256(ROUTE) != config["route_manifest_sha256"]:
        raise ValueError("route digest changed")
    if config["source_full_signed_columns"] < config[
        "selected_signed_columns_each"]:
        raise ValueError("source too small")
    if config["descendant_full_signed_columns"] != config[
        "selected_signed_columns_each"]:
        raise ValueError("descendant size mismatch")
    size = config["selected_signed_columns_each"]
    count = config["control_masks_each_geometry"]
    domain = config["control_mask_domain"]
    s_indices, s_attempts = control_indices(domain, "source", count, size)
    d_indices, d_attempts = control_indices(
        domain, "descendant_native", count, size)
    archive = W24 / "runs/w24-b2048-r1"
    source = scan(archive / "source-masks.bin.gz",
                  config["source_masks_gzip_sha256"],
                  config["source_masks_raw_sha256"],
                  config["source_full_signed_columns"], size, s_indices)
    descendant = scan(archive / "descendant-masks.bin.gz",
                      config["descendant_masks_gzip_sha256"],
                      config["descendant_masks_raw_sha256"],
                      config["descendant_full_signed_columns"], size, d_indices)
    assert source["selected_usable_points_B"] == descendant[
        "selected_usable_points_B"] == config["selected_usable_points_B_each"]
    assert source["first_excluded_mask"] is not None
    assert descendant["first_excluded_mask"] is None
    result = {
        "schema": "ecc2k130-263-equal-w24-base-selection-v1",
        "status": "exact_mask_selection_pending_point_map_replay",
        "proposal_id": config["proposal_id"],
        "candidate_id": None,
        "source_curve_id": config["source_curve_id"],
        "descendant_curve_id": config["descendant_curve_id"],
        "route_id": config["route_id"],
        "source": source,
        "descendant_native": descendant,
        "selection_attempts": {"source": s_attempts,
                               "descendant_native": d_attempts},
        "config_sha256": sha256(CONFIG),
        "route_manifest_sha256": sha256(ROUTE),
        "producer_sha256": sha256(Path(__file__)),
        "natural_pdp_yield": None,
        "verified_relation_rank": None,
        "verified_logarithm": None,
        "online_wall_time": None,
        "rho_ratio": None,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({name: {key: result[name][key] for key in (
        "selected_signed_columns", "selected_usable_points_B",
        "selected_mask_stream_sha256", "last_selected_mask")}
        for name in ("source", "descendant_native")}, indent=2))


if __name__ == "__main__":
    main()
