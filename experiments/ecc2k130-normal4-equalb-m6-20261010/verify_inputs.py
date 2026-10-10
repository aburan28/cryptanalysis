#!/usr/bin/env python3
"""Independently replay both selected mask streams and the scalar law."""

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


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CONFIG = HERE / "CONFIG.json"
BASE = HERE / "runs/R1/base_prefixes.json"
QUERIES = HERE / "runs/R1/query_scalars.json"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def unique_object(pairs):
    value = dict(pairs)
    if len(value) != len(pairs):
        raise ValueError("duplicate JSON key")
    return value


def load(path: Path):
    return json.loads(path.read_text(), object_pairs_hook=unique_object)


def peak_rss() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value * 1024


def check_envelope(started: float, config: dict) -> None:
    envelope = config["input_producer_envelope"]
    if time.perf_counter() - started > envelope["wall_seconds"]:
        raise TimeoutError("input replay wall cap exceeded")
    if peak_rss() > envelope["peak_rss_bytes"]:
        raise MemoryError("input replay RSS cap exceeded")


def selection_indices(domain: str, name: str, size: int, count: int):
    selected = []
    seen = set()
    counter = 0
    while len(selected) < count:
        encoded = f"{domain}|{name}|{counter}".encode("utf-8")
        position = int.from_bytes(hashlib.sha256(encoded).digest(), "big") % size
        if position not in seen:
            selected.append(position)
            seen.add(position)
        counter += 1
    return selected


def replay_archive(name: str, config: dict, receipt: dict, started: float):
    archive = config["w24_archives"][name]
    row = receipt[name]
    path = ROOT / archive["path"]
    if digest(path) != archive["gzip_sha256"]:
        raise ValueError(name + " gzip hash changed")
    selected_count = config["equal_base"]["signed_classes_each"]
    controls = selection_indices(config["point_controls"]["selection_domain"],
                                 name, selected_count,
                                 config["point_controls"]["w24_each_seed_geometry"])
    if controls != row["control_indices"]:
        raise ArithmeticError(name + " control selection changed")
    wanted = set(controls)
    found = {}
    raw_hash = hashlib.sha256()
    prefix_hash = hashlib.sha256()
    previous = 0
    total = 0
    last = None
    excluded = None
    with gzip.open(path, "rb") as stream:
        while data := stream.read(1 << 20):
            check_envelope(started, config)
            if len(data) % 4:
                raise ValueError(name + " raw mask stream is truncated")
            raw_hash.update(data)
            for (mask,) in struct.iter_unpack("<I", data):
                if not previous < mask < 1 << 24:
                    raise ArithmeticError(name + " mask order changed")
                if total < selected_count:
                    prefix_hash.update(mask.to_bytes(4, "little"))
                    last = mask
                elif total == selected_count:
                    excluded = mask
                if total in wanted:
                    found[total] = mask
                previous = mask
                total += 1
    if (raw_hash.hexdigest() != archive["raw_sha256"]
            or total != archive["full_signed_classes"]
            or prefix_hash.hexdigest() != row["selected_raw_sha256"]
            or row["full_raw_sha256"] != archive["raw_sha256"]
            or row["selected_signed_classes"] != selected_count
            or row["actual_usable_points_B"] != 2 * selected_count
            or last != row["last_selected_mask"]
            or excluded != row["first_excluded_mask"]
            or [found[index] for index in controls] != row["control_masks"]):
        raise ArithmeticError(name + " selected prefix mismatch")
    return {"full_signed_classes": total,
            "selected_signed_classes": selected_count,
            "selected_raw_sha256": prefix_hash.hexdigest(),
            "control_count": len(controls)}


