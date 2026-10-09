#!/usr/bin/env python3
"""Independent low-pivot rank of pair-sum and random-subgroup coordinates."""

import hashlib
import json
import random
import time
from pathlib import Path

from produce import Curve, Field

HERE = Path(__file__).resolve().parent
COORDS = 81


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def feature_vector(x: int, y: int) -> int:
    if x & 1 or (x >> 41) or (y >> 41):
        raise ValueError("coordinate encoding changed")
    active = [bit for bit in range(40) if (x >> (bit + 1)) & 1]
    active.extend(40 + bit for bit in range(41) if (y >> bit) & 1)
    row = 1
    for bit in active:
        row |= 1 << (1 + bit)
    for position, a in enumerate(active):
        for b in active[position + 1:]:
            index = 1 + COORDS + a * (2 * COORDS - a - 1) // 2 + b - a - 1
            row |= 1 << index
    return row


def insert_low(basis: dict[int, int], row: int) -> bool:
    while row:
        pivot = (row & -row).bit_length() - 1
        prior = basis.get(pivot)
        if prior is None:
            basis[pivot] = row
            return True
        row ^= prior
    return False


def main() -> None:
    frozen = json.loads((HERE / "combined_protocol.json").read_text())
    for name, expected in frozen["input_sha256"].items():
        if digest(HERE / name) != expected:
            raise ValueError(f"combined-rank input changed: {name}")
    if digest(Path(__file__)) != frozen["source_sha256"]:
        raise ValueError("combined-rank source changed after freeze")
    output = HERE / "combined_coordinate_rank.json"
    if output.exists():
        raise FileExistsError("preserve first combined rank")
    original = json.loads((HERE / "protocol.json").read_text())
    group_policy = json.loads((HERE / "subgroup_protocol.json").read_text())
    data = (HERE / "rows.bin").read_bytes()
    if len(data) != 18 * original["row_count"]:
        raise ValueError("two-pair row count changed")
    start = time.monotonic_ns()
    basis = {}
    pair_seen = 0
    status = "RUNNING"
    for offset in range(0, len(data), 18):
        x = int.from_bytes(data[offset + 2:offset + 8], "little")
        y = int.from_bytes(data[offset + 8:offset + 14], "little")
        insert_low(basis, feature_vector(x, y))
        pair_seen += 1
        if pair_seen % 512 == 0 and (time.monotonic_ns() - start) / 1e9 > frozen["limits"]["wall_seconds"]:
            status = "TIME_CAP_PAIR_ROWS"
            break
    pair_rank = len(basis)
    subgroup_seen = 0
    novel = 0
    if status == "RUNNING":
        curve = Curve(Field(41, [0, 3]), 0)
        target = tuple(original["public_target_q"])
        if not curve.on_curve(target) or curve.mul(original["subgroup_order"], target) is not None:
            raise ValueError("public target subgroup check changed")
        rng = random.Random(group_policy["random_seed"])
        for subgroup_seen in range(1, group_policy["point_count"] + 1):
            scalar = rng.randrange(1, original["subgroup_order"])
            novel += insert_low(basis, feature_vector(*curve.mul(scalar, target)))
            if subgroup_seen % 128 == 0 and (time.monotonic_ns() - start) / 1e9 > frozen["limits"]["wall_seconds"]:
                status = "TIME_CAP_SUBGROUP_ROWS"
                break
        else:
            status = "COMPLETE_COMBINED_RANK"
    result = {"status": status, "curve_id": original["curve_id"],
              "proposal_id": original["proposal_id"], "candidate_id": None,
              "coordinate_feature_count": 3322,
              "pair_rows_processed": pair_seen, "pair_rank_low_pivot": pair_rank,
              "subgroup_rows_processed": subgroup_seen,
              "novel_rank_from_subgroup": novel,
              "combined_rank_low_pivot": len(basis),
              "m4ri_pair_coordinate_rank": json.loads((HERE / "rank.json").read_text())["coordinate_rank"],
              "subgroup_only_rank_high_pivot": json.loads((HERE / "subgroup_coordinate_rank.json").read_text())["subgroup_coordinate_rank"],
              "pivot_set_sha256": hashlib.sha256(
                  ",".join(map(str, sorted(basis))).encode()).hexdigest(),
              "source_sha256": digest(Path(__file__)),
              "protocol_sha256": digest(HERE / "combined_protocol.json"),
              "wall_ns": time.monotonic_ns() - start}
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": status, "pair_rank": pair_rank,
                      "novel_subgroup_rank": novel,
                      "combined_rank": len(basis), "wall_s": result["wall_ns"] / 1e9}))


if __name__ == "__main__":
    main()
