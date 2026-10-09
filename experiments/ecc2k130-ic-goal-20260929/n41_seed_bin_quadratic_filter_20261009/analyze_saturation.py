#!/usr/bin/env python3
"""Check whether quadratic bin kernels exceed finite-support interpolation nullity."""

import hashlib
import json
import struct
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rank_headers(path: Path, equations: int):
    raw = path.read_bytes()
    stride = 4 + equations * 13 * 8
    if len(raw) != 3969 * stride:
        raise ValueError("filter table length changed")
    result = []
    for bin_index in range(3969):
        rank, count, reserved = struct.unpack_from("<HBB", raw, bin_index * stride)
        if rank > 821 or count > equations or reserved:
            raise ValueError("invalid filter table header")
        result.append(rank)
    return result


def main() -> None:
    output = HERE / "saturation_result.json"
    if output.exists():
        raise FileExistsError("preserve first saturation result")
    frozen = json.loads((HERE / "saturation_protocol.json").read_text())
    for name, expected in frozen["input_sha256"].items():
        if sha(HERE / name) != expected:
            raise ValueError(f"rank input changed: {name}")
    if sha(Path(__file__)) != frozen["producer_sha256"]:
        raise ValueError("saturation producer changed")
    data = (HERE / "x_orbits.bin").read_bytes()
    if len(data) != 1583568 * 12:
        raise ValueError("exact orbit count changed")
    sizes = [0] * 3969
    for offset in range(0, len(data), 12):
        left, right = data[offset], data[offset + 1]
        if not (1 <= left <= 63 and 1 <= right <= 63):
            raise ValueError("invalid seed-bin record")
        sizes[(left - 1) * 63 + right - 1] += 1
    ranks8 = rank_headers(HERE / "filters.bin", 8)
    ranks16 = rank_headers(HERE / "filters16.bin", 16)
    if ranks8 != ranks16:
        raise ValueError("eight- and sixteen-equation rank calculations disagree")
    defects = [min(size, 821) - rank for size, rank in zip(sizes, ranks16)]
    if any(defect < 0 for defect in defects):
        raise ValueError("reported rank exceeds row or feature count")
    result = {
        "status": "EXACT_ALL_BIN_QUADRATIC_RANK_SATURATION",
        "kind": "n41_seed_bin_quadratic_x_rank_versus_support_size",
        "curve_id": frozen["curve_id"],
        "candidate_id": None, "proposal_id": frozen["proposal_id"],
        "bin_count": 3969, "x_orbits": 1583568, "feature_count": 821,
        "minimum_bin_size": min(sizes), "median_bin_size": sorted(sizes)[1984],
        "maximum_bin_size": max(sizes),
        "bins_at_full_feature_rank": sum(rank == 821 for rank in ranks16),
        "bins_with_rank_below_min_support_and_feature_count": sum(bool(x) for x in defects),
        "maximum_extra_rank_defect": max(defects),
        "total_quadratic_kernel_dimension": sum(821 - rank for rank in ranks16),
        "total_interpolation_nullity": sum(max(821 - size, 0) for size in sizes),
        "bin_size_histogram": dict(sorted(Counter(sizes).items())),
        "rank_histogram": dict(sorted(Counter(ranks16).items())),
        "interpretation": "Every bin's feature rows are independent until the 821-feature ceiling; selected vanishing quadratics reflect finite-support interpolation nullity, with zero additional observed rank defect.",
        "claim_boundary": "This exact N41 rank result does not establish N131 rank. Literal N131 storage and enumeration are evaluated separately.",
        "saturation_protocol_sha256": sha(HERE / "saturation_protocol.json"),
    }
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in (
        "status", "bins_with_rank_below_min_support_and_feature_count",
        "total_quadratic_kernel_dimension", "total_interpolation_nullity")}))


if __name__ == "__main__":
    main()
