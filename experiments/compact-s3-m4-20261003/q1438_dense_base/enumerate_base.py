#!/usr/bin/env python3
"""Enumerate exact cofactor-projected W<=4 N53 and W<=6 N83 bases."""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import math
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))
from enumerate_n83_weight5_full import necklaces  # noqa: E402
from enumerate_q1413_projected_x import canonical_rotation, projected_x  # noqa: E402
from run_probe import ROOT, curves, field, sha  # noqa: E402

sys.path.insert(0, str(ROOT / "experiments/koblitz-pair-claw-20260929"))
from orbit_key import OrbitKey  # noqa: E402

PROTOCOL = HERE / "protocol.json"


def digest_keys(keys: set[int], n: int) -> str:
    digest = hashlib.sha256()
    width = (n + 7) // 8
    for key in sorted(keys):
        digest.update(key.to_bytes(width, "little"))
    return digest.hexdigest()


def n53_reference(onb, orbit):
    path = PARENT / "bases/n53_weight3_orbits.json.gz"
    with gzip.open(path, "rt") as stream:
        record = json.load(stream)
    base = record["factor_base"]
    data = base64.b64decode(base["packed_canonical_x_keys_base64"],
                            validate=True)
    assert hashlib.sha256(data).hexdigest() == base["enumerated_set_sha256"]
    width = (53 + 7) // 8
    assert len(data) % width == 0
    keys = {canonical_rotation(orbit.cycle_bits(onb.fromCoords(
        int.from_bytes(data[i:i + width], "little"))), 53)
        for i in range(0, len(data), width)}
    assert len(keys) == base["signed_frobenius_columns"] == 227
    return keys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--degree", type=int, choices=(53, 83), required=True)
    args = parser.parse_args()
    n = args.degree
    protocol = json.loads(PROTOCOL.read_text())
    instance = protocol["instances"][str(n)]
    weight = instance["new_weight_bound"]
    old_weight = instance["reference_weight_bound"]
    output = HERE / f"n{n}_w{weight}_base.json"
    assert not output.exists(), "refuse to overwrite exact base receipt"
    assert protocol["proposal_id"] == "Q1438"
    assert protocol["candidate_id"] is None and protocol["isogeny"] == "none"
    assert protocol["source_sha256"] == sha(Path(__file__))
    assert protocol["runtime_info_sha256"] == sha(HERE / "sage_runtime_info.json")
    assert json.loads((HERE / "sage_runtime_info.json").read_text())[
        "status"] == "verified"
    for path, digest in protocol["dependency_sha256"].items():
        assert digest == sha(ROOT / path)
    assert protocol["parent_protocol_sha256"] == sha(PARENT / "protocol.json")
    assert instance["field"]["n"] == n
    assert instance["curve"]["curve_id"] == instance["curve_id"]
    assert curves.curveOrder(n) == (instance["cofactor"] *
                                   instance["subgroup_order"])

    onb = field.Onb(n)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    keys, prefix_keys = set(), set()
    strata = {i: {"weight": i, "raw_x_orbits": 0,
                  "rational_x_orbits": 0, "identity_projection_orbits": 0,
                  "duplicate_projected_orbits_at_insertion": 0}
              for i in range(1, weight + 1)}
    controls = []
    rational_controls = nonrational_controls = 0
    started = time.perf_counter()
    for cycle_mask in necklaces(n, weight):
        row = strata[cycle_mask.bit_count()]
        row["raw_x_orbits"] += 1
        coords = 0
        bits = cycle_mask
        while bits:
            bit = bits & -bits
            coords |= 1 << orbit.coordinate_cycle[bit.bit_length() - 1]
            bits ^= bit
        x = onb.fromCoords(coords)
        if n == 53:
            raw_point = curve.pointFromX(x)
            rational = raw_point is not None
            projected_point = (curve.mul(raw_point, instance["cofactor"])
                               if rational else None)
            projected = (projected_point[0]
                         if projected_point is not None else None)
        else:
            rational, projected = projected_x(onb, x)
        if not rational:
            if nonrational_controls < 16:
                controls.append({"normal_x_mask": coords, "rational": False,
                                 "projected_orbit_key": None})
                nonrational_controls += 1
            continue
        row["rational_x_orbits"] += 1
        if projected is None:
            row["identity_projection_orbits"] += 1
            key = None
        else:
            key = canonical_rotation(orbit.cycle_bits(projected), n)
            if key in keys:
                row["duplicate_projected_orbits_at_insertion"] += 1
            else:
                keys.add(key)
            if row["weight"] <= old_weight:
                prefix_keys.add(key)
        if rational_controls < 16:
            controls.append({"normal_x_mask": coords, "rational": True,
                             "projected_orbit_key": key})
            rational_controls += 1
    elapsed = time.perf_counter() - started
    assert rational_controls == nonrational_controls == 16
    assert [strata[i]["raw_x_orbits"] for i in strata] == [
        math.comb(n, i) // n for i in strata]
    assert all(math.comb(n, i) % n == 0 for i in strata)
    assert all(key != 0 and key != (1 << n) - 1 for key in keys)
    assert len(keys) == sum(row["rational_x_orbits"] -
                            row["identity_projection_orbits"] -
                            row["duplicate_projected_orbits_at_insertion"]
                            for row in strata.values())
    if n == 53:
        assert prefix_keys == n53_reference(onb, orbit)
    else:
        prior = json.loads((PARENT / "runs/n83_q1413_projected_x_w5.json").read_text())
        assert len(prefix_keys) == prior["signed_frobenius_columns_K"]
        assert digest_keys(prefix_keys, n) == prior["enumerated_set_sha256"]
    assert len(prefix_keys) == instance["reference_columns_K"]
    assert 2 * n * len(prefix_keys) == instance["reference_actual_B"]

    receipt = {
        "kind": "q1438_exact_cofactor_projected_sparse_x_base",
        "proposal_id": "Q1438", "candidate_id": None,
        "workload_id": None, "run_id": None,
        "curve_id": instance["curve_id"], "isogeny": "none",
        "field_degree_n": n, "cofactor": instance["cofactor"],
        "normal_basis_weight_bound": weight,
        "nominal_x_mask_count": sum(math.comb(n, i)
                                    for i in range(1, weight + 1)),
        "actual_usable_points_B_before_folding": 2 * n * len(keys),
        "signed_frobenius_columns_K": len(keys),
        "enumerated_set_encoding": (
            f"sorted canonical cyclic-Frobenius projected x keys, "
            f"{(n + 7) // 8}-byte little-endian; expand each key to both "
            f"signs and all {n} Frobenius powers"),
        "enumerated_set_sha256": digest_keys(keys, n),
        "reference_weight_bound": old_weight,
        "reference_folded_columns_K": len(prefix_keys),
        "reference_projected_key_digest_sha256": digest_keys(prefix_keys, n),
        "reference_exact_set_checked": True,
        "strata": list(strata.values()),
        "independent_group_controls": controls,
        "enumeration_wall_seconds": elapsed,
        "peak_rss_raw": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "peak_rss_units": "bytes on Darwin, KiB on Linux",
        "protocol_sha256": sha(PROTOCOL),
        "source_sha256": sha(Path(__file__)),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "is_empirical_relation_yield": False,
        "complete_solve_work_log2": None,
    }
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"n": n, "weight": weight,
                      "B": receipt["actual_usable_points_B_before_folding"],
                      "K": len(keys), "seconds": elapsed}), flush=True)


if __name__ == "__main__":
    main()
