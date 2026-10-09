#!/usr/bin/env python3
"""Check whether public-target residual coordinates add any rank."""

import hashlib
import json
import random
import time
from pathlib import Path

from combined_coordinate_rank import feature_vector, insert_low
from produce import Curve, Field, pair_states

HERE = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    frozen = json.loads((HERE / "public_span_protocol.json").read_text())
    for name, expected in frozen["input_sha256"].items():
        if digest(HERE / name) != expected:
            raise ValueError(f"public-span input changed: {name}")
    if digest(Path(__file__)) != frozen["source_sha256"]:
        raise ValueError("public-span source changed after freeze")
    output = HERE / "public_coordinate_span.json"
    if output.exists():
        raise FileExistsError("preserve first public coordinate-span result")
    original = json.loads((HERE / "protocol.json").read_text())
    public = json.loads((HERE / "public_probe_protocol.json").read_text())
    data = (HERE / "rows.bin").read_bytes()
    if len(data) != 80000 * 18:
        raise ValueError("training rows changed")
    start = time.monotonic_ns()
    basis = {}
    for offset in range(0, len(data), 18):
        x = int.from_bytes(data[offset + 2:offset + 8], "little")
        y = int.from_bytes(data[offset + 8:offset + 14], "little")
        insert_low(basis, feature_vector(x, y))
    pair_rank = len(basis)
    curve = Curve(Field(41, [0, 3]), 0)
    geometry = json.loads(Path(original["inputs"]["geometry"]).read_text())["n41"]
    domains = [pair_states(curve, geometry["point_rows_by_unique_rotation"][str(r)])
               for r in public["prefix_rotations"]]
    target = tuple(original["public_target_q"])
    rng = random.Random(public["random_seed"])
    seen = set()
    draws = overlap_rejects = processed = novel = 0
    status = "RUNNING"
    while processed < public["residual_count"]:
        if draws >= public["max_draws"]:
            status = "DRAW_CAP"
            break
        i, j = rng.randrange(1956), rng.randrange(1956)
        draws += 1
        if (i, j) in seen:
            continue
        seen.add((i, j))
        left, right = domains[0][i], domains[1][j]
        if left[2] & right[2]:
            overlap_rejects += 1
            continue
        prefix = curve.add(left[1], right[1])
        if prefix is None:
            raise ValueError("admissible prefix is identity")
        residual = curve.add(target, curve.neg(prefix))
        if residual is None:
            raise ValueError("public residual is identity")
        novel += insert_low(basis, feature_vector(*residual))
        processed += 1
        if processed % 128 == 0 and (time.monotonic_ns() - start) / 1e9 >= frozen["limits"]["wall_seconds"]:
            status = "TIME_CAP"
            break
    else:
        status = "COMPLETE_PUBLIC_SPAN"
    prior = json.loads((HERE / "public_residual_probe.json").read_text())
    if status == "COMPLETE_PUBLIC_SPAN" and (draws != prior["draws"] or
            overlap_rejects != prior["cross_column_rejects"]):
        raise ValueError("public prefix ordering changed")
    result = {"status": status, "curve_id": original["curve_id"],
              "proposal_id": original["proposal_id"], "candidate_id": None,
              "public_target_q": original["public_target_q"],
              "pair_training_rows": 80000, "pair_coordinate_rank_low_pivot": pair_rank,
              "public_residuals_processed": processed,
              "draws": draws, "cross_column_rejects": overlap_rejects,
              "novel_rank_from_public_residuals": novel,
              "combined_coordinate_rank": len(basis),
              "source_sha256": digest(Path(__file__)),
              "protocol_sha256": digest(HERE / "public_span_protocol.json"),
              "wall_ns": time.monotonic_ns() - start}
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": status, "public_residuals": processed,
                      "novel_rank": novel, "combined_rank": len(basis),
                      "wall_s": result["wall_ns"] / 1e9}))


if __name__ == "__main__":
    main()
