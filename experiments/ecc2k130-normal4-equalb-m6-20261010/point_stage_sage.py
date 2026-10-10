#!/usr/bin/env sage -python
"""Construct the frozen equal-B point controls and ordinary public queries."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ

from freeze_inputs import scalar_sequence


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CONFIG = HERE / "CONFIG.json"
POINT_BYTES = 17


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def peak_bytes() -> int:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak if sys.platform == "darwin" else peak * 1024


def save_new(path: Path, record: dict) -> None:
    with path.open("x") as stream:
        json.dump(record, stream, indent=2, sort_keys=True)
        stream.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--runtime-info", type=Path, required=True)
    parser.add_argument("--count", type=int, choices=(16, 256, 65536), required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.out_dir.exists():
        parser.error("refusing to overwrite a point-stage run")
    started = time.perf_counter()
    cpu_started = time.process_time()
    args.out_dir.mkdir(parents=True)
    config = load(CONFIG)
    envelope = config["input_producer_envelope"]
    progress = {"phase": "preflight", "queries_completed": 0,
                "controls_completed": 0}

    def check_resources() -> None:
        if time.perf_counter() - started > envelope["wall_seconds"]:
            raise TimeoutError("frozen point-stage wall cap exceeded")
        if peak_bytes() > envelope["peak_rss_bytes"]:
            raise MemoryError("frozen point-stage RSS cap exceeded")

    try:
        runtime = load(args.runtime_info)
        if runtime.get("status") != "verified":
            raise ValueError("checked Sage runtime is not verified")
        base_path = args.input_dir / "base_prefixes.json"
        scalar_path = args.input_dir / "query_scalars.json"
        replay_path = args.input_dir / "input_verification.json"
        base = load(base_path)
        scalars = load(scalar_path)
        replay = load(replay_path)
        config_sha = sha256(CONFIG)
        if (base["config_sha256"] != config_sha
                or scalars["config_sha256"] != config_sha
                or replay["status"] != "PASS_INDEPENDENT_MASK_AND_SCALAR_REPLAY"
                or replay["base_receipt_sha256"] != sha256(base_path)
                or replay["query_receipt_sha256"] != sha256(scalar_path)
                or scalars["accepted_count"] != 65536):
            raise ValueError("frozen input receipts are unverified or changed")
        for name, entry in config["bound_inputs"].items():
            if sha256(ROOT / entry["path"]) != entry["sha256"]:
                raise ValueError(f"bound source changed: {name}")
        route_path = ROOT / config["bound_inputs"]["route_manifest"]["path"]
        route = load(route_path)
        primary = load(ROOT / config["bound_inputs"]["q1420_primary_workload"]["path"])
        normal4 = load(ROOT / config["bound_inputs"]["q1421_producer"]["path"])
        fixtures = load(ROOT / "experiments/ecc2k130-263-equal-w24-workload-20261005/target_fixtures.json")
        parent = load(ROOT / "experiments/ecc2k130-w24-normal-barrel-20261006/runs/R2/result.json")
        if (route["route_id"] != config["route_id"]
                or primary["workload_id"] != config["primary_target"]["workload_id"]
                or normal4["actual_usable_points_B"] != config["equal_base"]["actual_usable_points_B"]):
            raise ValueError("route, target, or base identity mismatch")

        binary = PolynomialRing(GF(2), "z")
        z = binary.gen()
        modulus = z**131 + z**13 + z**2 + z + 1
        if not modulus.is_irreducible():
            raise ArithmeticError("field modulus is reducible")
        field = GF(2**131, "z", modulus=modulus)
        powers = [field.gen()**index for index in range(131)]

        def decode(word: int):
            word = int(word)
            return sum((powers[index] for index in range(word.bit_length())
                        if (word >> index) & 1), field.zero())

        def encode(value) -> int:
            return sum(int(bit) << index for index, bit in
                       enumerate(value.polynomial().list()))

        def point_words(point) -> list[int]:
            if point.is_zero():
                raise ArithmeticError("unexpected identity point")
            return [encode(point[0]), encode(point[1])]

        def unpack_point(curve, words: list[int]):
            point = curve([decode(words[0]), decode(words[1])])
            if point_words(point) != words:
                raise ArithmeticError("public point encoding changed")
            return point

        def half_trace(value):
            if int(value.trace()) != 0:
                raise ArithmeticError("half-trace argument has trace one")
            term = total = value
            for _ in range(65):
                term = term**4
                total += term
            if total**2 + total != value:
                raise ArithmeticError("half trace did not solve the quadratic")
            return total

        progress["phase"] = "route"
        source = EllipticCurve(field, [1, 0, 0, 0, 1])
        ring = PolynomialRing(field, "X")
        forward_poly = ring([decode(word) for word in route["isogeny"][
            "forward_map"]["kernel_polynomial_coefficients"]])
        dual_poly = ring([decode(word) for word in route["isogeny"][
            "dual_map"]["kernel_polynomial_coefficients"]])
        forward = source.isogeny(forward_poly, check=True)
        descendant = forward.codomain()
        if [encode(value) for value in descendant.ainvs()] != route[
                "curve_nodes"]["target"]["coefficients_a1_a2_a3_a4_a6"]:
            raise ArithmeticError("constructed codomain differs from verified route")
        dual = descendant.isogeny(dual_poly, check=True)
        iso = dual.codomain().isomorphism_to(source)
        sign = ZZ(route["isogeny"]["dual_map"]["composition_sign"])
        if [encode(value) for value in iso.tuple()] != route[
                "isogeny"]["dual_map"]["isomorphism_tuple_to_source"]:
            raise ArithmeticError("dual route orientation changed")
        order = ZZ(config["subgroup_order"])
        inverse_degree = ZZ(263).inverse_mod(order)
        G = unpack_point(source, route["curve_nodes"]["source"]["generator_G"])
        H = unpack_point(descendant, route["curve_nodes"]["target"]["generator_G"])
        if (order*G != source(0) or order*H != descendant(0)
                or forward(G) != H or sign*iso(dual(H)) != 263*G):
            raise ArithmeticError("generator or route identity failed")
        route_seconds = time.perf_counter() - started
        check_resources()

        a4 = descendant.ainvs()[3]
        b = descendant.ainvs()[4] + a4*a4
        normalized = EllipticCurve(field, [1, 0, 0, 0, b])
        alpha = b**(1 << 129)
        if alpha**4 != b:
            raise ArithmeticError("codomain fourth-root normalization failed")
        w24 = [field.gen()**j + (field.gen()**j).trace() for j in range(1, 25)]
        normal_basis = [decode(int(word)) for word in parent["normal_orbit_polynomial_words"]]
        if len(normal_basis) != 131 or sum(normal_basis, field.zero()) != 1:
            raise ArithmeticError("normal-basis source changed")

        def project_w24(mask: int, curve, fourth_root, coefficient):
            w = sum((w24[index] for index in range(24) if mask & (1 << index)),
                    field.zero())
            if not w or int(w.trace()) != 0:
                raise ArithmeticError("W24 mask left trace-zero domain")
            u = half_trace(w)
            x = fourth_root*(1 + 1/u)
            rhs = x + coefficient/(x*x)
            point = 4*curve([x, x*half_trace(rhs)])
            if point.is_zero() or order*point != curve(0):
                raise ArithmeticError("W24 projection left prime subgroup")
            return point

        def project_normal4(mask: int):
            w = sum((normal_basis[index] for index in range(131)
                     if mask & (1 << index)), field.zero())
            u = half_trace(w)
            x = 1 + 1/u
            point = 4*source([x, x*half_trace(x + 1/(x*x))])
            if point.is_zero() or order*point != source(0):
                raise ArithmeticError("normal4 projection left prime subgroup")
            return point

        progress["phase"] = "point_controls"
        controls = {"w24_source": [], "w24_descendant_native": [],
                    "normal4_source": []}
        control_started = time.perf_counter()
        for index, mask in zip(base["source"]["control_indices"],
                               base["source"]["control_masks"]):
            point = project_w24(mask, source, field.one(), field.one())
            image = forward(point)
            if inverse_degree*sign*iso(dual(image)) != point:
                raise ArithmeticError("source W24 route round trip failed")
            controls["w24_source"].append({"index": index, "mask": mask,
                                           "source": point_words(point),
                                           "transported": point_words(image)})
            progress["controls_completed"] += 1
            if progress["controls_completed"] % 16 == 0:
                check_resources()
        for index, mask in zip(base["descendant_native"]["control_indices"],
                               base["descendant_native"]["control_masks"]):
            temporary = project_w24(mask, normalized, alpha, b)
            native = descendant([temporary[0], temporary[1] + a4])
            pullback = inverse_degree*sign*iso(dual(native))
            if order*native != descendant(0) or forward(pullback) != native:
                raise ArithmeticError("native W24 route round trip failed")
            controls["w24_descendant_native"].append({
                "index": index, "mask": mask,
                "descendant_native": point_words(native),
                "pullback": point_words(pullback)})
            progress["controls_completed"] += 1
            if progress["controls_completed"] % 16 == 0:
                check_resources()
        for index, word in zip(normal4["sample_indices"], normal4["sample_masks"]):
            mask = int(word)
            point = project_normal4(mask)
            image = forward(point)
            if inverse_degree*sign*iso(dual(image)) != point:
                raise ArithmeticError("normal4 route round trip failed")
            controls["normal4_source"].append({"index": index,
                                                "normal_mask_decimal": word,
                                                "source": point_words(point),
                                                "transported": point_words(image)})
            progress["controls_completed"] += 1
            if progress["controls_completed"] % 16 == 0:
                check_resources()
        if [len(controls[name]) for name in controls] != [64, 64, 128]:
            raise ArithmeticError("wrong fixed point-control counts")
        control_seconds = time.perf_counter() - control_started
        print("point controls checked", progress["controls_completed"],
              round(control_seconds, 3), flush=True)

        progress["phase"] = "primary_target"
        primary_row = primary["targets"][0]
        primary_source = unpack_point(source, primary_row["source"])
        primary_descendant = unpack_point(descendant, primary_row["descendant"])
        primary_scalar = ZZ(fixtures["accepted_scalars"][0])
        if (primary_scalar*G != primary_source
                or primary_scalar*H != primary_descendant
                or forward(primary_source) != primary_descendant
                or inverse_degree*sign*iso(dual(primary_descendant))
                != primary_source):
            raise ArithmeticError("primary target replay failed")
        primary_binding = {"workload_id": primary["workload_id"],
                           "primary_workload_sha256": sha256(ROOT / config[
                               "bound_inputs"]["q1420_primary_workload"]["path"]),
                           "source": primary_row["source"],
                           "descendant": primary_row["descendant"],
                           "scalar_replayed_for_verification": True}

        progress["phase"] = "ordinary_queries"
        query_started = time.perf_counter()
        pair_hash = hashlib.sha256()
        source_hash = hashlib.sha256()
        descendant_hash = hashlib.sha256()
        prefix = {}
        first = []
        scalar_hash = hashlib.sha256()
        for index, (counter, scalar) in enumerate(scalar_sequence(
                scalars["scalar_domain"], int(order), args.count)):
            value = ZZ(scalar)
            point = value*G
            image = value*H
            source_words = point_words(point)
            descendant_words = point_words(image)
            source_bytes = b"".join(int(word).to_bytes(POINT_BYTES, "little")
                                    for word in source_words)
            descendant_bytes = b"".join(int(word).to_bytes(POINT_BYTES, "little")
                                        for word in descendant_words)
            source_hash.update(source_bytes)
            descendant_hash.update(descendant_bytes)
            pair_hash.update(source_bytes + descendant_bytes)
            scalar_hash.update(int(scalar).to_bytes(17, "big"))
            if index < 16:
                if forward(point) != image or inverse_degree*sign*iso(dual(image)) != point:
                    raise ArithmeticError("ordinary pilot route mismatch")
                first.append({"index": index, "counter": counter,
                              "source": source_words, "descendant": descendant_words})
            if index + 1 in config["ordinary_relation_queries"]["frozen_prefix_lengths"]:
                prefix[str(index + 1)] = {
                    "source_sha256": source_hash.hexdigest(),
                    "descendant_sha256": descendant_hash.hexdigest(),
                    "paired_sha256": pair_hash.hexdigest(),
                    "scalar_sha256": scalar_hash.hexdigest()}
            progress["queries_completed"] = index + 1
            if (index + 1) % 256 == 0:
                check_resources()
                print("public queries", index + 1, flush=True)
        if args.count == 65536 and scalar_hash.hexdigest() != scalars[
                "scalar_stream_sha256"]:
            raise ArithmeticError("full scalar stream changed")
        check_resources()
        receipt = {"schema": "ecc2k130-normal4-equalb-public-points-v1",
                   "status": "PASS_PUBLIC_POINTS_AND_ROUTE_CONTROLS",
                   "candidate_id": None, "count": args.count,
                   "point_encoding": "each affine x,y as 17-byte little-endian polynomial-basis integers; source x,y then descendant x,y",
                   "prefix_digests": prefix,
                   "first_16_public_queries": first,
                   "point_controls": controls,
                   "primary_target": primary_binding,
                   "config_sha256": config_sha,
                   "base_prefixes_sha256": sha256(base_path),
                   "query_scalars_sha256": sha256(scalar_path),
                   "input_verification_sha256": sha256(replay_path),
                   "route_manifest_sha256": sha256(route_path),
                   "runtime_info_sha256": sha256(args.runtime_info),
                   "producer_sha256": sha256(Path(__file__)),
                   "route_setup_wall_seconds": route_seconds,
                   "point_controls_wall_seconds": control_seconds,
                   "ordinary_query_wall_seconds": time.perf_counter() - query_started,
                   "wall_seconds": time.perf_counter() - started,
                   "cpu_seconds": time.process_time() - cpu_started,
                   "peak_rss_bytes": peak_bytes(),
                   "host_cpu_isolation": "unverified",
                   "ordinary_pdp_attempts": 0,
                   "verified_novel_rank": None}
        save_new(args.out_dir / "public_points.json", receipt)
        print(receipt["status"], args.count, prefix[str(args.count)][
            "paired_sha256"], flush=True)
    except Exception as exc:
        save_new(args.out_dir / "failure.json", {
            "schema": "ecc2k130-normal4-equalb-point-failure-v1",
            "status": "PRODUCER_FAILURE", "error_type": type(exc).__name__,
            "error": str(exc), "progress": progress,
            "config_sha256": sha256(CONFIG),
            "producer_sha256": sha256(Path(__file__)),
            "wall_seconds": time.perf_counter() - started,
            "cpu_seconds": time.process_time() - cpu_started,
            "peak_rss_bytes": peak_bytes()})
        raise


if __name__ == "__main__":
    main()
