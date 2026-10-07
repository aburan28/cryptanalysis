#!/usr/bin/env python3
"""Enumerate exact Frobenius window-orbit factor bases on N53/N83."""

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
ROOT = PARENT.parents[1]
sys.path.insert(0, str(PARENT))
from enumerate_q1413_projected_x import canonical_rotation, projected_x  # noqa: E402
from run_probe import curves, field, sha  # noqa: E402

sys.path.insert(0, str(ROOT / "experiments/koblitz-pair-claw-20260929"))
from orbit_key import OrbitKey  # noqa: E402

PROTOCOL = HERE / "protocol.json"


def representatives(d: int):
    """Yield the unique long-zero-gap representative for each raw x orbit."""
    assert d >= 1
    yield 1, 1
    for span in range(2, d + 1):
        top = 1 << (span - 1)
        for interior in range(1 << (span - 2)):
            yield 1 | top | (interior << 1), span


def onb_x_from_cycle_mask(mask: int, onb, orbit):
    coords = 0
    while mask:
        bit = mask & -mask
        coords |= 1 << orbit.coordinate_cycle[bit.bit_length() - 1]
        mask ^= bit
    return onb.fromCoords(coords)


def pack_keys(keys: set[int], n: int) -> bytes:
    width = (n + 7) // 8
    return b"".join(key.to_bytes(width, "little") for key in sorted(keys))


def enumerate_base(n: int, protocol: dict) -> tuple[dict, bytes]:
    instance = protocol["instances"][str(n)]
    d = instance["nominal_window_dimension_d"]
    assert 2 * d < n
    assert instance["field"]["n"] == n
    assert instance["curve"]["curve_id"] == instance["curve_id"]
    assert curves.curveOrder(n) == (instance["cofactor"] *
                                   instance["subgroup_order"])

    onb = field.Onb(n)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    keys: set[int] = set()
    strata = {span: {"span": span, "raw_x_orbits": 0,
                     "rational_x_orbits": 0,
                     "identity_projection_orbits": 0,
                     "duplicate_projected_orbits": 0}
              for span in range(1, d + 1)}
    controls: list[dict] = []
    sampled = {(span, rational): 0 for span in range(1, d + 1)
               for rational in (False, True)}
    start = time.perf_counter()
    for cycle_mask, span in representatives(d):
        row = strata[span]
        row["raw_x_orbits"] += 1
        x = onb_x_from_cycle_mask(cycle_mask, onb, orbit)
        if n == 53:
            point = curve.pointFromX(x)
            rational = point is not None
            image = (curve.mul(point, instance["cofactor"])
                     if rational else None)
            projected = image[0] if image is not None else None
        else:
            rational, projected = projected_x(onb, x)
        key = None
        if rational:
            row["rational_x_orbits"] += 1
            if projected is None:
                row["identity_projection_orbits"] += 1
            else:
                key = canonical_rotation(orbit.cycle_bits(projected), n)
                if key in keys:
                    row["duplicate_projected_orbits"] += 1
                else:
                    keys.add(key)
        if sampled[(span, rational)] < 2:
            controls.append({"span": span, "raw_cycle_mask": cycle_mask,
                             "rational": rational,
                             "projected_orbit_key": key})
            sampled[(span, rational)] += 1
    elapsed = time.perf_counter() - start
    assert len(keys) == sum(row["rational_x_orbits"] -
                            row["identity_projection_orbits"] -
                            row["duplicate_projected_orbits"]
                            for row in strata.values())
    assert sum(row["raw_x_orbits"] for row in strata.values()) == 1 << (d - 1)
    assert all(row["raw_x_orbits"] ==
               (1 if span == 1 else 1 << (span - 2))
               for span, row in strata.items())
    assert all(key != 0 and key != (1 << n) - 1 for key in keys)
    packed = pack_keys(keys, n)
    assert len(packed) == len(keys) * ((n + 7) // 8)
    digest = hashlib.sha256(packed).hexdigest()
    geometric_points = 2 * n * sum(
        row["rational_x_orbits"] for row in strata.values())
    receipt = {
        "kind": "q1481_exact_cofactor_projected_window_orbit_base",
        "proposal_id": "Q1481", "candidate_id": None,
        "workload_id": None, "run_id": None,
        "curve_id": instance["curve_id"], "isogeny": "none",
        "field_degree_n": n, "cofactor": instance["cofactor"],
        "nominal_window_dimension_d": d,
        "nominal_raw_x_orbits": 1 << (d - 1),
        "nominal_raw_x_masks": n * (1 << (d - 1)),
        "geometric_rational_point_count_before_projection": geometric_points,
        "actual_usable_points_B_before_folding": 2 * n * len(keys),
        "signed_frobenius_columns_K": len(keys),
        "enumerated_set_encoding": (
            "Sorted canonical cyclic-Frobenius projected x keys as "
            f"{(n + 7) // 8}-byte little-endian integers; expand each "
            "key to both signs and all Frobenius powers"),
        "enumerated_set_sha256": digest,
        "packed_projected_key_file_sha256": digest,
        "packed_projected_key_file_bytes": len(packed),
        "strata": list(strata.values()),
        "independent_group_control_inputs": controls,
        "enumeration_wall_seconds_exploratory": elapsed,
        "peak_rss_raw": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "peak_rss_units": "bytes on Darwin, KiB on Linux",
        "design_sha256": sha(HERE / "design_protocol.json"),
        "protocol_sha256": sha(PROTOCOL),
        "source_sha256": sha(Path(__file__)),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "is_empirical_relation_yield": False,
        "complete_solve_work_log2": None,
    }
    return receipt, packed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--degree", type=int, choices=(53, 83), required=True)
    args = parser.parse_args()
    n = args.degree
    protocol = json.loads(PROTOCOL.read_text())
    instance = protocol["instances"][str(n)]
    d = instance["nominal_window_dimension_d"]
    receipt_path = HERE / f"n{n}_d{d}_base.json"
    packed_path = HERE / f"n{n}_d{d}_projected_keys.bin"
    assert not receipt_path.exists() and not packed_path.exists(), (
        "refuse to overwrite frozen base artifacts")
    assert protocol["proposal_id"] == "Q1481"
    assert protocol["candidate_id"] is None and protocol["isogeny"] == "none"
    assert protocol["design_sha256"] == sha(HERE / "design_protocol.json")
    assert protocol["source_sha256"]["enumerate_base.py"] == sha(Path(__file__))
    assert protocol["runtime_info_sha256"] == sha(HERE / "sage_runtime_info.json")
    assert json.loads((HERE / "sage_runtime_info.json").read_text())[
        "status"] == "verified"
    for relative, digest in protocol["dependency_sha256"].items():
        assert sha(ROOT / relative) == digest
    for relative, digest in protocol["reference_sha256"].items():
        assert sha(ROOT / relative) == digest
    assert instance["curve_id"] == protocol["design_instances"][str(n)][
        "curve_id"]
    receipt, packed = enumerate_base(n, protocol)
    packed_path.write_bytes(packed)
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"n": n, "d": d,
                      "B": receipt["actual_usable_points_B_before_folding"],
                      "K": receipt["signed_frobenius_columns_K"],
                      "seconds": receipt[
                          "enumeration_wall_seconds_exploratory"]}),
          flush=True)


if __name__ == "__main__":
    main()
