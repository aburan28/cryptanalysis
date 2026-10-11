#!/usr/bin/env sage -python
"""Freeze public W24 controls and a scalar-separated ECC2K-130 target corpus."""

import argparse
import hashlib
import json
import resource
import sys
import time
import traceback
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ
from sage.version import version as sage_version


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ROUTE = ROOT / "experiments/koblitz-polynomial-w-pair-20260925/ecc2k130_degree263_route_manifest.json"
CONFIG = HERE / "CONFIG.json"
BASE = HERE / "base_selection.json"
RUNTIME = HERE / "runtime-info.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(record):
    return json.dumps(record, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def save_new(path, record):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(record, stream, indent=2, sort_keys=True)
        stream.write("\n")


def peak_bytes():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value * 1024


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=HERE)
    args = parser.parse_args()
    out = args.out_dir
    outputs = [out / name for name in ("workload.json", "target_fixtures.json",
                                       "point_controls.json", "producer_receipt.json")]
    if any(path.exists() for path in outputs):
        parser.error("refusing to overwrite frozen artifacts")
    started = time.perf_counter()
    config = json.loads(CONFIG.read_text())
    base = json.loads(BASE.read_text())
    route = json.loads(ROUTE.read_text())
    assert sha(ROUTE) == config["route_manifest_sha256"]
    assert base["config_sha256"] == sha(CONFIG)
    assert route["route_id"] == config["route_id"]
    assert route["curve_nodes"]["source"]["curve_id"] == config["source_curve_id"]
    assert route["curve_nodes"]["target"]["curve_id"] == config["descendant_curve_id"]
    assert base["source"]["selected_signed_columns"] == base[
        "descendant_native"]["selected_signed_columns"] == config[
        "selected_signed_columns_each"]

    binary = PolynomialRing(GF(2), "t")
    t = binary.gen()
    modulus = t**131 + t**13 + t**2 + t + 1
    assert modulus.is_irreducible()
    field = GF(2**131, "t", modulus=modulus)

    def decode(word):
        word = int(word)
        return field(sum(t**i for i in range(word.bit_length())
                         if (word >> i) & 1))

    def encode(value):
        return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))

    def point_words(point):
        assert not point.is_zero()
        return [encode(point[0]), encode(point[1])]

    source = EllipticCurve(field, [1, 0, 0, 0, 1])
    poly = PolynomialRing(field, "X")
    forward_poly = poly([decode(c) for c in route["isogeny"]["forward_map"][
        "kernel_polynomial_coefficients"]])
    dual_poly = poly([decode(c) for c in route["isogeny"]["dual_map"][
        "kernel_polynomial_coefficients"]])
    forward = source.isogeny(forward_poly, check=True)
    target = forward.codomain()
    target_record = route["curve_nodes"]["target"]
    assert [encode(a) for a in target.ainvs()] == target_record[
        "coefficients_a1_a2_a3_a4_a6"]
    dual = target.isogeny(dual_poly, check=True)
    iso = dual.codomain().isomorphism_to(source)
    sign = ZZ(route["isogeny"]["dual_map"]["composition_sign"])
    assert sign in (-1, 1)
    assert [encode(a) for a in iso.tuple()] == route["isogeny"][
        "dual_map"]["isomorphism_tuple_to_source"]
    r = ZZ(route["curve_nodes"]["source"]["subgroup_order"])
    inverse_263 = ZZ(263).inverse_mod(r)
    generator = source([decode(v) for v in route["curve_nodes"][
        "source"]["generator_G"]])
    mapped_generator = target([decode(v) for v in target_record["generator_G"]])
    assert r*generator == source(0) and r*mapped_generator == target(0)
    assert forward(generator) == mapped_generator
    assert sign*iso(dual(mapped_generator)) == 263*generator
    assert inverse_263*sign*iso(dual(mapped_generator)) == generator
    map_setup_seconds = time.perf_counter() - started
    print("route maps and generators checked", round(map_setup_seconds, 3), flush=True)

    a = decode(target_record["coefficients_a1_a2_a3_a4_a6"][3])
    b = decode(target_record["coefficients_a1_a2_a3_a4_a6"][4]) + a*a
    normalized = EllipticCurve(field, [1, 0, 0, 0, b])
    alpha = b ** (1 << 129)
    assert alpha**4 == b
    basis = [field.gen()**j + (field.gen()**j).trace()
             for j in range(1, config["w_dimension"] + 1)]
    assert all(int(v.trace()) == 0 for v in basis)

    def half_trace(value):
        term = total = value
        for _ in range(65):
            term = term**4
            total += term
        assert total**2 + total == value
        return total

    def project(mask, curve, coordinate_a, coefficient):
        w = field.zero()
        for index, element in enumerate(basis):
            if mask & (1 << index):
                w += element
        assert w and int(w.trace()) == 0
        u = half_trace(w)
        assert u not in (0, 1)
        x = coordinate_a * (1 + 1/u)
        rhs = x + coefficient/(x*x)
        assert int(rhs.trace()) == 0
        projected = 4*curve([x, x*half_trace(rhs)])
        assert not projected.is_zero() and r*projected == curve(0)
        return projected

    def check_envelope():
        if time.perf_counter() - started > config["wall_limit_seconds"]:
            raise TimeoutError("frozen wall envelope exceeded")
        if peak_bytes() > config["peak_rss_limit_bytes"]:
            raise MemoryError("frozen RSS envelope exceeded")

    controls = {"schema": "ecc2k130-263-equal-w24-controls-v1",
                "config_sha256": sha(CONFIG), "base_selection_sha256": sha(BASE),
                "route_manifest_sha256": sha(ROUTE), "point_encoding":
                "little_endian_polynomial_basis_integer_affine_xy",
                "source_curve_id": config["source_curve_id"],
                "descendant_curve_id": config["descendant_curve_id"],
                "source": [], "descendant_native": []}
    control_started = time.perf_counter()
    for index, mask in zip(base["source"]["control_indices_selection_order"],
                           base["source"]["control_masks_selection_order"]):
        check_envelope()
        point = project(mask, source, field.one(), field.one())
        image = forward(point)
        assert not image.is_zero() and r*image == target(0)
        assert inverse_263*sign*iso(dual(image)) == point
        controls["source"].append({"index": index, "mask": mask,
                                   "source": point_words(point),
                                   "transported": point_words(image)})
    for index, mask in zip(base["descendant_native"][
            "control_indices_selection_order"], base["descendant_native"][
            "control_masks_selection_order"]):
        check_envelope()
        normalized_point = project(mask, normalized, alpha, b)
        native = target([normalized_point[0], normalized_point[1] + a])
        assert r*native == target(0)
        pullback = inverse_263*sign*iso(dual(native))
        assert forward(pullback) == native and r*pullback == source(0)
        controls["descendant_native"].append({"index": index, "mask": mask,
                                               "descendant_native": point_words(native),
                                               "pullback": point_words(pullback)})
    control_seconds = time.perf_counter() - control_started
    print("point controls checked", len(controls["source"]),
          len(controls["descendant_native"]), round(control_seconds, 3), flush=True)

    targets = []
    fixture_scalars = []
    seen = set()
    counter = 0
    target_started = time.perf_counter()
    while len(targets) < config["target_count"]:
        check_envelope()
        digest = hashlib.sha256(config["target_scalar_domain"].encode() +
                                b":" + counter.to_bytes(8, "big")).digest()
        scalar = int.from_bytes(digest[:17], "big") & ((1 << 130) - 1)
        current_counter = counter
        counter += 1
        if not 0 < scalar < r or scalar in seen:
            continue
        seen.add(scalar)
        point = ZZ(scalar)*generator
        image = forward(point)
        assert not point.is_zero() and not image.is_zero()
        assert image == ZZ(scalar)*mapped_generator
        assert inverse_263*sign*iso(dual(image)) == point
        targets.append({"index": len(targets), "counter": current_counter,
                        "source": point_words(point),
                        "descendant": point_words(image)})
        fixture_scalars.append(scalar)
        if len(targets) % 64 == 0:
            print("public fixtures checked", len(targets), flush=True)
    target_seconds = time.perf_counter() - target_started
    workload = {"schema": "ecc2k130-263-equal-w24-public-workload-v1",
                "config_sha256": sha(CONFIG), "base_selection_sha256": sha(BASE),
                "route_manifest_sha256": sha(ROUTE),
                "source_curve_id": config["source_curve_id"],
                "descendant_curve_id": config["descendant_curve_id"],
                "route_id": config["route_id"],
                "point_encoding": "little_endian_polynomial_basis_integer_affine_xy",
                "input_law": config["target_scalar_law"],
                "target_scalar_domain": config["target_scalar_domain"],
                "target_count": config["target_count"],
                "primary_target_index": 0,
                "remaining_targets_status": "dormant_fixture_controls",
                "targets": targets}
    workload_sha = hashlib.sha256(canonical(workload)).hexdigest()
    workload["workload_id"] = workload_sha[:12]
    fixtures = {"schema": "ecc2k130-263-equal-w24-target-fixtures-v1",
                "workload_id": workload["workload_id"],
                "workload_identity_sha256": workload_sha,
                "accepted_scalars": fixture_scalars,
                "counter_attempts": counter,
                "use": "independent_fixture_replay_only; never solver input"}
    receipt = {"schema": "ecc2k130-263-equal-w24-producer-receipt-v1",
               "status": "PASS_INPUT_CONSTRUCTION_UNVERIFIED",
               "candidate_id": None, "workload_id": workload["workload_id"],
               "config_sha256": sha(CONFIG), "base_selection_sha256": sha(BASE),
               "route_manifest_sha256": sha(ROUTE), "sage_runtime_info_sha256": sha(RUNTIME),
               "producer_sha256": sha(Path(__file__)), "sage_version": sage_version,
               "map_setup_wall_seconds": map_setup_seconds,
               "control_wall_seconds": control_seconds,
               "fixture_wall_seconds": target_seconds,
               "total_wall_seconds": time.perf_counter() - started,
               "peak_rss_bytes": peak_bytes(),
               "memory_unit": "bytes",
               "source_control_count": len(controls["source"]),
               "native_control_count": len(controls["descendant_native"]),
               "public_fixture_count": len(targets),
               "natural_pdp_yield": None, "verified_relation_rank": None,
               "verified_logarithm": None, "online_wall_time": None,
               "rho_ratio": None}
    out.mkdir(parents=True, exist_ok=True)
    for path, record in zip(outputs, (workload, fixtures, controls, receipt)):
        save_new(path, record)
    print(json.dumps({"workload_id": workload["workload_id"],
                      "targets": len(targets), "controls": 128,
                      "wall_seconds": round(receipt["total_wall_seconds"], 3)}),
          flush=True)


if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("assertions must remain enabled")
    try:
        main()
    except BaseException as error:
        failure = HERE / "producer_failure.json"
        if not failure.exists():
            save_new(failure, {"schema": "ecc2k130-263-equal-w24-failure-v1",
                               "status": "FAILED", "error_type": type(error).__name__,
                               "error": str(error), "traceback": traceback.format_exc(),
                               "producer_sha256": sha(Path(__file__))})
        raise
