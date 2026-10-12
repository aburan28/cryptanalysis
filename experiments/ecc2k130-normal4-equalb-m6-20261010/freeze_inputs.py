#!/usr/bin/env python3
"""Freeze equal-B W24 prefixes and target-independent scalar query law."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import resource
import struct
import sys
import time

from preflight import CONFIG, ROOT, load_json, sha256, validate


def control_indices(domain: str, geometry: str, size: int, count: int) -> list[int]:
    selected: list[int] = []
    seen: set[int] = set()
    counter = 0
    while len(selected) < count:
        digest = hashlib.sha256(f"{domain}|{geometry}|{counter}".encode()).digest()
        index = int.from_bytes(digest, "big") % size
        if index not in seen:
            selected.append(index)
            seen.add(index)
        counter += 1
    return selected


def checked_resources(started: float, envelope: dict) -> None:
    if time.perf_counter() - started > envelope["wall_seconds"]:
        raise TimeoutError("input producer wall limit exceeded")
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    used = peak if sys.platform == "darwin" else peak * 1024
    if used > envelope["peak_rss_bytes"]:
        raise MemoryError("input producer RSS limit exceeded")


def scan_prefix(path: Path, archive: dict, selected_count: int,
                indices: list[int], started: float, envelope: dict) -> dict:
    if sha256(path) != archive["gzip_sha256"]:
        raise ValueError("compressed archive hash changed")
    full_digest = hashlib.sha256()
    prefix_digest = hashlib.sha256()
    requested = set(indices)
    masks: dict[int, int] = {}
    total = 0
    previous = -1
    last_selected = None
    first_excluded = None
    with gzip.open(path, "rb") as stream:
        while chunk := stream.read(1 << 20):
            checked_resources(started, envelope)
            if len(chunk) % 4:
                raise ValueError("truncated uint32 mask stream")
            full_digest.update(chunk)
            take = min(max(selected_count - total, 0), len(chunk) // 4)
            prefix_digest.update(chunk[:4 * take])
            for (mask,) in struct.iter_unpack("<I", chunk):
                if not 0 < mask < (1 << 24) or mask <= previous:
                    raise ValueError("mask stream is not strictly increasing")
                if total in requested:
                    masks[total] = mask
                if total == selected_count - 1:
                    last_selected = mask
                if total == selected_count:
                    first_excluded = mask
                total += 1
                previous = mask
    if (total != archive["full_signed_classes"]
            or full_digest.hexdigest() != archive["raw_sha256"]
            or len(masks) != len(indices)
            or last_selected is None or first_excluded is None):
        raise ValueError("full archive or selected prefix is incomplete")
    return {
        "full_signed_classes": total,
        "selected_signed_classes": selected_count,
        "actual_usable_points_B": 2 * selected_count,
        "full_raw_sha256": full_digest.hexdigest(),
        "selected_raw_sha256": prefix_digest.hexdigest(),
        "last_selected_mask": last_selected,
        "first_excluded_mask": first_excluded,
        "control_indices": indices,
        "control_masks": [masks[index] for index in indices],
    }


def scalar_sequence(domain: str, subgroup_order: int, count: int):
    seen: set[int] = set()
    accepted = 0
    counter = 0
    encoded_domain = domain.encode("utf-8")
    while accepted < count:
        if counter >= 1 << 64:
            raise OverflowError("query scalar counter exhausted")
        digest = hashlib.sha256(
            encoded_domain + b"\0" + counter.to_bytes(8, "big")
        ).digest()
        scalar = int.from_bytes(digest[:17], "big") & ((1 << 130) - 1)
        source_counter = counter
        counter += 1
        if scalar == 0 or scalar >= subgroup_order or scalar in seen:
            continue
        seen.add(scalar)
        accepted += 1
        yield source_counter, scalar


def freeze_queries(config: dict, started: float) -> dict:
    query_started = time.perf_counter()
    query_cpu_started = time.process_time()
    query = config["ordinary_relation_queries"]
    count = max(query["frozen_prefix_lengths"])
    stream_digest = hashlib.sha256()
    first: list[dict] = []
    counters_used = 0
    for index, (counter, scalar) in enumerate(scalar_sequence(
            query["scalar_domain"], int(config["subgroup_order"]), count)):
        if index % 1024 == 0:
            checked_resources(started, config["input_producer_envelope"])
        stream_digest.update(scalar.to_bytes(17, "big"))
        counters_used = counter + 1
        if index < min(query["frozen_prefix_lengths"]):
            first.append({"index": index, "counter": counter,
                          "scalar_decimal": str(scalar)})
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak = peak if sys.platform == "darwin" else peak * 1024
    return {
        "schema": "ecc2k130-normal4-equalb-query-scalars-v1",
        "status": "SCALARS_FROZEN_PENDING_PUBLIC_POINT_REPLAY",
        "accepted_count": count,
        "counters_used": counters_used,
        "prefix_lengths": query["frozen_prefix_lengths"],
        "scalar_domain": query["scalar_domain"],
        "scalar_stream_sha256": stream_digest.hexdigest(),
        "first_16_accepted": first,
        "primary_target_workload_id": config["primary_target"]["workload_id"],
        "public_point_stream_sha256": None,
        "config_sha256": sha256(CONFIG),
        "producer_sha256": sha256(Path(__file__)),
        "wall_seconds": time.perf_counter() - query_started,
        "cpu_seconds": time.process_time() - query_cpu_started,
        "process_peak_rss_bytes": peak,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.out_dir.exists():
        parser.error("refusing to overwrite an input run")
    started = time.perf_counter()
    started_cpu = time.process_time()
    config = load_json(CONFIG)
    args.out_dir.mkdir(parents=True)
    try:
        preflight = validate(config)
        selected_count = config["equal_base"]["signed_classes_each"]
        sample = config["point_controls"]
        bases = {}
        for geometry in ("source", "descendant_native"):
            archive = config["w24_archives"][geometry]
            indices = control_indices(sample["selection_domain"], geometry,
                                      selected_count,
                                      sample["w24_each_seed_geometry"])
            bases[geometry] = scan_prefix(
                ROOT / archive["path"], archive, selected_count, indices,
                started, config["input_producer_envelope"])
        if any(item["actual_usable_points_B"] !=
               config["equal_base"]["actual_usable_points_B"]
               for item in bases.values()):
            raise ArithmeticError("equal-B source/native count mismatch")
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        peak = peak if sys.platform == "darwin" else peak * 1024
        base_receipt = {
            "schema": "ecc2k130-normal4-equalb-prefixes-v1",
            "status": "MASK_PREFIXES_FROZEN_PENDING_SAGE_POINT_REPLAY",
            "candidate_id": None,
            "preflight": preflight,
            "source": bases["source"],
            "descendant_native": bases["descendant_native"],
            "normal4_rational_orbit_digest_sha256": load_json(
                ROOT / config["bound_inputs"]["q1421_producer"]["path"]
            )["rational_canonical_orbit_representatives_sha256"],
            "config_sha256": sha256(CONFIG),
            "producer_sha256": sha256(Path(__file__)),
            "wall_seconds": time.perf_counter() - started,
            "cpu_seconds": time.process_time() - started_cpu,
            "peak_rss_bytes": peak,
            "ordinary_pdp_attempts": 0,
            "verified_novel_rank": None,
        }
        query_receipt = freeze_queries(config, started)
        with (args.out_dir / "base_prefixes.json").open("x") as stream:
            json.dump(base_receipt, stream, indent=2, sort_keys=True)
            stream.write("\n")
        with (args.out_dir / "query_scalars.json").open("x") as stream:
            json.dump(query_receipt, stream, indent=2, sort_keys=True)
            stream.write("\n")
        print(base_receipt["status"], query_receipt["status"])
    except Exception as exc:
        with (args.out_dir / "failure.json").open("x") as stream:
            json.dump({"schema": "ecc2k130-normal4-equalb-input-failure-v1",
                       "status": "PRODUCER_FAILURE",
                       "error_type": type(exc).__name__, "error": str(exc),
                       "config_sha256": sha256(CONFIG),
                       "producer_sha256": sha256(Path(__file__)),
                       "wall_seconds": time.perf_counter() - started},
                      stream, indent=2, sort_keys=True)
            stream.write("\n")
        raise


if __name__ == "__main__":
    main()
