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
    components = []
    key_sets = []
    for row in rows[:2]:
        bits = row["shift_coordinates"]
        geometry, keys = exact_keys((1 << bits[0]) ^ (1 << bits[1]), onb, curve, orbit)
        assert geometry["valid_lifts"] == row["valid_lifts"]
        assert geometry["identity_projections"] == 0
        assert geometry["duplicate_orbit_seeds"] == 0
        components.append({"shift_coordinates": bits, **geometry})
        key_sets.append(keys)
    intersection = key_sets[0] & key_sets[1]
    union = key_sets[0] | key_sets[1]
    assert not intersection
    assert len(union) == 4352 == sum(row["valid_lifts"] for row in rows[:2])
    blob = b"".join(key.to_bytes(21, "little") for key in sorted(union))
    key_path.write_bytes(blob)
    report = {
        "kind": "n83_width12_two_coset_union_optimum_v1",
        "status": "complete_geometry",
        "protocol_sha256": sha(protocol_path),
        "source_sha256": sha(Path(__file__)),
        "screen_sha256": sha(screen_path),
        "components": components,
        "intersection_K": len(intersection),
        "best_K": len(union),
        "best_B": 166 * len(union),
        "upper_bound_K_all_pairs": sum(row["valid_lifts"] for row in rows[:2]),
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
                      "B": report["best_B"], "intersection_K": 0}), flush=True)


if __name__ == "__main__":
    main()
