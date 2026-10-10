#!/usr/bin/env python3
"""Postrun exact six-rotation factor-base count from frozen source rows."""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
SOURCE = GOAL / "n41_w8_fixed_sum_backward_20261009"
sys.path.insert(0, str(SOURCE))
import geometry as source_geometry


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    output = HERE / "base_count_audit.json"
    if output.exists():
        raise FileExistsError("preserve first base-count audit")
    geometry_path = SOURCE / "geometry.json"
    input_path = GOAL / "n41_lowpower_w8_s6/native_input.txt"
    geometry = json.loads(geometry_path.read_text())
    active = set(geometry["permitted_canonical_a"])
    active |= {code ^ 56 for code in geometry["permitted_canonical_a"]}
    lines = input_path.read_text().splitlines()
    count = int(lines[1])
    rows = [tuple(map(int, line.split())) for line in lines[2:2+count]]
    field = source_geometry.source.Field(41, [0, 3])
    points = set()
    by_rotation = []
    for rotation in geometry["rotations"][:6]:
        current = {source_geometry.point_frob(field, (x, y), rotation)
                   for x, y, column, mask, branch, sign in rows
                   if mask in active and branch == 0}
        by_rotation.append(len(current))
        points.update(current)
    if (len(active) != 80 or by_rotation != [160]*6 or
            len(points) != 960):
        raise ValueError("six-block actual factor-base count changed")
    result = {"status": "PASS_EXACT_SIX_BLOCK_BASE_COUNT",
              "curve_id": geometry["curve_id"],
              "active_masks_per_rotation": len(active),
              "usable_points_per_rotation": by_rotation,
              "distinct_usable_subgroup_points_B": len(points),
              "folded_columns_K": geometry["folded_columns_K"],
              "source_sha256": {str(path): sha(path) for path in
                                (geometry_path, input_path,
                                 SOURCE / "geometry.py", Path(__file__))}}
    output.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print(json.dumps({key: result[key] for key in
                      ("status", "distinct_usable_subgroup_points_B",
                       "folded_columns_K")}, sort_keys=True))


if __name__ == "__main__":
    main()
