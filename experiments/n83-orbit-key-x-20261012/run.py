#!/usr/bin/env python3
"""Check the faster canonical x lookup on every width-16 orbit key."""

import hashlib
import json
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / "ecc2k130/runner/codegen"),
                str(ROOT / "experiments/koblitz-pair-claw-20260929"),
                str(ROOT / "experiments/m5-s3-gate-20261004")]

import field  # noqa: E402
from orbit_key import OrbitKey  # noqa: E402
from build_m5 import canonical_projected_x  # noqa: E402
from fast_x import CanonicalXFromOrbitKey  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "result.json"
    assert not output.exists()
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["proposal_id"] == "Q2026101248"
    assert sha(HERE / "sage_runtime_info.json") == protocol[
        "sage_runtime_info_sha256"]
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    key_path = ROOT / protocol["key_file"]
    assert sha(key_path) == protocol["key_sha256"]
    data = key_path.read_bytes()
    assert len(data) == 21 * protocol["K"]
    keys = [int.from_bytes(data[i:i + 21], "little")
            for i in range(0, len(data), 21)]
    assert keys == sorted(set(keys))
    onb = field.Onb(83)
    orbit = OrbitKey(onb)
    fast = CanonicalXFromOrbitKey(orbit)
    started = time.perf_counter_ns()
    output.write_text(json.dumps({
        "kind": "n83_full_base_canonical_x_lookup_result",
        "status": "running",
        "protocol_sha256": sha(protocol_path),
        "key_sha256": sha(key_path),
    }, indent=2, sort_keys=True) + "\n")
    reference_start = time.perf_counter_ns()
    reference = [canonical_projected_x(onb, orbit.point_from_key(key), 83)
                 for key in keys]
    reference_ns = time.perf_counter_ns() - reference_start
    fast_start = time.perf_counter_ns()
    observed = [fast.canonical_x(key) for key in keys]
    fast_ns = time.perf_counter_ns() - fast_start
    first_mismatch = next((i for i, (old, new) in
                           enumerate(zip(reference, observed)) if old != new),
                          None)
    distinct_x_count = len(set(observed))
    status = "PASS" if first_mismatch is None and distinct_x_count == protocol[
        "K"] else "FAIL"
    record = {
        "kind": "n83_full_base_canonical_x_lookup_result",
        "status": status,
        "curve_id": protocol["curve_id"],
        "K": protocol["K"],
        "B": protocol["B"],
        "checked_keys": len(keys),
        "first_mismatch_index": first_mismatch,
        "distinct_x_count": distinct_x_count,
        "reference_ns_exploratory": reference_ns,
        "cycle_table_ns_exploratory": fast_ns,
        "timing_tier": protocol["timing_tier"],
        "run_order": protocol["run_order"],
        "peak_rss_raw": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "protocol_sha256": sha(protocol_path),
        "key_sha256": sha(key_path),
        "reference_digest_sha256": hashlib.sha256(b"".join(
            x.to_bytes(11, "little") for x in reference)).hexdigest(),
        "cycle_table_digest_sha256": hashlib.sha256(b"".join(
            x.to_bytes(11, "little") for x in observed)).hexdigest(),
        "total_wall_ns": time.perf_counter_ns() - started,
    }
    output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": status, "K": len(keys),
                      "reference_seconds": reference_ns / 1e9,
                      "cycle_table_seconds": fast_ns / 1e9}), flush=True)
    assert status == "PASS"


if __name__ == "__main__":
    main()
