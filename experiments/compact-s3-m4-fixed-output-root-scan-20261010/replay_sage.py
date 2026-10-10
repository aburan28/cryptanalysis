#!/usr/bin/env python3
"""Replay native right-pair hits on the exact curves with checked Sage."""

from __future__ import annotations

import base64
import gzip
import itertools
import json
from pathlib import Path
import sys
import time

from sage.all import EllipticCurve, GF, PolynomialRing

import experiment

HERE = Path(__file__).resolve().parent
ROOT = experiment.ROOT
OLD = experiment.OLD
sys.path.insert(0, str(OLD))
sys.path.insert(0, str(ROOT / "experiments/koblitz-pair-claw-20260929"))
from run_probe import curves, field  # noqa: E402
from orbit_key import OrbitKey  # noqa: E402


def poly_element(poly_field, integer):
    generator = poly_field.gen()
    answer = poly_field.zero()
    power = poly_field.one()
    for _ in range(poly_field.degree()):
        if integer & 1:
            answer += power
        integer >>= 1
        power *= generator
    assert integer == 0
    return answer


def load_keys(profile, onb) -> set[int]:
    archive_path = ROOT / profile["factor_base_archive"]["path"]
    assert experiment.sha(archive_path) == profile[
        "factor_base_archive"]["sha256"]
    n = profile["field_degree_n"]
    if n == 53:
        with gzip.open(archive_path, "rt") as stream:
            data = json.load(stream)
        encoded = base64.b64decode(data["factor_base"][
            "packed_canonical_x_keys_base64"], validate=True)
        step = 7
    else:
        encoded = archive_path.read_bytes()
        step = 21
    assert experiment.sha_bytes(encoded) == profile[
        "factor_base_enumerated_set_sha256"]
    assert len(encoded) % step == 0
    keys = {int.from_bytes(encoded[i:i + step], "little")
            for i in range(0, len(encoded), step)}
    assert len(keys) == profile["folded_columns_K"]
    return keys


def canonical_x(onb, point) -> int:
    x = point[0]
    values = []
    for _ in range(onb.m):
        values.append(onb.toCoords(x))
        x = onb.sqr(x)
    return min(values)