def replay_queries(config: dict, receipt: dict, started: float):
    law = config["ordinary_relation_queries"]
    domain = law["scalar_domain"].encode("utf-8")
    order = int(config["subgroup_order"])
    wanted = max(law["frozen_prefix_lengths"])
    accepted = set()
    first = []
    stream_hash = hashlib.sha256()
    counter = 0
    while len(accepted) < wanted:
        if counter % 1024 == 0:
            check_envelope(started, config)
        value = int.from_bytes(hashlib.sha256(
            domain + b"\x00" + counter.to_bytes(8, "big")
        ).digest()[:17], "big") % (1 << 130)
        source_counter = counter
        counter += 1
        if value == 0 or value >= order or value in accepted:
            continue
        index = len(accepted)
        accepted.add(value)
        stream_hash.update(value.to_bytes(17, "big"))
        if index < 16:
            first.append({"index": index, "counter": source_counter,
                          "scalar_decimal": str(value)})
    if (receipt["accepted_count"] != wanted
            or receipt["counters_used"] != counter
            or receipt["prefix_lengths"] != law["frozen_prefix_lengths"]
            or receipt["scalar_stream_sha256"] != stream_hash.hexdigest()
            or receipt["first_16_accepted"] != first
            or receipt["primary_target_workload_id"]
            != config["primary_target"]["workload_id"]):
        raise ArithmeticError("query scalar stream mismatch")
    return {"accepted": wanted, "counter_attempts": counter,
            "scalar_stream_sha256": stream_hash.hexdigest()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("refusing to overwrite a replay receipt")
    started = time.perf_counter()
    cpu_started = time.process_time()
    try:
        config = load(CONFIG)
        base = load(BASE)
        queries = load(QUERIES)
        if (base["status"] != "MASK_PREFIXES_FROZEN_PENDING_SAGE_POINT_REPLAY"
                or queries["status"] != "SCALARS_FROZEN_PENDING_PUBLIC_POINT_REPLAY"
                or base["config_sha256"] != digest(CONFIG)
                or queries["config_sha256"] != digest(CONFIG)):
            raise ValueError("frozen receipt or configuration identity changed")
        archives = {name: replay_archive(name, config, base, started)
                    for name in ("source", "descendant_native")}
        scalar_result = replay_queries(config, queries, started)
        normal_path = ROOT / config["bound_inputs"]["q1421_producer"]["path"]
        if (digest(normal_path)
                != config["bound_inputs"]["q1421_producer"]["sha256"]
                or load(normal_path)[
                    "rational_canonical_orbit_representatives_sha256"]
                != base["normal4_rational_orbit_digest_sha256"]):
            raise ValueError("normal4 orbit digest changed")
        result = {
            "schema": "ecc2k130-normal4-equalb-independent-input-replay-v1",
            "status": "PASS_INDEPENDENT_MASK_AND_SCALAR_REPLAY",
            "archives": archives,
            "queries": scalar_result,
            "config_sha256": digest(CONFIG),
            "base_receipt_sha256": digest(BASE),
            "query_receipt_sha256": digest(QUERIES),
            "verifier_sha256": digest(Path(__file__)),
            "wall_seconds": time.perf_counter() - started,
            "cpu_seconds": time.process_time() - cpu_started,
            "peak_rss_bytes": peak_rss(),
            "ordinary_pdp_attempts": 0,
        }
        with args.out.open("x") as output:
            json.dump(result, output, indent=2, sort_keys=True)
            output.write("\n")
        print(result["status"], archives, scalar_result)
    except Exception as exc:
        failure = args.out.with_name("input_verification_failure.json")
        with failure.open("x") as output:
            json.dump({"schema": "ecc2k130-normal4-equalb-input-replay-failure-v1",
                       "status": "VERIFIER_FAILURE", "error_type": type(exc).__name__,
                       "error": str(exc), "config_sha256": digest(CONFIG),
                       "verifier_sha256": digest(Path(__file__)),
                       "wall_seconds": time.perf_counter() - started},
                      output, indent=2, sort_keys=True)
            output.write("\n")
        raise


if __name__ == "__main__":
    main()
