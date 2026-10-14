#!/usr/bin/env python3
"""Exact best two-coset union from the frozen width-12 shift census."""

import hashlib
import json
import time
from pathlib import Path

from screen import CODEGEN, PAIR, ROOT, exact_keys, sha  # noqa: F401
from curves import Curve
from field import Onb
from orbit_key import OrbitKey

HERE = Path(__file__).resolve().parent


def main():
    output = HERE / "union.json"
    key_path = HERE / "union_keys.bin"
    assert not output.exists() and not key_path.exists(), "refusing to overwrite evidence"
    protocol_path = HERE / "union_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    screen_path = HERE / "screen.json"
    screen = json.loads(screen_path.read_text())
    assert protocol["screen_sha256"] == sha(screen_path)
    assert protocol["source_sha256"] == sha(Path(__file__))
    assert protocol["screen_source_sha256"] == sha(HERE / "screen.py")
    rows = sorted(screen["rows"], key=lambda row: (-row["valid_lifts"], row["shift_coordinates"]))
    assert [row["shift_coordinates"] for row in rows[:2]] == [[37, 73], [12, 51]]
    assert [row["valid_lifts"] for row in rows[:2]] == [2196, 2156]
    onb = Onb(83)
    curve = Curve(onb)
    orbit = OrbitKey(onb)
    started = time.perf_counter_ns()
    cache = {}

    def full_scan(index):
        if index in cache:
            return cache[index]
        row = rows[index]
        bits = row["shift_coordinates"]
        geometry, keys = exact_keys((1 << bits[0]) ^ (1 << bits[1]), onb, curve, orbit)
        assert geometry["valid_lifts"] == row["valid_lifts"]
        assert geometry["K"] == len(keys)
        cache[index] = ({"shift_coordinates": bits, **geometry}, keys)
        return cache[index]

    best = 0
    best_pair = None
    best_union = set()
    best_intersection = 0
    evaluated_pairs = 0
    for i, left in enumerate(rows[:-1]):
        if left["valid_lifts"] + rows[i + 1]["valid_lifts"] <= best:
            break
        left_geometry, left_keys = full_scan(i)
        for j in range(i + 1, len(rows)):
            right = rows[j]
            if left["valid_lifts"] + right["valid_lifts"] <= best:
                break
            right_geometry, right_keys = full_scan(j)
            if left_geometry["K"] + right_geometry["K"] <= best:
                continue
            evaluated_pairs += 1
            intersection = left_keys & right_keys
            union = left_keys | right_keys
            if len(union) > best:
                best = len(union)
                best_pair = [i, j]
                best_union = union
                best_intersection = len(intersection)
    assert best_pair is not None
    assert best == len(best_union)
    assert best <= rows[0]["valid_lifts"] + rows[1]["valid_lifts"]
    blob = b"".join(key.to_bytes(21, "little") for key in sorted(best_union))
    key_path.write_bytes(blob)
    report = {
        "kind": "n83_width12_two_coset_union_optimum_v1",
        "status": "complete_geometry",
        "protocol_sha256": sha(protocol_path),
        "source_sha256": sha(Path(__file__)),
        "screen_sha256": sha(screen_path),
        "components": [cache[index][0] for index in best_pair],
        "intersection_K": best_intersection,
        "best_K": best,
        "best_B": 166 * best,
        "upper_bound_K_all_pairs": sum(row["valid_lifts"] for row in rows[:2]),
        "full_scanned_offsets": len(cache),
        "evaluated_pairs": evaluated_pairs,
        "all_pair_optimum_certified": True,
        "key_file": key_path.name,
        "key_sha256": hashlib.sha256(blob).hexdigest(),
        "geometry_wall_ns_exploratory": time.perf_counter_ns() - started,
        "candidate_id": None,
        "ordinary_query_relation_yield": None,
        "novel_rank_per_query": None,
        "one_target_online_ms": None
    }
    output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "K": report["best_K"],
                      "B": report["best_B"], "intersection_K": best_intersection,
                      "full_scanned_offsets": len(cache),
                      "evaluated_pairs": evaluated_pairs}), flush=True)


if __name__ == "__main__":
    main()
