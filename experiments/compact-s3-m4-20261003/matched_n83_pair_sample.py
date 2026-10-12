#!/usr/bin/env python3
"""Bounded pair-table sample on the frozen n83 weight-four base and target."""

from __future__ import annotations

import base64
import bisect
import gzip
import hashlib
import json
import random
import resource
import sys
import time
from pathlib import Path

from run_probe import HERE, sha, curves, field

PRIOR = HERE.parent / "koblitz-pair-claw-20260929"
sys.path.insert(0, str(PRIOR))
from orbit_key import OrbitKey  # noqa: E402

TABLE_SAMPLES = 20_000
QUERY_SAMPLES = 20_000
TABLE_SEED = 830930
QUERY_SEED = 830931


class CompactBase:
    def __init__(self, curve, onb, keys, orbit_lengths):
        self.curve = curve
        self.onb = onb
        self.keys = keys
        self.orbit_lengths = orbit_lengths
        self.offsets = [0]
        for length in orbit_lengths:
            self.offsets.append(self.offsets[-1] + 2 * length)
        self.cache = {}

    def __len__(self):
        return self.offsets[-1]

    def __getitem__(self, index):
        if not 0 <= index < len(self):
            raise IndexError(index)
        position = bisect.bisect_right(self.offsets, index) - 1
        length = self.orbit_lengths[position]
        within = index - self.offsets[position]
        point = self.cache.get(position)
        if point is None:
            point = self.curve.pointFromX(
                self.onb.fromCoords(self.keys[position]))
            assert point is not None
            self.cache[position] = point
        shifted = self.curve.frob(point, within % length)
        return self.curve.neg(shifted) if within >= length else shifted


def main():
    stage_path = HERE / "runs/n83_ordinary_frozen.json"
    archive_path = HERE / "bases/n83_weight4_orbits.json.gz"
    output = HERE / "runs/n83_ordinary_matched_pair_sample.json"
    assert not output.exists()
    stage = json.loads(stage_path.read_text())
    with gzip.open(archive_path, "rt") as stream:
        archive = json.load(stream)
    assert sha(Path(field.__file__)) == archive["enumeration"][
        "field_source_sha256"]
    assert sha(Path(curves.__file__)) == archive["enumeration"][
        "curve_source_sha256"]
    assert stage["curve_id"] == archive["curve"]["curve_id"]
    assert stage["factor_base_archive_sha256"] == sha(archive_path)
    assert stage["workload_kind"] == "ordinary"
    assert stage["protocol_sha256"] == sha(HERE / "protocol.json")
    fb = archive["factor_base"]
    packed = base64.b64decode(fb["packed_canonical_x_keys_base64"])
    assert hashlib.sha256(packed).hexdigest() == fb["enumerated_set_sha256"]
    assert len(packed) == 11 * fb["signed_frobenius_columns"]
    keys = [int.from_bytes(packed[i:i + 11], "little")
            for i in range(0, len(packed), 11)]
    assert keys == sorted(set(keys))
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    base = CompactBase(curve, onb, keys, fb["orbit_lengths"])
    assert len(base) == fb["actual_usable_points_B_before_folding"]
    target = tuple(int(v) for v in stage["public_subgroup_target"])
    order = int(archive["curve"]["subgroup_order"])
    assert curve.onCurve(target) and curve.mul(target, order) is None
    for index in (0, 1, 82, 83, len(base) - 1):
        point = base[index]
        assert curve.onCurve(point) and curve.mul(point, order) is None

    orbit = OrbitKey(onb)
    table_rng = random.Random(TABLE_SEED)
    query_rng = random.Random(QUERY_SEED)
    table = {}
    table_identity = 0
    table_started = time.perf_counter_ns()
    for _ in range(TABLE_SAMPLES):
        first, second = table_rng.randrange(len(base)), table_rng.randrange(len(base))
        point = curve.add(base[first], base[second])
        if point is None:
            table_identity += 1
            continue
        key, exponent, sign = orbit.canonical(point)
        table.setdefault(key, (first, second, exponent, sign))
    table_ns = time.perf_counter_ns() - table_started

    query_identity = 0
    quotient_key_hits = 0
    verified_relations = []
    query_started = time.perf_counter_ns()
    for query_number in range(1, QUERY_SAMPLES + 1):
        first, second = query_rng.randrange(len(base)), query_rng.randrange(len(base))
        pair = curve.add(base[first], base[second])
        if pair is None:
            query_identity += 1
            continue
        complement = curve.add(target, curve.neg(pair))
        key, exponent, sign = orbit.canonical(complement)
        previous = table.get(key)
        if previous is None:
            continue
        quotient_key_hits += 1
        earlier_first, earlier_second, earlier_exponent, earlier_sign = previous
        shift = (earlier_exponent - exponent) % orbit.n
        negation = earlier_sign * sign
        points = [curve.frob(base[i], shift) for i in
                  (earlier_first, earlier_second)]
        if negation < 0:
            points = [curve.neg(point) for point in points]
        points.extend((base[first], base[second]))
        total = None
        for point in points:
            total = curve.add(total, point)
        assert total == target
        verified_relations.append({"query_number": query_number,
                                   "point_coordinates": [list(point)
                                                         for point in points]})
    query_ns = time.perf_counter_ns() - query_started
    report = {
        "kind": "matched_n83_weight4_pair_table_bounded_stage_sample",
        "proposal_id": "Q1302",
        "candidate_id": None,
        "run_id": None,
        "workload_id": stage["workload_id"],
        "curve_id": stage["curve_id"],
        "isogeny": "none",
        "status": "bounded_sample_complete",
        "target": stage["public_subgroup_target"],
        "matched_s3_stage_receipt_sha256": sha(stage_path),
        "protocol_sha256": stage["protocol_sha256"],
        "factor_base_archive_sha256": sha(archive_path),
        "factor_base_enumerated_set_sha256": fb["enumerated_set_sha256"],
        "factor_base_actual_B": len(base),
        "factor_base_folded_columns": fb["signed_frobenius_columns"],
        "table_samples": TABLE_SAMPLES,
        "query_samples": QUERY_SAMPLES,
        "table_seed": TABLE_SEED,
        "query_seed": QUERY_SEED,
        "table_identity_pairs": table_identity,
        "query_identity_pairs": query_identity,
        "table_distinct_keys": len(table),
        "quotient_key_hits": quotient_key_hits,
        "verified_relations": verified_relations,
        "table_wall_ns": table_ns,
        "query_wall_ns": query_ns,
        "base_cached_representatives": len(base.cache),
        "peak_parent_rss_raw": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "peak_parent_rss_units": "bytes on Darwin, KiB on Linux",
        "verified_single_target_dlp": False,
        "complete_work_log2": None,
        "source_sha256": sha(Path(__file__)),
        "orbit_key_source_sha256": sha(PRIOR / "orbit_key.py"),
        "field_source_sha256": sha(Path(field.__file__)),
        "curve_source_sha256": sha(Path(curves.__file__)),
        "run_probe_source_sha256": sha(HERE / "run_probe.py"),
    }
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"],
                      "table_seconds": table_ns / 1e9,
                      "query_seconds": query_ns / 1e9,
                      "table_distinct_keys": len(table),
                      "quotient_key_hits": quotient_key_hits,
                      "verified_relations": len(verified_relations),
                      "base_cached_representatives": len(base.cache)}))


if __name__ == "__main__":
    main()
