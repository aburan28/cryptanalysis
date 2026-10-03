#!/usr/bin/env python3
"""Measure quotient pair sampling on the exact compressed n=83 base."""

import hashlib
import json
import platform
import random
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEGEN = HERE.parents[1] / "ecc2k130" / "runner" / "codegen"
BASE_RECEIPT = HERE / "runs" / "n83_weight5_orbit_base.json"
OUTPUT = HERE / "runs" / "n83_full_base_quotient_pair_perf.json"
sys.path.insert(0, str(CODEGEN))

import curves
import field
from bench_steps import CountingOnb
from orbit_key import OrbitKey
from run_n23 import frozen, sha

TABLE_SAMPLES = 100000
QUERY_SAMPLES = 100000
TABLE_SEED = 830930
QUERY_SEED = 830931
COUNT_SAMPLES = 4096


class CompactOrbitBase:
    def __init__(self, orbit, keys):
        self.orbit = orbit
        self.keys = keys
        self.n = orbit.n
        self.mask = (1 << orbit.n) - 1

    def __len__(self):
        return 2 * self.n * len(self.keys)

    def __getitem__(self, index):
        if index < 0 or index >= len(self):
            raise IndexError(index)
        orbit_index, within = divmod(index, 2 * self.n)
        key = self.keys[orbit_index]
        x = key >> self.n
        y = key & self.mask
        shift = within % self.n
        if shift:
            x = ((x << shift) | (x >> (self.n - shift))) & self.mask
            y = ((y << shift) | (y >> (self.n - shift))) & self.mask
        if within >= self.n:
            y ^= x
        return self.orbit.point_from_key((x << self.n) | y)


