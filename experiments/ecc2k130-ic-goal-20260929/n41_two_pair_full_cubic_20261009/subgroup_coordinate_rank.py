#!/usr/bin/env python3
"""Compare two-pair coordinate relations with random N41 subgroup points."""

import hashlib
import json
import random
import time
from pathlib import Path

from produce import Curve, Field

HERE = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def vector(point: tuple[int, int]) -> int:
    x, y = point
    if x & 1:
        raise ValueError("prime-subgroup point left trace-zero x encoding")
    active = [bit for bit in range(40) if (x >> (bit + 1)) & 1]
    active.extend(40 + bit for bit in range(41) if (y >> bit) & 1)
    value = 1
    for a in active:
        value |= 1 << (1 + a)
    for pos, a in enumerate(active):
        base = 1 + 81 + a * (2 * 81 - a - 1) // 2
        for b in active[pos + 1:]:
            value |= 1 << (base + b - a - 1)
    return value


def main() -> None:
    frozen = json.loads((HERE / "subgroup_protocol.json").read_text())
    for name, expected in frozen["input_sha256"].items():
        if digest(HERE / name) != expected:
            raise ValueError(f"subgroup input changed: {name}")
    if digest(Path(__file__)) != frozen["source_sha256"]:
        raise ValueError("subgroup rank source changed after freeze")
    output = HERE / "subgroup_coordinate_rank.json"
    if output.exists():
        raise FileExistsError("preserve first random-subgroup rank")
    original = json.loads((HERE / "protocol.json").read_text())
    curve = Curve(Field(41, [0, 3]), 0)
    target = tuple(original["public_target_q"])
    order = original["subgroup_order"]
    if not curve.on_curve(target) or curve.mul(order, target) is not None:
        raise ValueError("public subgroup point changed")
    rng = random.Random(frozen["random_seed"])
    basis = {}
    rank_progress = []
    start = time.monotonic_ns()
    for count in range(1, frozen["point_count"] + 1):
        point = curve.mul(rng.randrange(1, order), target)
        value = vector(point)
        while value:
            pivot = value.bit_length() - 1
            prior = basis.get(pivot)
            if prior is None:
                basis[pivot] = value
                break
            value ^= prior
        if count in frozen["milestones"]:
            rank_progress.append({"points": count, "rank": len(basis)})
        if (time.monotonic_ns() - start) / 1e9 >= frozen["limits"]["wall_seconds"]:
            status = "TIME_CAP"
            break
    else:
        status = "POINT_CAP_REACHED"
    result = {"status": status, "curve_id": original["curve_id"],
              "proposal_id": original["proposal_id"], "candidate_id": None,
              "public_target_q": original["public_target_q"],
              "points_sampled": count,
              "coordinate_features": 3322,
              "subgroup_coordinate_rank": len(basis),
              "two_pair_coordinate_rank": json.loads((HERE / "rank.json").read_text())["coordinate_rank"],
              "milestones": rank_progress,
              "pivot_set_sha256": hashlib.sha256(
                  ",".join(map(str, sorted(basis))).encode()).hexdigest(),
              "source_sha256": digest(Path(__file__)),
              "protocol_sha256": digest(HERE / "subgroup_protocol.json"),
              "wall_ns": time.monotonic_ns() - start}
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": status, "points": count,
                      "rank": len(basis), "wall_s": result["wall_ns"] / 1e9}))


if __name__ == "__main__":
    main()
