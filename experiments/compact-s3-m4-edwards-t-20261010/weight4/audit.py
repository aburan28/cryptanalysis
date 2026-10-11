#!/usr/bin/env python3
"""Replay t-weight-four geometry using the other x lift and field Frobenius."""

import hashlib
import itertools
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(PARENT), str(ROOT / "ecc2k130/codegen")]
import field  # noqa: E402
import curves  # noqa: E402
from t_link import t_of_x, x_roots_of_t  # noqa: E402


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def audit(frozen, saved):
    f = field.Onb(53)
    e = curves.Curve(f)
    seen = set()
    keys = set()
    counts = []
    for weight in range(1, 5):
        row = {"nominal_masks": 0, "orbit_representatives": 0,
               "quadratic_solvable_orbits": 0, "rational_orbits": 0,
               "identity_projected_orbits": 0,
               "duplicate_projected_columns": 0}
        for positions in itertools.combinations(range(53), weight):
            mask = sum(1 << i for i in positions)
            row["nominal_masks"] += 1
            if mask in seen:
                continue
            value = f.fromCoords(mask)
            current = value
            orbit = []
            for _ in range(53):
                orbit.append(f.toCoords(current))
                current = f.sqr(current)
            assert current == value and len(set(orbit)) == 53
            seen.update(orbit)
            row["orbit_representatives"] += 1
            roots = x_roots_of_t(f, e, value)
            if not roots:
                continue
            assert len(roots) == 2
            assert all(t_of_x(f, x) == value for x in roots)
            row["quadratic_solvable_orbits"] += 1
            point = e.pointFromX(roots[1])
            if point is None:
                assert e.pointFromX(roots[0]) is None
                continue
            row["rational_orbits"] += 1
            projected = e.mul(point, frozen["cofactor"])
            if projected is None:
                row["identity_projected_orbits"] += 1
                continue
            x = projected[0]
            cycle = []
            for _ in range(53):
                cycle.append(f.toCoords(x))
                x = f.sqr(x)
            assert x == projected[0] and len(set(cycle)) == 53
            key = min(cycle)
            if key in keys:
                row["duplicate_projected_columns"] += 1
            else:
                keys.add(key)
        assert row["nominal_masks"] == math.comb(53, weight)
        assert row["orbit_representatives"] * 53 == row["nominal_masks"]
        counts.append(row)
        if weight in (3, 4):
            recorded = saved[weight-3]
            assert recorded["weight_bound"] == weight
            assert recorded["counts_by_weight"] == counts
            packed = b"".join(value.to_bytes(7, "little")
                              for value in sorted(keys))
            path = HERE / "bases" / f"n53_t_weight{weight}_columns.bin"
            assert path.read_bytes() == packed
            assert digest(path) == recorded["enumerated_set_sha256"]
            assert recorded["enumerated_set_bytes"] == len(packed)
            assert recorded["nominal_t_masks"] == sum(math.comb(53,w)
                                                       for w in range(1,weight+1))
            assert recorded["folded_columns_K"] == len(keys)
            assert recorded["actual_usable_points_B"] == 106*len(keys)
            assert recorded["elapsed_seconds_exploratory"] >= 0
    return {"w3_B": saved[0]["actual_usable_points_B"],
            "w3_K": saved[0]["folded_columns_K"],
            "w4_B": saved[1]["actual_usable_points_B"],
            "w4_K": saved[1]["folded_columns_K"]}


def main():
    frozen = load(HERE / "freeze.json")
    assert frozen["schema"] == "q20261010174100-freeze-v1"
    assert frozen["proposal_id"] == "Q20261010174100"
    assert frozen["candidate_id"] is frozen["run_id"] is None
    assert frozen["isogeny"] == "none"
    assert frozen["q1419_protocol_sha256"] == digest(
        ROOT / "experiments/compact-s3-m4-20261003/q1419_partial_pin/protocol.json")
    assert frozen["parent_run_sha256"] == digest(PARENT / "run.json")
    assert frozen["parent_w3_digest"] == digest(
        PARENT / "bases/n53_t_weight3_columns.bin")
    assert frozen["t_link_source_sha256"] == digest(PARENT / "t_link.py")
    for name, value in frozen["source_sha256"].items():
        assert digest(HERE / name) == value
    result = load(HERE / "run.json")
    assert result["proposal_id"] == frozen["proposal_id"]
    assert result["candidate_id"] is result["run_id"] is None
    assert result["isogeny"] == "none"
    assert result["curve_id"] == frozen["curve_id"]
    assert result["freeze_sha256"] == digest(HERE / "freeze.json")
    geometry = audit(frozen, result["rows"])
    assert geometry["w3_B"] == frozen["parent_w3_B"]
    assert geometry["w3_K"] == frozen["parent_w3_K"]
    assert result["rows"][0]["enumerated_set_sha256"] == frozen[
        "parent_w3_digest"]
    output = HERE / "audit.json"
    assert not output.exists()
    output.write_text(json.dumps({"schema": "q20261010174100-audit-v1",
        "status": "PASS", "geometry": geometry,
        "freeze_sha256": digest(HERE / "freeze.json"),
        "run_sha256": digest(HERE / "run.json"),
        "auditor_sha256": digest(Path(__file__))},
        sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": "PASS", **geometry}))


if __name__ == "__main__":
    main()