def replay_degree(n: int, profile: dict) -> list[dict]:
    bridge_path = OLD / "field_bridges" / f"n{n}_onb_poly.json"
    bridge = json.loads(bridge_path.read_text())
    basis_images = bridge["onb_to_poly_basis_images"]
    low_terms = bridge["target_implementation_basis"]["low_terms"]
    f2 = GF(2)
    ring = PolynomialRing(f2, "z")
    z = ring.gen()
    modulus = z ** n + sum(z ** degree for degree in low_terms)
    assert modulus.is_irreducible()
    poly_field = GF(2 ** n, f"u{n}", modulus=modulus)
    elliptic = EllipticCurve(poly_field, [1, 0, 0, 0, 1])
    onb = field.Onb(n)
    native_curve = curves.Curve(onb)
    keys = load_keys(profile, onb)
    orbit = OrbitKey(onb) if n == 83 else None
    cofactor = profile["cofactor"]
    order = profile["subgroup_order_r"]

    def mapped(point):
        if point is None:
            return elliptic(0)
        coords = [experiment.xor_images(onb.toCoords(int(value)),
                                        basis_images)
                  for value in point]
        return elliptic(poly_element(poly_field, coords[0]),
                        poly_element(poly_field, coords[1]))

    rows = []
    for kind in experiment.KINDS:
        for window in experiment.WINDOWS:
            name = experiment.cell_name(n, kind, window)
            inp = json.loads((HERE / "inputs" / f"{name}.json").read_text())
            source = json.loads((HERE / "runs" / f"{name}.scan.json").read_text())
            assert inp["curve_id"] == bridge["curve_id"] == profile["curve_id"]
            assert inp["factor_base_actual_B"] == profile["factor_base_actual_B"]
            assert inp["factor_base_folded_columns_K"] == profile["folded_columns_K"]
            public_onb = tuple(map(int, inp["public_target"]))
            assert native_curve.onCurve(public_onb)
            public = mapped(public_onb)
            assert order * public == elliptic(0)
            output = poly_element(poly_field, int(
                inp["right_output_x_poly_decimal"]))
            checked = []
            for hit in source["recorded_hits"]:
                right_coords = [experiment.xor_images(int(hit[key]),
                    bridge["poly_to_onb_basis_images"])
                    for key in ("left_x_poly_decimal", "right_x_poly_decimal")]
                all_coords = [int(leaf["raw_x"]) for leaf in inp[
                    "selected_anchor"]["leaves"]] + right_coords
                raw_points = [native_curve.pointFromX(onb.fromCoords(coords))
                              for coords in all_coords]
                status = "nonrational_raw_x"
                columns = []
                if all(point is not None for point in raw_points):
                    mapped_points = [mapped(point) for point in raw_points]
                    left = poly_element(poly_field, int(
                        hit["left_x_poly_decimal"]))
                    right = poly_element(poly_field, int(
                        hit["right_x_poly_decimal"]))
                    assert ((left * output + (left + output) * right) ** 2 +
                            left * output * right + 1) == 0
                    projections = [native_curve.mul(point, cofactor)
                                   for point in raw_points]
                    status = "identity_projection"
                    if all(point is not None for point in projections):
                        assert all(order * mapped(point) == elliptic(0)
                                   for point in projections)
                        assert all(cofactor * raw == mapped(projected)
                                   for raw, projected in zip(mapped_points,
                                                             projections))
                        columns = [canonical_x(onb, point) if n == 53 else
                                   orbit.canonical(point)[0]
                                   for point in projections]
                        status = "outside_exact_base"
                        if all(column in keys for column in columns):
                            status = "duplicate_columns"
                            if len(set(columns)) == 4:
                                status = "no_signed_public_sum"
                                for signs in itertools.product((1, -1), repeat=4):
                                    raw_sum = elliptic(0)
                                    for sign, point in zip(signs, mapped_points):
                                        raw_sum += sign * point
                                    if cofactor * raw_sum == public:
                                        status = "verified_four_point_relation"
                                        break
                checked.append({"raw_leaf_x": [str(x) for x in all_coords],
                                "status": status,
                                "distinct_columns": len(set(columns)),
                                "columns_in_base": sum(x in keys for x in columns)})
            rows.append({"cell": name, "curve_id": inp["curve_id"],
                         "workload_id": inp["workload_id"],
                         "recorded_hits_checked": len(checked),
                         "hits": checked})
    return rows


def main() -> None:
    started = time.perf_counter_ns()
    frozen = experiment.check_freeze()
    runtime_path = HERE / "sage_runtime_info.json"
    assert runtime_path.exists()
    runtime_info = json.loads(runtime_path.read_text())
    assert runtime_info["status"] == "verified"
    protocol = json.loads((OLD / "q1419_partial_pin/protocol.json").read_text())
    rows = [row for n in experiment.DEGREES
            for row in replay_degree(n, protocol["profiles"][str(n)])]
    assert len(rows) == 8
    result = {"schema": "q20261010103500-sage-replay-v1",
              "proposal_id": "Q20261010103500",
              "freeze_sha256": experiment.sha(HERE / "freeze.json"),
              "sage_runtime_info_sha256": experiment.sha(runtime_path),
              "protocol_sha256": experiment.sha(
                  OLD / "q1419_partial_pin/protocol.json"),
              "elapsed_ns": str(time.perf_counter_ns() - started),
              "rows": rows}
    experiment.write_json(HERE / "sage_replay.json", result)
    print(json.dumps({"status": "PASS", "rows": len(rows),
                      "checked_hits": sum(row["recorded_hits_checked"]
                                          for row in rows)}))


if __name__ == "__main__":
    main()
