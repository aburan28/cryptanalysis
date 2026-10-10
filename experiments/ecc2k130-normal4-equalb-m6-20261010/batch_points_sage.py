#!/usr/bin/env sage -python
"""Build the full frozen ordinary-query point stream by radix-16 batch sums."""

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

from freeze_inputs import scalar_sequence


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CONFIG = HERE / "CONFIG.json"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def save_new(path: Path, record: dict) -> None:
    with path.open("x") as stream:
        json.dump(record, stream, sort_keys=True, indent=2)
        stream.write("\n")


def peak_bytes() -> int:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak if sys.platform == "darwin" else peak * 1024


def select_samples(count: int) -> list[int]:
    indices = set(range(min(count, 16)))
    counter = 0
    while len(indices) < min(count, 80):
        digest = hashlib.sha256((
            "ecc2k130-normal4-equalb-m6-batch-map-sample-v1|" +
            str(counter)).encode("utf-8")).digest()
        indices.add(int.from_bytes(digest, "big") % count)
        counter += 1
    return sorted(indices)


def window_four_points(curve, generator, scalars: list[int], resource_check):
    """Sum 33 independently selected radix-16 fixed-base table entries."""
    zero = curve(0)
    tables = []
    position = generator
    for _ in range(33):
        row = [zero]
        for _ in range(15):
            row.append(row[-1] + position)
        tables.append(row)
        position = 16 * position
    points = [zero] * len(scalars)
    for window, row in enumerate(tables):
        shift = 4 * window
        points = add_pairs(curve, (
            (point, row[(scalar >> shift) & 15])
            for point, scalar in zip(points, scalars)))
        if window % 4 == 0:
            resource_check()
    return points


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--pilot-result", type=Path, required=True)
    parser.add_argument("--pilot-verification", type=Path, required=True)
    parser.add_argument("--runtime-info", type=Path, required=True)
    parser.add_argument("--count", type=int, choices=(256, 65536), required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.out_dir.exists():
        parser.error("refusing to overwrite a batch point run")
    args.out_dir.mkdir(parents=True)
    started = time.perf_counter()
    cpu_started = time.process_time()
    progress = {"phase": "preflight", "batch_curves_completed": 0,
                "queries_hashed": 0}
    config = load(CONFIG)
    cap = config["input_producer_envelope"]

    def check_resource() -> None:
        if time.perf_counter() - started > cap["wall_seconds"]:
            raise TimeoutError("batch point producer wall cap exceeded")
        if peak_bytes() > cap["peak_rss_bytes"]:
            raise MemoryError("batch point producer RSS cap exceeded")

    try:
        pilot = load(args.pilot_result)
        pilot_replay = load(args.pilot_verification)
        runtime = load(args.runtime_info)
        base_path = args.input_dir / "base_prefixes.json"
        scalar_path = args.input_dir / "query_scalars.json"
        input_replay_path = args.input_dir / "input_verification.json"
        scalar_receipt = load(scalar_path)
        if (runtime.get("status") != "verified"
                or pilot["status"] != "PASS_PUBLIC_POINTS_AND_ROUTE_CONTROLS"
                or pilot["count"] != 256
                or pilot["producer_sha256"] != sha(HERE / "point_stage_sage.py")
                or pilot["config_sha256"] != sha(CONFIG)
                or pilot["base_prefixes_sha256"] != sha(base_path)
                or pilot["query_scalars_sha256"] != sha(scalar_path)
                or pilot["input_verification_sha256"] != sha(input_replay_path)
                or pilot_replay["status"] != "PASS_INDEPENDENT_PUBLIC_POINT_REPLAY"
                or pilot_replay["count"] != 256
                or pilot_replay["producer_result_sha256"] != sha(args.pilot_result)
                or scalar_receipt["accepted_count"] != 65536):
            raise ValueError("pilot, independent replay, or input identity changed")
        route_path = ROOT / config["bound_inputs"]["route_manifest"]["path"]
        if sha(route_path) != config["bound_inputs"]["route_manifest"]["sha256"]:
            raise ValueError("verified route manifest changed")
        route = load(route_path)
        if route["route_id"] != config["route_id"]:
            raise ValueError("oriented route ID changed")
        samples = list(scalar_sequence(scalar_receipt["scalar_domain"],
                                       int(config["subgroup_order"]), args.count))
        counters = [counter for counter, _ in samples]
        scalars = [scalar for _, scalar in samples]
        stream_hash = hashlib.sha256(b"".join(
            scalar.to_bytes(17, "big") for scalar in scalars)).hexdigest()
        if args.count == 65536 and stream_hash != scalar_receipt[
                "scalar_stream_sha256"]:
            raise ArithmeticError("full scalar stream digest mismatch")
        check_resource()

        progress["phase"] = "field_and_route"
        f2 = GF(2)
        binary = PolynomialRing(f2, "t")
        t = binary.gen()
        modulus = t**131 + t**13 + t**2 + t + 1
        if not modulus.is_irreducible():
            raise ArithmeticError("field modulus changed")
        field = GF(2**131, "t", modulus=modulus)
        powers = [field.gen()**j for j in range(131)]

        def decode(number: int):
            number = int(number)
            return sum((powers[j] for j in range(number.bit_length())
                        if number & (1 << j)), field.zero())

        def encode(value) -> int:
            return sum(int(bit) << j for j, bit in
                       enumerate(value.polynomial().list()))

        def point_words(point) -> list[int]:
            if point.is_zero():
                raise ArithmeticError("unexpected zero query point")
            return [encode(point[0]), encode(point[1])]

        source = EllipticCurve(field, [1, 0, 0, 0, 1])
        poly = PolynomialRing(field, "X")
        kernel = poly([decode(c) for c in route["isogeny"][
            "forward_map"]["kernel_polynomial_coefficients"]])
        forward = source.isogeny(kernel, check=True)
        descendant = forward.codomain()
        if [encode(a) for a in descendant.ainvs()] != route[
                "curve_nodes"]["target"]["coefficients_a1_a2_a3_a4_a6"]:
            raise ArithmeticError("constructed codomain changed")
        G = source([decode(c) for c in route["curve_nodes"]["source"][
            "generator_G"]])
        H = descendant([decode(c) for c in route["curve_nodes"]["target"][
            "generator_G"]])
        if forward(G) != H:
            raise ArithmeticError("forward generator transport failed")
        a4 = descendant.ainvs()[3]
        b = descendant.ainvs()[4] + a4*a4
        normalized = EllipticCurve(field, [1, 0, 0, 0, b])
        Hn = normalized([H[0], H[1] + a4])
        order = ZZ(config["subgroup_order"])
        if order*G != source(0) or order*Hn != normalized(0):
            raise ArithmeticError("subgroup generator order failed")
        setup_seconds = time.perf_counter() - started
        check_resource()

        progress["phase"] = "source_radix16_batch"
        phase_started = time.perf_counter()
        source_points = window_four_points(source, G, scalars, check_resource)
        source_seconds = time.perf_counter() - phase_started
        progress["batch_curves_completed"] = 1
        print("source radix-16 batch", args.count, round(source_seconds, 3),
              flush=True)
        progress["phase"] = "descendant_radix16_batch"
        phase_started = time.perf_counter()
        normalized_points = window_four_points(normalized, Hn, scalars,
                                                check_resource)
        descendant_seconds = time.perf_counter() - phase_started
        progress["batch_curves_completed"] = 2
        print("descendant radix-16 batch", args.count,
              round(descendant_seconds, 3), flush=True)

        progress["phase"] = "digest_and_samples"
        phase_started = time.perf_counter()
        source_hash = hashlib.sha256()
        descendant_hash = hashlib.sha256()
        pair_hash = hashlib.sha256()
        scalar_hash = hashlib.sha256()
        prefixes = {}
        first = []
        sample_set = set(select_samples(args.count))
        direct_checks = 0
        for index, (point, normalized_point) in enumerate(zip(
                source_points, normalized_points)):
            source_words = point_words(point)
            descendant_words = [encode(normalized_point[0]),
                                encode(normalized_point[1] + a4)]
            src = b"".join(word.to_bytes(17, "little")
                           for word in source_words)
            dst = b"".join(word.to_bytes(17, "little")
                           for word in descendant_words)
            source_hash.update(src)
            descendant_hash.update(dst)
            pair_hash.update(src + dst)
            scalar_hash.update(scalars[index].to_bytes(17, "big"))
            if index < 16:
                first.append({"index": index, "counter": counters[index],
                              "source": source_words,
                              "descendant": descendant_words})
            if index in sample_set:
                native = descendant([normalized_point[0], normalized_point[1] + a4])
                if (point != ZZ(scalars[index])*G
                        or native != ZZ(scalars[index])*H
                        or forward(point) != native):
                    raise ArithmeticError(f"direct map check failed at {index}")
                direct_checks += 1
            if index + 1 in (16, 256, 65536):
                prefixes[str(index + 1)] = {
                    "source_sha256": source_hash.hexdigest(),
                    "descendant_sha256": descendant_hash.hexdigest(),
                    "paired_sha256": pair_hash.hexdigest(),
                    "scalar_sha256": scalar_hash.hexdigest()}
            progress["queries_hashed"] = index + 1
            if (index + 1) % 1024 == 0:
                check_resource()
        if (prefixes["16"] != pilot["prefix_digests"]["16"]
                or prefixes["256"] != pilot["prefix_digests"]["256"]
                or first != pilot["first_16_public_queries"]):
            raise ArithmeticError("batch prefix disagrees with direct pilot")
        digest_seconds = time.perf_counter() - phase_started
        check_resource()
        receipt = {"schema": "ecc2k130-normal4-equalb-batch-points-v1",
                   "status": "PASS_BATCH_PUBLIC_POINT_STREAM",
                   "candidate_id": None,
                   "count": args.count,
                   "point_encoding": pilot["point_encoding"],
                   "prefix_digests": prefixes,
                   "first_16_public_queries": first,
                   "direct_scalar_and_forward_map_checks": direct_checks,
                   "direct_sample_indices": sorted(sample_set),
                   "primary_target_workload_id": pilot["primary_target"]["workload_id"],
                   "config_sha256": sha(CONFIG),
                   "base_prefixes_sha256": sha(base_path),
                   "query_scalars_sha256": sha(scalar_path),
                   "input_verification_sha256": sha(input_replay_path),
                   "pilot_result_sha256": sha(args.pilot_result),
                   "pilot_verification_sha256": sha(args.pilot_verification),
                   "route_manifest_sha256": sha(route_path),
                   "runtime_info_sha256": sha(args.runtime_info),
                   "producer_sha256": sha(Path(__file__)),
                   "setup_wall_seconds": setup_seconds,
                   "source_batch_wall_seconds": source_seconds,
                   "descendant_batch_wall_seconds": descendant_seconds,
                   "digest_and_direct_checks_wall_seconds": digest_seconds,
                   "wall_seconds": time.perf_counter() - started,
                   "cpu_seconds": time.process_time() - cpu_started,
                   "peak_rss_bytes": peak_bytes(),
                   "host_cpu_isolation": "unverified",
                   "ordinary_pdp_attempts": 0,
                   "verified_novel_rank": None}
        save_new(args.out_dir / "public_points.json", receipt)
        print(receipt["status"], args.count,
              prefixes[str(args.count)]["paired_sha256"], flush=True)
    except Exception as exc:
        save_new(args.out_dir / "failure.json", {
            "schema": "ecc2k130-normal4-equalb-batch-point-failure-v1",
            "status": "PRODUCER_FAILURE", "error_type": type(exc).__name__,
            "error": str(exc), "progress": progress,
            "producer_sha256": sha(Path(__file__)),
            "config_sha256": sha(CONFIG),
            "wall_seconds": time.perf_counter() - started,
            "cpu_seconds": time.process_time() - cpu_started,
            "peak_rss_bytes": peak_bytes()})
        raise


if __name__ == "__main__":
    main()
