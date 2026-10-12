#!/usr/bin/env python3
"""Lift the matched n53 projected relation to four low-weight raw leaves."""

import itertools
import json
import time
from pathlib import Path

from chain_s3 import evaluate_s3
from run_probe import HERE, curves, field, sha


def main():
    relation_path = HERE / "runs/n53_ordinary_matched_pair_table.json"
    preimage_path = HERE / "runs/n53_ordinary_raw_preimages.json"
    output = HERE / "runs/n53_ordinary_raw_pair_witness.json"
    assert not output.exists()
    relation = json.loads(relation_path.read_text())
    preimages = json.loads(preimage_path.read_text())
    assert relation["status"] == "verified_four_point_relation"
    assert preimages["raw_target_preimage_count"] == 428
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    wanted = [tuple(point) for point in relation["ordinary_query"][
        "relation"]["points"]]
    wanted_set = set(wanted)
    raw_for_projected = {}
    began = time.perf_counter()
    for weight in (1, 2, 3):
        for positions in itertools.combinations(range(53), weight):
            x = onb.fromCoords(sum(1 << index for index in positions))
            point = curve.pointFromX(x)
            if point is None:
                continue
            projected = curve.mul(point, 428)
            if projected is None:
                continue
            for raw, public in ((point, projected),
                                (curve.neg(point), curve.neg(projected))):
                if public in wanted_set:
                    raw_for_projected.setdefault(public, raw)
        if len(raw_for_projected) == len(wanted_set):
            break
    assert len(raw_for_projected) == len(wanted_set)
    leaves = [raw_for_projected[point] for point in wanted]
    first = curve.add(leaves[0], leaves[1])
    second = curve.add(first, leaves[2])
    total = curve.add(second, leaves[3])
    assert first is not None and second is not None and total is not None
    assert curve.mul(total, 428) == tuple(int(v) for v in relation["target"])
    preimage_points = {tuple(int(v) for v in point)
                       for point in preimages["raw_target_points"]}
    assert total in preimage_points
    assert all(evaluate_s3(onb, *triple) == 0 for triple in (
        (leaves[0][0], leaves[1][0], first[0]),
        (first[0], leaves[2][0], second[0]),
        (second[0], leaves[3][0], total[0])))
    report = {
        "kind": "n53_ordinary_projected_relation_raw_low_weight_witness",
        "proposal_id": "Q1306",
        "candidate_id": None,
        "workload_id": relation["workload_id"],
        "curve_id": relation["curve_id"],
        "isogeny": "none",
        "raw_leaf_points": [[str(v) for v in point] for point in leaves],
        "raw_leaf_x_weights": [onb.toCoords(point[0]).bit_count()
                               for point in leaves],
        "intermediate_x_coordinates": [onb.toCoords(first[0]),
                                       onb.toCoords(second[0])],
        "raw_target": [str(v) for v in total],
        "raw_target_x_coordinates": onb.toCoords(total[0]),
        "public_target": relation["target"],
        "all_three_s3_links_verified": True,
        "elapsed_seconds": time.perf_counter() - began,
        "projected_relation_receipt_sha256": sha(relation_path),
        "preimage_coset_sha256": sha(preimage_path),
        "source_sha256": sha(Path(__file__)),
        "field_source_sha256": sha(Path(field.__file__)),
        "curve_source_sha256": sha(Path(curves.__file__)),
    }
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"raw_target_x": report["raw_target_x_coordinates"],
                      "raw_leaf_x_weights": report["raw_leaf_x_weights"],
                      "elapsed_seconds": report["elapsed_seconds"]}))


if __name__ == "__main__":
    main()
