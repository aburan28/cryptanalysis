#!/usr/bin/env python3
"""Directly enumerate one N53 cyclic window as an incidence control."""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))

from q1481_window_orbit_base.enumerate_base import OrbitKey  # noqa: E402
from run_probe import curves, field  # noqa: E402

DESIGN = HERE / "design_protocol.json"
PROTOCOL = HERE / "protocol.json"
OUT = HERE / "n53_direct_window_control.json"
Q1481 = PARENT / "q1481_window_orbit_base"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def direct_counts() -> dict:
    n, d = 53, 14
    base_protocol = json.loads((Q1481 / "protocol.json").read_text())
    instance = base_protocol["instances"][str(n)]
    assert instance["nominal_window_dimension_d"] == d
    assert instance["cofactor"] == 428
    onb = field.Onb(n)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    assert len(orbit.coordinate_cycle) == n
    rational = 0
    point_keys: set[tuple[int, int]] = set()
    for local_mask in range(1, 1 << d):
        coordinates = sum(1 << orbit.coordinate_cycle[j]
                          for j in range(d) if (local_mask >> j) & 1)
        point = curve.pointFromX(onb.fromCoords(coordinates))
        if point is None:
            continue
        rational += 1
        projected = curve.mul(point, instance["cofactor"])
        assert projected is not None
        assert curve.mul(projected, instance["subgroup_order"]) is None
        negative = curve.neg(projected)
        assert negative != projected
        for item in (projected, negative):
            key = (int(item[0]), int(item[1]))
            assert key not in point_keys
            point_keys.add(key)
    assert len(point_keys) == 2 * rational
    digest = hashlib.sha256()
    for x, y in sorted(point_keys):
        digest.update(x.to_bytes(7, "little"))
        digest.update(y.to_bytes(7, "little"))
    return {
        "field_degree_n": n,
        "window_dimension_d": d,
        "curve_id": instance["curve_id"],
        "cofactor": instance["cofactor"],
        "raw_nonzero_x_tested": (1 << d) - 1,
        "direct_rational_x_count": rational,
        "direct_usable_point_count": len(point_keys),
        "direct_projected_point_set_sha256": digest.hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    design = json.loads(DESIGN.read_text())
    protocol = json.loads(PROTOCOL.read_text())
    assert design["proposal_id"] == protocol["proposal_id"] == "Q1495"
    assert protocol["design_sha256"] == sha(DESIGN)
    assert protocol["n53_control_source_sha256"] == sha(Path(__file__))
    assert protocol["input_sha256"]["q1481_protocol"] == sha(
        Q1481 / "protocol.json")
    assert protocol["input_sha256"]["q1481_n53_receipt"] == sha(
        Q1481 / "n53_d14_base.json")
    started = time.perf_counter_ns()
    direct = direct_counts()
    wall_ns = time.perf_counter_ns() - started
    receipt = json.loads((Q1481 / "n53_d14_base.json").read_text())
    predicted_rational = sum(row["rational_x_orbits"] *
                             (14 - row["span"] + 1) for row in receipt[
                                 "strata"])
    assert direct["direct_rational_x_count"] == predicted_rational
    assert direct["direct_usable_point_count"] == 2 * predicted_rational
    if args.check:
        archived = json.loads(OUT.read_text())
        assert archived["status"] == "PASS"
        assert archived["source_sha256"] == sha(Path(__file__))
        assert archived["protocol_sha256"] == sha(PROTOCOL)
        assert archived["input_sha256"] == protocol["input_sha256"]
        for key, value in direct.items():
            assert archived[key] == value, key
        print("Q1495 N53 direct fixed-window control PASS (recomputed)")
    else:
        assert not OUT.exists(), "refusing to replace N53 control"
        result = {
            **direct,
            "kind": "q1495_n53_direct_fixed_window_control",
            "proposal_id": "Q1495", "candidate_id": None,
            "run_id": None, "isogeny": "none", "status": "PASS",
            "predicted_rational_x_from_strata": predicted_rational,
            "wall_ns_exploratory": wall_ns,
            "peak_rss_raw": resource.getrusage(
                resource.RUSAGE_SELF).ru_maxrss,
            "peak_rss_units": "bytes on Darwin, KiB on Linux",
            "source_sha256": sha(Path(__file__)),
            "design_sha256": sha(DESIGN),
            "protocol_sha256": sha(PROTOCOL),
            "input_sha256": protocol["input_sha256"],
        }
        OUT.write_text(json.dumps(result, indent=2,
                                  sort_keys=True) + "\n")
        print("Q1495 N53 direct fixed-window control written")


if __name__ == "__main__":
    main()
