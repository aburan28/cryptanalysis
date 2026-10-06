#!/usr/bin/env python3
"""Exact signed-Frobenius base enumeration using the x-coordinate of [4]P.

For E: y^2 + xy = x^3 + 1 in characteristic two, x([2]P) = x(P)^2 +
x(P)^(-2). Rationality is Tr(x + x^(-1)) = 0. Both properties depend only
on x, so the two signed lifts need not be built for every sparse support.
The group law is replayed on sampled representatives at every weight.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import resource
import sys
import time
from pathlib import Path

from enumerate_n83_weight5_full import necklaces
from run_probe import HERE, ROOT, curves, field, sha

PAIR = ROOT / "experiments/koblitz-pair-claw-20260929"
sys.path.insert(0, str(PAIR))
from orbit_key import OrbitKey  # noqa: E402

PROTOCOL = HERE / "q1413_projected_x_protocol.json"
KEY_FILE = HERE / "bases/n83_weight5_full_point_orbits.bin"
Q1302 = HERE / "bases/n83_weight4_orbits.json.gz"


def canonical_rotation(value: int, n: int) -> int:
    mask = (1 << n) - 1
    best = current = value
    for _ in range(1, n):
        current = ((current << 1) | (current >> (n - 1))) & mask
        if current < best:
            best = current
    return best


def projected_x(onb, x):
    """Return (rational, x([4]P)) or (rational, None) for [4]P = O."""
    assert x != 0
    inverse = onb.inv(x)
    rational = onb.trace(x) == onb.trace(inverse)
    if not rational:
        return False, None
    double_x = onb.sqr(onb.add(x, inverse))
    if double_x == 0:
        return True, None
    double_inverse = onb.inv(double_x)
    return True, onb.sqr(onb.add(double_x, double_inverse))


def control(onb, curve, x, predicted, subgroup_order):
    point = curve.pointFromX(x)
    assert point is not None
    actual = curve.mul(point, 4)
    assert (actual is None) == (predicted is None)
    if actual is not None:
        assert actual[0] == predicted
        assert curve.onCurve(actual)
        assert curve.mul(actual, subgroup_order) is None


def reference_keys(n: int, weight: int, orbit):
    if n != 83:
        return None, None
    if weight == 5:
        data = KEY_FILE.read_bytes()
        assert len(data) % 21 == 0
        keys = {int.from_bytes(data[i:i + 21], "little") >> 83
                for i in range(0, len(data), 21)}
        assert len(keys) == 186612
        return keys, sha(KEY_FILE)
    if weight == 4:
        import base64
        with gzip.open(Q1302, "rt") as stream:
            base = json.load(stream)
        encoded = base64.b64decode(base["factor_base"][
            "packed_canonical_x_keys_base64"], validate=True)
        assert hashlib.sha256(encoded).hexdigest() == base["factor_base"][
            "enumerated_set_sha256"]
        keys = {canonical_rotation(orbit.cycle_bits(onb_x), 83)
                for onb_x in (orbit.onb.fromCoords(int.from_bytes(
                    encoded[i:i + 11], "little"))
                    for i in range(0, len(encoded), 11))}
        assert len(keys) == 11651
        return keys, sha(Q1302)
    return None, None


def enumerate_base(n: int, weight: int, protocol: dict):
    design = protocol["instances"][str(n)]
    assert design["curve_id"] in (
        "EC1N83Ckb1h876c2921cb64", "EC1N131Ckb1h6816f880945e")
    assert design["cofactor"] == 4
    assert curves.curveOrder(n) == 4 * design["subgroup_order"]
    onb = field.Onb(n)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    keys = set()
    strata = {i: {"weight": i, "x_orbits": 0, "rational_x_orbits": 0,
                  "identity_projection_orbits": 0,
                  "duplicate_projection_orbits": 0,
                  "sampled_group_controls": 0}
              for i in range(1, weight + 1)}
    start = time.perf_counter()
    for cycle_mask in necklaces(n, weight):
        row = strata[cycle_mask.bit_count()]
        row["x_orbits"] += 1
        coords = 0
        bits = cycle_mask
        while bits:
            bit = bits & -bits
            coords |= 1 << orbit.coordinate_cycle[bit.bit_length() - 1]
            bits ^= bit
        x = onb.fromCoords(coords)
        rational, projected = projected_x(onb, x)
        if not rational:
            continue
        row["rational_x_orbits"] += 1
        if row["sampled_group_controls"] < 16:
            control(onb, curve, x, projected, design["subgroup_order"])
            row["sampled_group_controls"] += 1
        if projected is None:
            row["identity_projection_orbits"] += 1
            continue
        key = canonical_rotation(orbit.cycle_bits(projected), n)
        if key in keys:
            row["duplicate_projection_orbits"] += 1
        else:
            keys.add(key)
    elapsed = time.perf_counter() - start
    for i, row in strata.items():
        assert row["x_orbits"] == math.comb(n, i) // n
    assert all(key != 0 and key != (1 << n) - 1 for key in keys)
    assert sum(row["rational_x_orbits"] -
               row["identity_projection_orbits"] -
               row["duplicate_projection_orbits"]
               for row in strata.values()) == len(keys)
    width = (n + 7) // 8
    digest = hashlib.sha256()
    for key in sorted(keys):
        digest.update(key.to_bytes(width, "little"))
    expected, expected_sha = reference_keys(n, weight, orbit)
    if expected is not None:
        assert keys == expected
    return {
        "kind": "exact_cofactor_four_projected_x_orbit_base",
        "proposal_id": "Q1413",
        "parent_base_proposal_id": design["base_proposal_ids"][str(weight)],
        "candidate_id": None, "workload_id": None, "run_id": None,
        "curve_id": design["curve_id"], "isogeny": "none",
        "field_degree_n": n, "normal_basis_weight_bound": weight,
        "cofactor": 4,
        "nominal_x_mask_count": sum(math.comb(n, i)
                                    for i in range(1, weight + 1)),
        "actual_usable_points_B_before_folding": 2 * n * len(keys),
        "signed_frobenius_columns_K": len(keys),
        "enumerated_set_encoding": (
            f"sorted canonical cyclic-Frobenius x keys, {width}-byte "
            "little-endian; both signs and all Frobenius powers expand a key"),
        "enumerated_set_sha256": digest.hexdigest(),
        "strata": list(strata.values()),
        "n83_reference_set_equal": expected is not None,
        "n83_reference_artifact_sha256": expected_sha,
        "enumeration_wall_seconds": elapsed,
        "peak_rss_raw": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "peak_rss_units": "bytes on Darwin, KiB on Linux",
        "protocol_sha256": sha(PROTOCOL),
        "source_sha256": sha(Path(__file__)),
        "field_source_sha256": sha(Path(field.__file__)),
        "curve_source_sha256": sha(Path(curves.__file__)),
        "orbit_source_sha256": sha(PAIR / "orbit_key.py"),
        "necklace_source_sha256": sha(HERE / "enumerate_n83_weight5_full.py"),
        "is_empirical_relation_yield": False,
        "is_complete_solve_projection": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, choices=(83, 131), required=True)
    parser.add_argument("--weight", type=int, required=True)
    args = parser.parse_args()
    assert (args.n, args.weight) in ((83, 4), (83, 5), (131, 5), (131, 6))
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["proposal_id"] == "Q1413"
    assert protocol["candidate_id"] is None and protocol["isogeny"] == "none"
    assert protocol["source_sha256"] == sha(Path(__file__))
    assert protocol["parent_protocol_sha256"] == sha(HERE / "protocol.json")
    assert protocol["reference_artifact_sha256"] == {
        "q1302": sha(Q1302), "q1325": sha(KEY_FILE)}
    parent = json.loads((HERE / "protocol.json").read_text())
    n83_parent = next(row for row in parent["profiles"]
                      if row["field"]["n"] == 83)
    n131_parent = parent["degree_131_design"]
    assert protocol["instances"]["83"]["curve_id"] == n83_parent[
        "curve"]["curve_id"]
    assert protocol["instances"]["131"]["curve_id"] == n131_parent[
        "curve"]["curve_id"]
    for n, record in ((83, n83_parent), (131, n131_parent)):
        assert protocol["instances"][str(n)]["subgroup_order"] == record[
            "curve"]["subgroup_order"]
    for relative, expected in protocol["dependency_sha256"].items():
        assert expected == sha(ROOT / relative)
    runtime_path = HERE / "q1413_sage_runtime_info.json"
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    assert protocol["runtime_info_sha256"] == sha(runtime_path)
    output = HERE / "runs" / f"n{args.n}_q1413_projected_x_w{args.weight}.json"
    assert not output.exists()
    receipt = enumerate_base(args.n, args.weight, protocol)
    receipt["runtime_info_sha256"] = sha(runtime_path)
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"n": args.n, "weight": args.weight,
                      "B": receipt["actual_usable_points_B_before_folding"],
                      "K": receipt["signed_frobenius_columns_K"],
                      "seconds": receipt["enumeration_wall_seconds"]}),
          flush=True)


if __name__ == "__main__":
    main()