def main():
    base_receipt = json.loads(BASE_RECEIPT.read_text())
    identity = base_receipt["curve_identity_record"]
    curve_id = "EC1N83Ckb1h" + hashlib.sha256(frozen(identity)).hexdigest()[:12]
    assert base_receipt["curve_id"] == curve_id
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    key_path = HERE / base_receipt["factor_base"]["orbit_key_file"]
    data = key_path.read_bytes()
    assert sha(key_path) == base_receipt["factor_base"]["enumerated_set_sha256"]
    keys = [int.from_bytes(data[index:index + 21], "little")
            for index in range(0, len(data), 21)]
    base = CompactOrbitBase(orbit, keys)
    assert len(base) == base_receipt["factor_base"]["actual_usable_points_B_before_folding"] == 4000102
    reference_path = (HERE.parent / "ecc2k130-quotient-pair-probe-20260926" /
                      "runs" / "n83_perf_prefix.json")
    reference = json.loads(reference_path.read_text())
    target = tuple(reference["workload"]["target"])
    assert curve.onCurve(target)
    for index in (0, 1, 82, 83, 165, len(base) - 1):
        point = base[index]
        assert curve.onCurve(point)
        assert orbit.canonical(point)[0] == keys[index // 166]

    table_rng = random.Random(TABLE_SEED)
    table = {}
    table_started = time.perf_counter_ns()
    for _ in range(TABLE_SAMPLES):
        first = table_rng.randrange(len(base))
        second = table_rng.randrange(len(base))
        pair = curve.add(base[first], base[second])
        if pair is None:
            continue
        key = orbit.canonical(pair)[0]
        table.setdefault(key, (first, second))
    table_ns = time.perf_counter_ns() - table_started

    query_rng = random.Random(QUERY_SEED)
    hits = 0
    query_started = time.perf_counter_ns()
    for _ in range(QUERY_SAMPLES):
        first = query_rng.randrange(len(base))
        second = query_rng.randrange(len(base))
        pair = curve.add(base[first], base[second])
        if pair is None:
            continue
        target_complement = curve.add(target, curve.neg(pair))
        key = orbit.canonical(target_complement)[0]
        hits += int(key in table)
    query_ns = time.perf_counter_ns() - query_started

    counted_onb = CountingOnb(83)
    counted_curve = curves.Curve(counted_onb)
    counted_orbit = OrbitKey(counted_onb)
    counted_base = CompactOrbitBase(counted_orbit, keys)
    counted_table_rng = random.Random(TABLE_SEED)
    for _ in range(COUNT_SAMPLES):
        first = counted_table_rng.randrange(len(counted_base))
        second = counted_table_rng.randrange(len(counted_base))
        pair = counted_curve.add(counted_base[first], counted_base[second])
        if pair is not None:
            counted_orbit.canonical(pair)
    table_field_calls = dict(counted_onb.calls)
    counted_query_rng = random.Random(QUERY_SEED)
    for _ in range(COUNT_SAMPLES):
        first = counted_query_rng.randrange(len(counted_base))
        second = counted_query_rng.randrange(len(counted_base))
        pair = counted_curve.add(counted_base[first], counted_base[second])
        if pair is not None:
            counted_orbit.canonical(counted_curve.add(
                target, counted_curve.neg(pair)))
    query_field_calls = {name: counted_onb.calls[name] - table_field_calls.get(name, 0)
                         for name in counted_onb.calls}
    report = {
        "kind": "n83_exact_four_million_point_base_quotient_pair_stage_benchmark",
        "scope": "measured bounded table-build and target-complement pair samples; no relation or DLP",
        "proposal_id": "Q1041", "candidate_id": None, "run_id": None,
        "curve_id": curve_id, "curve_identity_record": identity,
        "isogeny": "none", "public_target": list(target),
        "factor_base": base_receipt["factor_base"],
        "compact_orbit_base_access": "index // 166 selects canonical key; index % 166 selects Frobenius rotation and sign; point decoded on demand",
        "table_seed": TABLE_SEED, "query_seed": QUERY_SEED,
        "table_samples": TABLE_SAMPLES,
        "table_distinct_keys": len(table),
        "table_wall_ns": table_ns,
        "table_ns_per_sample": table_ns / TABLE_SAMPLES,
        "query_samples": QUERY_SAMPLES,
        "query_table_key_hits": hits,
        "query_wall_ns": query_ns,
        "query_ns_per_sample": query_ns / QUERY_SAMPLES,
        "field_api_count_samples_each_phase": COUNT_SAMPLES,
        "table_field_api_calls_per_sample": {name: count / COUNT_SAMPLES
                                             for name, count in table_field_calls.items()},
        "query_field_api_calls_per_sample": {name: count / COUNT_SAMPLES
                                             for name, count in query_field_calls.items()},
        "field_api_accounting": "logical calls on a separate instrumented run; square invokes Frobenius, so categories are nested and not summed; inversion cost in multiplication equivalents is uncalibrated",
        "verified_relation_count": 0,
        "verified_single_target_dlp": False,
        "complete_work_log2": None,
        "peak_parent_rss_bytes": (resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                                  if platform.system() == "Darwin" else
                                  resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024),
        "runtime": {"python": sys.version, "platform": platform.platform()},
        "source_sha256": sha(Path(__file__)),
        "orbit_key_sha256": sha(HERE / "orbit_key.py"),
        "base_receipt_sha256": sha(BASE_RECEIPT),
        "key_file_sha256": sha(key_path),
        "reference_sha256": sha(reference_path),
        "dependency_sha256": {name: sha(CODEGEN / name)
                              for name in ("curves.py", "field.py", "indexcalc.py")},
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"curve_id": curve_id, "actual_B": len(base),
                      "columns": len(keys), "table_ns_per_sample":
                      report["table_ns_per_sample"],
                      "query_ns_per_sample": report["query_ns_per_sample"],
                      "query_field_calls": report["query_field_api_calls_per_sample"],
                      "table_hits": hits,
                      "rss_mib": report["peak_parent_rss_bytes"] / 2**20}))


if __name__ == "__main__":
    main()
