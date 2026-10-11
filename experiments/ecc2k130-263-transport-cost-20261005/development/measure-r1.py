#!/usr/bin/env sage -python
"""Measure and verify exact degree-263 maps on frozen public points."""

import argparse
import hashlib
import json
import platform
import resource
import statistics
import sys
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
INPUT = ROOT / "experiments/ecc2k130-263-equal-w24-workload-20261005"
ROUTE = ROOT / "experiments/koblitz-polynomial-w-pair-20260925/ecc2k130_degree263_route_manifest.json"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def summary(values):
    return {"count": len(values), "min_ns": min(values),
            "median_ns": statistics.median(values), "max_ns": max(values)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists()
    runtime = HERE / "runtime-info.json"
    assert runtime.is_file(), "save checked Sage --runtime-info before the run"
    route = json.loads(ROUTE.read_text())
    workload = json.loads((INPUT / "workload.json").read_text())
    primary = json.loads((INPUT / "primary_workload.json").read_text())
    controls = json.loads((INPUT / "point_controls.json").read_text())
    assert workload["route_manifest_sha256"] == sha256(ROUTE)
    assert controls["route_manifest_sha256"] == sha256(ROUTE)
    assert workload["source_curve_id"] == route["curve_nodes"]["source"]["curve_id"]
    assert workload["descendant_curve_id"] == route["curve_nodes"]["target"]["curve_id"]
    assert primary["target_count"] == 1
    assert primary["targets"][0] == workload["targets"][0]
    assert len(workload["targets"]) >= 64
    assert len(controls["source"]) == len(controls["descendant_native"]) == 64

    field_started = time.perf_counter_ns()
    binary = PolynomialRing(GF(2), "z")
    z = binary.gen()
    modulus = z**131 + z**13 + z**2 + z + 1
    assert modulus.is_irreducible()
    field = GF(2**131, "z", modulus=modulus)

    def decode(number):
        number = int(number)
        return field(sum(z**bit for bit in range(number.bit_length())
                         if (number >> bit) & 1))

    def encode(number):
        return sum(int(bit) << index for index, bit in
                   enumerate(number.polynomial().list()))

    def decode_point(curve, words):
        assert len(words) == 2 and all(isinstance(value, int) for value in words)
        point = curve([decode(words[0]), decode(words[1])])
        assert [encode(point[0]), encode(point[1])] == words
        return point

    source = EllipticCurve(field, [1, 0, 0, 0, 1])
    field_setup_ns = time.perf_counter_ns() - field_started
    setup_started = time.perf_counter_ns()
    ring = PolynomialRing(field, "Y")
    forward_kernel = ring([decode(coefficient) for coefficient in
                           route["isogeny"]["forward_map"]["kernel_polynomial_coefficients"]])
    dual_kernel = ring([decode(coefficient) for coefficient in
                        route["isogeny"]["dual_map"]["kernel_polynomial_coefficients"]])
    forward = source.isogeny(forward_kernel, check=True)
    descendant = forward.codomain()
    assert [encode(value) for value in descendant.ainvs()] == route[
        "curve_nodes"]["target"]["coefficients_a1_a2_a3_a4_a6"]
    dual = descendant.isogeny(dual_kernel, check=True)
    codomain_iso = dual.codomain().isomorphism_to(source)
    assert [encode(value) for value in codomain_iso.tuple()] == route[
        "isogeny"]["dual_map"]["isomorphism_tuple_to_source"]
    orientation = ZZ(route["isogeny"]["dual_map"]["composition_sign"])
    order = ZZ(route["curve_nodes"]["source"]["subgroup_order"])
    inverse_degree = ZZ(263).inverse_mod(order)
    generator = decode_point(source, route["curve_nodes"]["source"]["generator_G"])
    image_generator = decode_point(descendant, route["curve_nodes"]["target"]["generator_G"])
    assert forward(generator) == image_generator
    assert orientation*codomain_iso(dual(image_generator)) == 263*generator
    map_setup_ns = time.perf_counter_ns() - setup_started

    source_targets = [decode_point(source, row["source"])
                      for row in workload["targets"][:64]]
    descendant_targets = [decode_point(descendant, row["descendant"])
                          for row in workload["targets"][:64]]
    source_controls = [decode_point(source, row["source"])
                       for row in controls["source"]]
    transported_controls = [decode_point(descendant, row["transported"])
                            for row in controls["source"]]
    native_controls = [decode_point(descendant, row["descendant_native"])
                       for row in controls["descendant_native"]]
    pullback_controls = [decode_point(source, row["pullback"])
                         for row in controls["descendant_native"]]

    def inverse(point):
        return inverse_degree*orientation*codomain_iso(dual(point))

    def timed(inputs, expected, operation):
        elapsed = []
        for index, (point, wanted) in enumerate(zip(inputs, expected)):
            started = time.perf_counter_ns()
            found = operation(point)
            elapsed.append(time.perf_counter_ns() - started)
            assert found == wanted, f"map mismatch at control {index}"
        assert len(elapsed) == len(inputs) == len(expected) == 64
        return elapsed

    target_forward = timed(source_targets, descendant_targets, forward)
    target_inverse = timed(descendant_targets, source_targets, inverse)
    base_forward = timed(source_controls, transported_controls, forward)
    base_inverse = timed(native_controls, pullback_controls, inverse)
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak = peak if sys.platform == "darwin" else peak*1024
    result = {
        "schema": "ecc2k130-263-transport-cost-v1",
        "status": "PASS_256_FROZEN_MAP_EVALUATIONS",
        "candidate_id": None,
        "primary_workload_id": primary["workload_id"],
        "control_corpus_id": workload["workload_id"],
        "source_curve_id": workload["source_curve_id"],
        "descendant_curve_id": workload["descendant_curve_id"],
        "route_id": route["route_id"],
        "primary_target_index": 0,
        "primary_forward_ns": target_forward[0],
        "primary_inverse_ns": target_inverse[0],
        "field_setup_ns_excluded": field_setup_ns,
        "map_setup_ns_excluded": map_setup_ns,
        "target_forward_ns": target_forward,
        "target_inverse_ns": target_inverse,
        "base_forward_ns": base_forward,
        "base_inverse_ns": base_inverse,
        "diagnostic_summaries": {
            "target_forward": summary(target_forward),
            "target_inverse": summary(target_inverse),
            "base_forward": summary(base_forward),
            "base_inverse": summary(base_inverse),
        },
        "checks": {
            "source_target_to_descendant": 64,
            "descendant_target_to_source": 64,
            "source_base_to_transport": 64,
            "native_base_to_pullback": 64,
            "generator_and_dual_composition": True,
        },
        "host": {"platform": platform.platform(), "machine": platform.machine(),
                 "python": platform.python_version()},
        "peak_rss_bytes": peak,
        "sha256": {
            "route": sha256(ROUTE),
            "workload": sha256(INPUT / "workload.json"),
            "primary_workload": sha256(INPUT / "primary_workload.json"),
            "base_controls": sha256(INPUT / "point_controls.json"),
            "runtime_info": sha256(runtime),
            "protocol": sha256(HERE / "PROTOCOL.md"),
            "source": sha256(Path(__file__)),
        },
        "natural_pdp_yield": None,
        "verified_relation_rank": None,
        "verified_logarithm": None,
        "ic_online_ms": None,
        "rho_online_ms": None,
        "speedup": None,
    }
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({key: result[key] for key in
                      ("status", "primary_forward_ns", "primary_inverse_ns",
                       "diagnostic_summaries")}), flush=True)


if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("assertions must remain enabled")
    main()
