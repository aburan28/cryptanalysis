#!/usr/bin/env sage -python
"""Replay the full public-query point stream by binary-power batch sums."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ

from verify_points_sage import accepted_scalars, fixed_base_batch, sample_indices


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CONFIG = HERE / "CONFIG.json"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1 << 20), b""):
            h.update(part)
    return h.hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def write_new(path: Path, result: dict) -> None:
    with path.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")


def peak_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value * 1024


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--pilot-result", type=Path, required=True)
    parser.add_argument("--pilot-verification", type=Path, required=True)
    parser.add_argument("--batch-result", type=Path, required=True)
    parser.add_argument("--runtime-info", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("refusing to overwrite a full point verification")
    started = time.perf_counter()
    cpu_started = time.process_time()
    progress = {"phase": "preflight", "batch_curves_completed": 0,
                "queries_hashed": 0}
    config = read(CONFIG)
    cap = config["input_producer_envelope"]

    def check_resource() -> None:
        if time.perf_counter() - started > cap["wall_seconds"]:
            raise TimeoutError("independent full point replay wall cap exceeded")
        if peak_bytes() > cap["peak_rss_bytes"]:
            raise MemoryError("independent full point replay RSS cap exceeded")

    try:
        pilot = read(args.pilot_result)
        pilot_replay = read(args.pilot_verification)
        batch = read(args.batch_result)
        runtime = read(args.runtime_info)
        scalar_path = args.input_dir / "query_scalars.json"
        scalar_receipt = read(scalar_path)
        if (runtime.get("status") != "verified"
                or pilot["status"] != "PASS_PUBLIC_POINTS_AND_ROUTE_CONTROLS"
                or pilot["count"] != 256
                or pilot_replay["status"] != "PASS_INDEPENDENT_PUBLIC_POINT_REPLAY"
                or pilot_replay["count"] != 256
                or pilot_replay["producer_result_sha256"] != sha(args.pilot_result)
                or batch["status"] != "PASS_BATCH_PUBLIC_POINT_STREAM"
                or batch["count"] != 65536
                or batch["pilot_result_sha256"] != sha(args.pilot_result)
                or batch["pilot_verification_sha256"] != sha(args.pilot_verification)
                or batch["producer_sha256"] != sha(HERE / "batch_points_sage.py")
                or batch["query_scalars_sha256"] != sha(scalar_path)
                or batch["config_sha256"] != sha(CONFIG)):
            raise ValueError("full batch or independently verified pilot changed")
        for name, item in config["bound_inputs"].items():
            if sha(ROOT / item["path"]) != item["sha256"]:
                raise ValueError(f"bound source changed: {name}")
        route_path = ROOT / config["bound_inputs"]["route_manifest"]["path"]
        route = read(route_path)
        primary = read(ROOT / config["bound_inputs"]["q1420_primary_workload"]["path"])
        fixtures = read(ROOT / "experiments/ecc2k130-263-equal-w24-workload-20261005/target_fixtures.json")
        if (batch["route_manifest_sha256"] != sha(route_path)
                or batch["primary_target_workload_id"] != primary["workload_id"]
                or primary["workload_id"] != pilot["primary_target"]["workload_id"]):
            raise ValueError("route or primary workload identity changed")

        progress["phase"] = "field_and_route"
        f2 = GF(2)
        binary = PolynomialRing(f2, "z")
        z = binary.gen()
        modulus = z**131 + z**13 + z**2 + z + 1
        if not modulus.is_irreducible():
            raise ArithmeticError("reducible field modulus")
        field = GF(2**131, "z", modulus=modulus)
        powers = [field.gen()**bit for bit in range(131)]

        def decode(number: int):
            number = int(number)
            return sum((powers[bit] for bit in range(number.bit_length())
                        if number & (1 << bit)), field.zero())

        def encode(value) -> int:
            return sum(int(bit) << j for j, bit in
                       enumerate(value.polynomial().list()))

        def point_on(curve, words):
            point = curve([decode(words[0]), decode(words[1])])
            if [encode(point[0]), encode(point[1])] != words:
                raise ArithmeticError("noncanonical public point")
            return point

        source = EllipticCurve(field, [1, 0, 0, 0, 1])
        ring = PolynomialRing(field, "Y")
        forward_kernel = ring([decode(c) for c in route["isogeny"][
            "forward_map"]["kernel_polynomial_coefficients"]])
        dual_kernel = ring([decode(c) for c in route["isogeny"][
            "dual_map"]["kernel_polynomial_coefficients"]])
        forward = source.isogeny(forward_kernel, check=True)
        descendant = forward.codomain()
        if [encode(c) for c in descendant.ainvs()] != route[
                "curve_nodes"]["target"]["coefficients_a1_a2_a3_a4_a6"]:
            raise ArithmeticError("codomain changed")
        dual = descendant.isogeny(dual_kernel, check=True)
        iso = dual.codomain().isomorphism_to(source)
        sign = ZZ(route["isogeny"]["dual_map"]["composition_sign"])
        if [encode(c) for c in iso.tuple()] != route[
                "isogeny"]["dual_map"]["isomorphism_tuple_to_source"]:
            raise ArithmeticError("dual orientation changed")
        order = ZZ(config["subgroup_order"])
        inv_degree = ZZ(263).inverse_mod(order)
        G = point_on(source, route["curve_nodes"]["source"]["generator_G"])
        H = point_on(descendant, route["curve_nodes"]["target"]["generator_G"])
        if (order*G != source(0) or order*H != descendant(0)
                or forward(G) != H or sign*iso(dual(H)) != 263*G):
            raise ArithmeticError("generator or transport identity failed")
        a4 = descendant.ainvs()[3]
        b = descendant.ainvs()[4] + a4*a4
        normalized = EllipticCurve(field, [1, 0, 0, 0, b])
        Hn = normalized([H[0], H[1] + a4])
        if order*Hn != normalized(0):
            raise ArithmeticError("normalized generator order failed")
        target = primary["targets"][0]
        primary_scalar = ZZ(fixtures["accepted_scalars"][0])
        P = point_on(source, target["source"])
        Q = point_on(descendant, target["descendant"])
        if (primary_scalar*G != P or primary_scalar*H != Q
                or forward(P) != Q or inv_degree*sign*iso(dual(Q)) != P):
            raise ArithmeticError("primary target binding failed")
        check_resource()

        progress["phase"] = "scalar_stream"
        stream = list(accepted_scalars(scalar_receipt["scalar_domain"],
                                       int(order), 65536))
        scalars = [value for _, value in stream]
        scalar_digest = hashlib.sha256(b"".join(
            value.to_bytes(17, "big") for value in scalars)).hexdigest()
        if scalar_digest != scalar_receipt["scalar_stream_sha256"]:
            raise ArithmeticError("full scalar stream digest changed")
        if [{"index": i, "counter": stream[i][0],
             "scalar_decimal": str(scalars[i])} for i in range(16)] != scalar_receipt[
                 "first_16_accepted"]:
            raise ArithmeticError("scalar fixture vector changed")

        progress["phase"] = "source_binary_power_batch"
        source_points = fixed_base_batch(source, G, scalars, check_resource)
        progress["batch_curves_completed"] = 1
        print("independent source points", len(source_points), flush=True)
        progress["phase"] = "descendant_binary_power_batch"
        normalized_points = fixed_base_batch(normalized, Hn, scalars,
                                             check_resource)
        progress["batch_curves_completed"] = 2
        print("independent descendant points", len(normalized_points), flush=True)

        progress["phase"] = "point_digest_and_map_samples"
        src_hash = hashlib.sha256()
        dst_hash = hashlib.sha256()
        pair_hash = hashlib.sha256()
        scalar_prefix = hashlib.sha256()
        prefixes = {}
        sample = sample_indices(
            "ecc2k130-normal4-equalb-m6-independent-full-map-v1", 65536, 64)
        sample_set = set(sample)
        direct_checks = 0
        first = []
        for index, (point, normalized_point) in enumerate(zip(
                source_points, normalized_points)):
            if point.is_zero() or normalized_point.is_zero():
                raise ArithmeticError("zero query point")
            source_words = [encode(point[0]), encode(point[1])]
            descendant_words = [encode(normalized_point[0]),
                                encode(normalized_point[1] + a4)]
            src = b"".join(value.to_bytes(17, "little")
                           for value in source_words)
            dst = b"".join(value.to_bytes(17, "little")
                           for value in descendant_words)
            src_hash.update(src)
            dst_hash.update(dst)
            pair_hash.update(src + dst)
            scalar_prefix.update(scalars[index].to_bytes(17, "big"))
            if index < 16:
                first.append({"index": index, "counter": stream[index][0],
                              "source": source_words,
                              "descendant": descendant_words})
            if index in sample_set:
                native = descendant([normalized_point[0], normalized_point[1] + a4])
                if (point != ZZ(scalars[index])*G
                        or native != ZZ(scalars[index])*H
                        or forward(point) != native
                        or inv_degree*sign*iso(dual(native)) != point):
                    raise ArithmeticError(f"map sample mismatch at {index}")
                direct_checks += 1
            if index + 1 in (16, 256, 65536):
                prefixes[str(index + 1)] = {
                    "source_sha256": src_hash.hexdigest(),
                    "descendant_sha256": dst_hash.hexdigest(),
                    "paired_sha256": pair_hash.hexdigest(),
                    "scalar_sha256": scalar_prefix.hexdigest()}
            progress["queries_hashed"] = index + 1
            if (index + 1) % 1024 == 0:
                check_resource()
        if (prefixes != batch["prefix_digests"]
                or prefixes["16"] != pilot["prefix_digests"]["16"]
                or prefixes["256"] != pilot["prefix_digests"]["256"]
                or first != pilot["first_16_public_queries"]):
            raise ArithmeticError("full independent public-point digest mismatch")
        check_resource()
        result = {"schema": "ecc2k130-normal4-equalb-full-point-replay-v1",
                  "status": "PASS_INDEPENDENT_FULL_PUBLIC_POINT_STREAM",
                  "count": 65536, "candidate_id": None,
                  "prefix_digests": prefixes,
                  "direct_scalar_and_route_checks": direct_checks,
                  "direct_sample_indices": sample,
                  "primary_target_workload_id": primary["workload_id"],
                  "batch_result_sha256": sha(args.batch_result),
                  "pilot_result_sha256": sha(args.pilot_result),
                  "pilot_verification_sha256": sha(args.pilot_verification),
                  "producer_source_sha256": sha(HERE / "batch_points_sage.py"),
                  "helper_source_sha256": sha(HERE / "verify_points_sage.py"),
                  "verifier_sha256": sha(Path(__file__)),
                  "runtime_info_sha256": sha(args.runtime_info),
                  "config_sha256": sha(CONFIG),
                  "wall_seconds": time.perf_counter() - started,
                  "cpu_seconds": time.process_time() - cpu_started,
                  "peak_rss_bytes": peak_bytes(),
                  "host_cpu_isolation": "unverified",
                  "ordinary_pdp_attempts": 0,
                  "verified_novel_rank": None}
        write_new(args.out, result)
        print(result["status"], result["count"],
              prefixes["65536"]["paired_sha256"], flush=True)
    except Exception as exc:
        write_new(args.out, {
            "schema": "ecc2k130-normal4-equalb-full-point-replay-failure-v1",
            "status": "VERIFICATION_FAILURE",
            "error_type": type(exc).__name__, "error": str(exc),
            "progress": progress, "batch_result_sha256": sha(args.batch_result),
            "verifier_sha256": sha(Path(__file__)),
            "wall_seconds": time.perf_counter() - started,
            "cpu_seconds": time.process_time() - cpu_started,
            "peak_rss_bytes": peak_bytes()})
        raise


if __name__ == "__main__":
    main()
