#!/usr/bin/env python3
"""Independent full-orbit replay of the exact N53 x-weight-four base."""

import hashlib
import itertools
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "ecc2k130/codegen"))
import field  # noqa: E402
import curves  # noqa: E402


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def main():
    frozen, run = load(HERE / "freeze.json"), load(HERE / "run.json")
    assert frozen["schema"] == "q20261010182800-freeze-v1"
    assert frozen["proposal_id"] == run["proposal_id"] == "Q20261010182800"
    assert frozen["candidate_id"] is frozen["run_id"] is None
    assert run["candidate_id"] is run["run_id"] is None
    assert frozen["isogeny"] == run["isogeny"] == "none"
    assert run["freeze_sha256"] == digest(HERE / "freeze.json")
    assert frozen["parent_run_sha256"] == digest(
        HERE.parent / "runs/n53_q1410_ordinary.json")
    assert frozen["parent_protocol_sha256"] == digest(
        HERE.parent / "q1410_balanced_s3_n53_protocol.json")
    assert frozen["field_source_sha256"] == digest(Path(field.__file__))
    assert frozen["curve_source_sha256"] == digest(Path(curves.__file__))
    for name, value in frozen["source_sha256"].items():
        assert value == digest(HERE / name)
    assert run["curve_id"] == frozen["curve_id"]
    assert run["workload_id"] == frozen["workload_id"] == "74f2979b3e68"
    assert frozen["cofactor"] * frozen["subgroup_order_r"] == (
        curves.curveOrder(53))
    onb, curve = field.Onb(53), curves.Curve(field.Onb(53))
    seen, keys = set(), set()
    counts = []
    for weight in range(1, 5):
        orbits = rational = identity = duplicate = 0
        for positions in itertools.combinations(range(53), weight):
            mask = sum(1 << i for i in positions)
            if mask in seen:
                continue
            x = onb.fromCoords(mask)
            cycle = []
            for _ in range(53):
                cycle.append(onb.toCoords(x))
                x = onb.sqr(x)
            assert x == onb.fromCoords(mask)
            assert len(set(cycle)) == 53
            seen.update(cycle)
            orbits += 1
            point = curve.pointFromX(onb.fromCoords(mask))
            if point is None:
                continue
            rational += 1
            other_lift = curve.neg(point)
            assert other_lift != point and other_lift[0] == point[0]
            subgroup = curve.mul(other_lift, frozen["cofactor"])
            if subgroup is None:
                identity += 1
                continue
            assert curve.mul(subgroup, frozen["subgroup_order_r"]) is None
            projected_x = subgroup[0]
            projected_cycle = []
            for _ in range(53):
                projected_cycle.append(onb.toCoords(projected_x))
                projected_x = onb.sqr(projected_x)
            assert len(set(projected_cycle)) == 53
            key = min(projected_cycle)
            if key in keys:
                duplicate += 1
            else:
                keys.add(key)
        assert orbits * 53 == math.comb(53, weight)
        row = run["rows"][weight - 1]
        assert row["weight"] == weight
        assert row["nominal_masks"] == math.comb(53, weight)
        assert row["orbit_representatives"] == orbits
        assert row["rational_orbits"] == rational
        assert row["identity_projected_orbits"] == identity
        assert row["duplicate_projected_columns"] == duplicate
        counts.append({"weight": weight, "orbits": orbits,
                       "rational": rational, "identity": identity,
                       "duplicate": duplicate})
        if weight in (3, 4):
            data = b"".join(value.to_bytes(7, "little")
                            for value in sorted(keys))
            path = HERE / f"n53_x_weight{weight}_columns.bin"
            assert data == path.read_bytes()
            assert digest(path) == row["enumerated_set_sha256"]
            assert row["cumulative_K"] == len(keys)
            assert row["cumulative_B"] == 106 * len(keys)
    assert run["actual_usable_points_B"] == 106 * len(keys)
    assert run["folded_columns_K"] == len(keys)
    assert run["enumerated_set_sha256"] == digest(
        HERE / "n53_x_weight4_columns.bin")
    assert run["elapsed_seconds_exploratory"] >= 0
    assert run["peak_process_rss_raw"] > 0
    output = HERE / "audit.json"
    assert not output.exists()
    output.write_text(json.dumps({"schema": "q20261010182800-audit-v1",
        "status": "PASS", "counts": counts,
        "freeze_sha256": digest(HERE / "freeze.json"),
        "run_sha256": digest(HERE / "run.json"),
        "auditor_sha256": digest(Path(__file__))},
        sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "B": run[
        "actual_usable_points_B"], "K": len(keys)}))


if __name__ == "__main__":
    main()
