#!/usr/bin/env sage -python
"""Independently replay equal-B controls and public queries with batched sums."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ
from sage.schemes.elliptic_curves.binary_batch import add_pairs


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CONFIG = HERE / "CONFIG.json"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def peak_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value * 1024


def write_new(path: Path, value: dict) -> None:
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def accepted_scalars(domain: str, order: int, count: int):
    """Replay the frozen counter law without importing the input producer."""
    known = set()
    counter = 0
    while len(known) < count:
        payload = domain.encode("utf-8") + b"\x00" + counter.to_bytes(8, "big")
        value = int.from_bytes(hashlib.sha256(payload).digest()[:17], "big")
        value &= (1 << 130) - 1
        current = counter
        counter += 1
        if not 0 < value < order or value in known:
            continue
        known.add(value)
        yield current, value


def sample_indices(domain: str, count: int, sample_count: int) -> list[int]:
    selected = set(range(min(16, count)))
    counter = 0
    while len(selected) < min(count, sample_count + 16):
        payload = (domain + "|" + str(counter)).encode("utf-8")
        selected.add(int.from_bytes(hashlib.sha256(payload).digest(), "big") % count)
        counter += 1
    return sorted(selected)


def fixed_base_batch(curve, generator, scalars: list[int], check_resource):
    """Sum independent precomputed binary powers in 130 batched passes."""
    zero = curve(0)
    powers = [generator]
    for _ in range(129):
        powers.append(2 * powers[-1])
    accumulators = [zero] * len(scalars)
    for bit, power in enumerate(powers):
        accumulators = add_pairs(curve, (
            (point, power if scalar & (1 << bit) else zero)
            for point, scalar in zip(accumulators, scalars)))
        if bit % 8 == 0:
            check_resource()
    return accumulators


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--producer", type=Path, required=True)
    parser.add_argument("--runtime-info", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("refusing to overwrite a point verification receipt")
    started = time.perf_counter()
    cpu_started = time.process_time()
    progress = {"phase": "preflight", "controls_completed": 0,
                "batch_curves_completed": 0, "queries_hashed": 0}
    config = read(CONFIG)
    cap = config["input_producer_envelope"]

    def check_resource() -> None:
        if time.perf_counter() - started > cap["wall_seconds"]:
            raise TimeoutError("independent point replay wall cap exceeded")
        if peak_bytes() > cap["peak_rss_bytes"]:
            raise MemoryError("independent point replay RSS cap exceeded")

    try:
        producer = read(args.producer)
        runtime = read(args.runtime_info)
        base_path = args.input_dir / "base_prefixes.json"
        scalar_path = args.input_dir / "query_scalars.json"
        replay_path = args.input_dir / "input_verification.json"
        base = read(base_path)
        scalar_receipt = read(scalar_path)
        input_replay = read(replay_path)
        if (runtime.get("status") != "verified"
                or producer["status"] != "PASS_PUBLIC_POINTS_AND_ROUTE_CONTROLS"
                or producer["config_sha256"] != digest(CONFIG)
                or producer["producer_sha256"] != digest(HERE / "point_stage_sage.py")
                or producer["base_prefixes_sha256"] != digest(base_path)
                or producer["query_scalars_sha256"] != digest(scalar_path)
                or producer["input_verification_sha256"] != digest(replay_path)
                or input_replay["status"] != "PASS_INDEPENDENT_MASK_AND_SCALAR_REPLAY"):
            raise ValueError("point producer or frozen inputs changed")
        count = producer["count"]
        if count not in (16, 256, 65536):
            raise ValueError("unfrozen query count")
        route_path = ROOT / config["bound_inputs"]["route_manifest"]["path"]
        route = read(route_path)
        normal4 = read(ROOT / config["bound_inputs"]["q1421_producer"]["path"])
        primary = read(ROOT / config["bound_inputs"]["q1420_primary_workload"]["path"])
        fixtures = read(ROOT / "experiments/ecc2k130-263-equal-w24-workload-20261005/target_fixtures.json")
        parent = read(ROOT / "experiments/ecc2k130-w24-normal-barrel-20261006/runs/R2/result.json")
        if (digest(route_path) != producer["route_manifest_sha256"]
                or primary["workload_id"] != producer["primary_target"]["workload_id"]
                or normal4["actual_usable_points_B"] != base["source"][
                    "actual_usable_points_B"]):
            raise ValueError("route or base identity mismatch")

        progress["phase"] = "field_and_route"
        f2 = GF(2)
        ring2 = PolynomialRing(f2, "t")
        t = ring2.gen()
        modulus = t**131 + t**13 + t**2 + t + 1
        if not modulus.is_irreducible():
            raise ArithmeticError("reducible field modulus")
        field = GF(2**131, "t", modulus=modulus)
        polynomial_powers = [field.gen()**bit for bit in range(131)]

        def from_integer(value: int):
            value = int(value)
            return sum((polynomial_powers[bit] for bit in range(value.bit_length())
                        if value & (1 << bit)), field.zero())

        def to_integer(value) -> int:
            return sum(int(bit) << index for index, bit in
                       enumerate(value.polynomial().list()))

        def coordinates(point) -> list[int]:
            if point.is_zero():
                raise ArithmeticError("identity public point")
            return [to_integer(point[0]), to_integer(point[1])]

        def point_on(curve, words):
            point = curve([from_integer(words[0]), from_integer(words[1])])
            if coordinates(point) != words:
                raise ArithmeticError("noncanonical public point encoding")
            return point

        def halftrace(value):
            result = field.zero()
            term = value
            for _ in range(66):
                result += term
                term = term**4
            if result*result + result != value:
                raise ArithmeticError("halftrace equation failed")
            return result

        source = EllipticCurve(field, [1, 0, 0, 0, 1])
        polyring = PolynomialRing(field, "Y")
        forward_kernel = polyring([from_integer(c) for c in route[
            "isogeny"]["forward_map"]["kernel_polynomial_coefficients"]])
        dual_kernel = polyring([from_integer(c) for c in route[
            "isogeny"]["dual_map"]["kernel_polynomial_coefficients"]])
        phi = source.isogeny(forward_kernel, check=True)
        descendant = phi.codomain()
        if [to_integer(a) for a in descendant.ainvs()] != route[
                "curve_nodes"]["target"]["coefficients_a1_a2_a3_a4_a6"]:
            raise ArithmeticError("wrong oriented codomain")
        dual = descendant.isogeny(dual_kernel, check=True)
        back_iso = dual.codomain().isomorphism_to(source)
        sign = ZZ(route["isogeny"]["dual_map"]["composition_sign"])
        if [to_integer(a) for a in back_iso.tuple()] != route[
                "isogeny"]["dual_map"]["isomorphism_tuple_to_source"]:
            raise ArithmeticError("dual-map isomorphism changed")
        order = ZZ(config["subgroup_order"])
        inv_degree = ZZ(263).inverse_mod(order)
        G = point_on(source, route["curve_nodes"]["source"]["generator_G"])
        H = point_on(descendant, route["curve_nodes"]["target"]["generator_G"])
        if phi(G) != H or sign*back_iso(dual(H)) != 263*G:
            raise ArithmeticError("generator transport identity failed")
        a4 = descendant.ainvs()[3]
        b = descendant.ainvs()[4] + a4*a4
        normalized = EllipticCurve(field, [1, 0, 0, 0, b])
        Hn = normalized([H[0], H[1] + a4])
        if order*G != source(0) or order*Hn != normalized(0):
            raise ArithmeticError("generator subgroup order failed")
        fourth_root = b**(1 << 129)
        if fourth_root**4 != b:
            raise ArithmeticError("codomain normalization failed")
        w24_basis = [field.gen()**j + (field.gen()**j).trace()
                     for j in range(1, 25)]
        normal_basis = [from_integer(int(w)) for w in parent[
            "normal_orbit_polynomial_words"]]
        if len(normal_basis) != 131 or sum(normal_basis, field.zero()) != 1:
            raise ArithmeticError("normal basis changed")

        def project_w24(mask, curve, root, coefficient):
            w = sum((w24_basis[j] for j in range(24) if mask & (1 << j)),
                    field.zero())
            u = halftrace(w)
            x = root * (1 + 1/u)
            point = 4*curve([x, x*halftrace(x + coefficient/(x*x))])
            if point.is_zero() or order*point != curve(0):
                raise ArithmeticError("W24 subgroup projection failed")
            return point

        def project_normal4(mask):
            positions = [j for j in range(131) if mask & (1 << j)]
            if len(positions) != 4:
                raise ArithmeticError("normal4 mask changed")
            w = sum((normal_basis[j] for j in positions), field.zero())
            u = halftrace(w)
            x = 1 + 1/u
            point = 4*source([x, x*halftrace(x + 1/(x*x))])
            if point.is_zero() or order*point != source(0):
                raise ArithmeticError("normal4 subgroup projection failed")
            return point

        progress["phase"] = "point_controls"
        controls = producer["point_controls"]
        if ([len(controls[name]) for name in (
                "w24_source", "w24_descendant_native", "normal4_source")]
                != [64, 64, 128]):
            raise ValueError("producer point-control count changed")
        for row, index, mask in zip(controls["w24_source"],
                                    base["source"]["control_indices"],
                                    base["source"]["control_masks"]):
            point = project_w24(mask, source, field.one(), field.one())
            image = phi(point)
            if (row["index"] != index or row["mask"] != mask
                    or row["source"] != coordinates(point)
                    or row["transported"] != coordinates(image)
                    or inv_degree*sign*back_iso(dual(image)) != point):
                raise ArithmeticError("source W24 point control mismatch")
            progress["controls_completed"] += 1
            if progress["controls_completed"] % 16 == 0:
                check_resource()
        for row, index, mask in zip(controls["w24_descendant_native"],
                                    base["descendant_native"]["control_indices"],
                                    base["descendant_native"]["control_masks"]):
            point = project_w24(mask, normalized, fourth_root, b)
            native = descendant([point[0], point[1] + a4])
            pullback = inv_degree*sign*back_iso(dual(native))
            if (row["index"] != index or row["mask"] != mask
                    or row["descendant_native"] != coordinates(native)
                    or row["pullback"] != coordinates(pullback)
                    or phi(pullback) != native):
                raise ArithmeticError("native W24 point control mismatch")
            progress["controls_completed"] += 1
            if progress["controls_completed"] % 16 == 0:
                check_resource()
        for row, index, mask in zip(controls["normal4_source"],
                                    normal4["sample_indices"],
                                    normal4["sample_masks"]):
            point = project_normal4(int(mask))
            image = phi(point)
            if (row["index"] != index or row["normal_mask_decimal"] != mask
                    or row["source"] != coordinates(point)
                    or row["transported"] != coordinates(image)
                    or inv_degree*sign*back_iso(dual(image)) != point):
                raise ArithmeticError("normal4 point control mismatch")
            progress["controls_completed"] += 1
            if progress["controls_completed"] % 16 == 0:
                check_resource()
        print("independent point controls", progress["controls_completed"], flush=True)

        progress["phase"] = "primary_target"
        target = primary["targets"][0]
        scalar = ZZ(fixtures["accepted_scalars"][0])
        source_target = point_on(source, target["source"])
        descendant_target = point_on(descendant, target["descendant"])
        if (primary["workload_id"] != producer["primary_target"]["workload_id"]
                or scalar*G != source_target or scalar*H != descendant_target
                or phi(source_target) != descendant_target
                or inv_degree*sign*back_iso(dual(descendant_target))
                != source_target):
            raise ArithmeticError("primary target replay mismatch")

        progress["phase"] = "scalar_law"
        stream = list(accepted_scalars(scalar_receipt["scalar_domain"],
                                       int(order), count))
        scalars = [value for _, value in stream]
        scalar_hash = hashlib.sha256(b"".join(
            value.to_bytes(17, "big") for value in scalars)).hexdigest()
        if count == 65536 and scalar_hash != scalar_receipt["scalar_stream_sha256"]:
            raise ArithmeticError("full scalar stream mismatch")
        if [{"index": i, "counter": stream[i][0],
             "scalar_decimal": str(scalars[i])} for i in range(16)] != scalar_receipt[
                 "first_16_accepted"]:
            raise ArithmeticError("first 16 scalar fixtures mismatch")

        progress["phase"] = "source_batch"
        source_points = fixed_base_batch(source, G, scalars, check_resource)
        progress["batch_curves_completed"] = 1
        print("source batched powers complete", count, flush=True)
        progress["phase"] = "normalized_descendant_batch"
        normalized_points = fixed_base_batch(normalized, Hn, scalars,
                                             check_resource)
        progress["batch_curves_completed"] = 2
        print("descendant batched powers complete", count, flush=True)

        progress["phase"] = "point_digest"
        source_digest = hashlib.sha256()
        descendant_digest = hashlib.sha256()
        paired_digest = hashlib.sha256()
        scalar_digest = hashlib.sha256()
        prefix = {}
        first = producer["first_16_public_queries"]
        if len(first) != 16:
            raise ArithmeticError("producer first-16 point controls missing")
        samples = sample_indices("ecc2k130-normal4-equalb-m6-query-map-sample-v1",
                                 count, 64)
        sample_set = set(samples)
        direct_checks = 0
        for index, (point, normalized_point) in enumerate(zip(
                source_points, normalized_points)):
            source_words = coordinates(point)
            descendant_words = [to_integer(normalized_point[0]),
                                to_integer(normalized_point[1] + a4)]
            source_bytes = b"".join(word.to_bytes(17, "little")
                                    for word in source_words)
            descendant_bytes = b"".join(word.to_bytes(17, "little")
                                        for word in descendant_words)
            source_digest.update(source_bytes)
            descendant_digest.update(descendant_bytes)
            paired_digest.update(source_bytes + descendant_bytes)
            scalar_digest.update(scalars[index].to_bytes(17, "big"))
            if index < 16 and (first[index]["index"] != index
                               or first[index]["counter"] != stream[index][0]
                               or first[index]["source"] != source_words
                               or first[index]["descendant"] != descendant_words):
                raise ArithmeticError("first-16 public point mismatch")
            if index in sample_set:
                native = descendant([normalized_point[0], normalized_point[1] + a4])
                if (point != ZZ(scalars[index])*G
                        or native != ZZ(scalars[index])*H
                        or phi(point) != native
                        or inv_degree*sign*back_iso(dual(native)) != point):
                    raise ArithmeticError(f"direct query map sample failed at {index}")
                direct_checks += 1
            if index + 1 in (16, 256, 65536):
                prefix[str(index + 1)] = {
                    "source_sha256": source_digest.hexdigest(),
                    "descendant_sha256": descendant_digest.hexdigest(),
                    "paired_sha256": paired_digest.hexdigest(),
                    "scalar_sha256": scalar_digest.hexdigest()}
            progress["queries_hashed"] = index + 1
            if (index + 1) % 1024 == 0:
                check_resource()
        if prefix != producer["prefix_digests"]:
            raise ArithmeticError("independent public-point digest mismatch")
        check_resource()
        receipt = {"schema": "ecc2k130-normal4-equalb-point-verification-v1",
                   "status": "PASS_INDEPENDENT_PUBLIC_POINT_REPLAY",
                   "count": count, "candidate_id": None,
                   "point_control_counts": {name: len(values)
                                            for name, values in controls.items()},
                   "direct_scalar_and_route_checks": direct_checks,
                   "direct_sample_indices": samples,
                   "prefix_digests": prefix,
                   "primary_target_workload_id": primary["workload_id"],
                   "producer_result_sha256": digest(args.producer),
                   "producer_source_sha256": digest(HERE / "point_stage_sage.py"),
                   "verifier_sha256": digest(Path(__file__)),
                   "runtime_info_sha256": digest(args.runtime_info),
                   "config_sha256": digest(CONFIG),
                   "wall_seconds": time.perf_counter() - started,
                   "cpu_seconds": time.process_time() - cpu_started,
                   "peak_rss_bytes": peak_bytes(),
                   "host_cpu_isolation": "unverified",
                   "ordinary_pdp_attempts": 0,
                   "verified_novel_rank": None}
        write_new(args.out, receipt)
        print(receipt["status"], count, prefix[str(count)]["paired_sha256"],
              flush=True)
    except Exception as exc:
        write_new(args.out, {
            "schema": "ecc2k130-normal4-equalb-point-verification-failure-v1",
            "status": "VERIFICATION_FAILURE",
            "error_type": type(exc).__name__, "error": str(exc),
            "progress": progress, "producer_result_sha256": digest(args.producer),
            "verifier_sha256": digest(Path(__file__)),
            "wall_seconds": time.perf_counter() - started,
            "cpu_seconds": time.process_time() - cpu_started,
            "peak_rss_bytes": peak_bytes()})
        raise


if __name__ == "__main__":
    main()
