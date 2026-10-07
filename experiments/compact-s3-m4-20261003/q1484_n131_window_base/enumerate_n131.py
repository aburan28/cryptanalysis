#!/usr/bin/env python3
"""Exhaustively archive Q1481's N131 window base in two bits per raw orbit."""

from __future__ import annotations

import hashlib
import json
import os
import resource
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
Q1481 = PARENT / "q1481_window_orbit_base"
PROTOCOL = HERE / "protocol.json"
RUN = HERE / "runs" / "r1"

sys.path.insert(0, str(PARENT))
from enumerate_q1413_projected_x import canonical_rotation, projected_x  # noqa: E402
from run_probe import curves, field, sha  # noqa: E402
sys.path.insert(0, str(Q1481))
from enumerate_base import (OrbitKey, onb_x_from_cycle_mask,  # noqa: E402
                            representatives)


def verify_freeze(protocol: dict) -> None:
    design_path = HERE / "design_protocol.json"
    design = json.loads(design_path.read_text())
    assert protocol["kind"] == "q1484_frozen_n131_window_base_enumeration"
    assert protocol["proposal_id"] == design["proposal_id"] == "Q1484"
    assert protocol["candidate_id"] is design["candidate_id"] is None
    assert protocol["run_id"] is design["run_id"] is None
    assert protocol["isogeny"] == design["isogeny"] == "none"
    assert protocol["curve_id"] == design["curve_id"]
    assert protocol["nominal_window_dimension_d"] == design[
        "nominal_window_dimension_d"] == 27
    assert protocol["raw_x_orbits_formula"] == design[
        "raw_x_orbits_formula"] == 1 << 26
    assert protocol["design_sha256"] == sha(design_path)
    assert protocol["runtime_info_sha256"] == sha(
        HERE / "sage_runtime_info.json")
    assert protocol["preflight_sha256"] == sha(HERE / "preflight.json")
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert runtime["status"] == "verified"
    assert protocol["source_sha256"]["enumerate_n131.py"] == sha(
        Path(__file__))
    for relative, digest in protocol["dependency_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    for relative, digest in protocol["reference_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    assert protocol["limits"] == design["limits"]
    assert protocol["field"]["n"] == 131
    assert protocol["curve"]["curve_id"] == design["curve_id"]
    assert curves.curveOrder(131) == (protocol["cofactor"] *
                                       protocol["subgroup_order"])


def status_code(flags: bytearray, index: int, code: int) -> None:
    assert 0 <= code <= 2
    slot = index >> 2
    shift = (index & 3) << 1
    assert not (flags[slot] & (3 << shift))
    flags[slot] |= code << shift


def emit_progress(path: Path, flags_path: Path, flags: bytearray,
                  processed: int, written: int, keys: set[int],
                  start: float, limits: dict) -> int:
    assert processed % 4 == 0
    end = processed >> 2
    with flags_path.open("ab") as output:
        output.write(flags[written:end])
        output.flush()
        os.fsync(output.fileno())
    elapsed = time.perf_counter() - start
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    row = {"processed_raw_x_orbits": processed,
           "unique_projected_orbits_so_far": len(keys),
           "elapsed_seconds_exploratory": elapsed,
           "peak_rss_raw": rss}
    with path.open("a") as output:
        output.write(json.dumps(row, sort_keys=True) + "\n")
        output.flush()
    print(json.dumps(row, sort_keys=True), flush=True)
    assert elapsed <= limits["max_wall_seconds"], "registered wall cap"
    assert rss <= limits["max_peak_rss_bytes"], "registered RSS cap"
    assert shutil.disk_usage(RUN).free >= 500_000_000, "low disk"
    return end


def enumerate_base(protocol: dict) -> dict:
    n = 131
    d = protocol["nominal_window_dimension_d"]
    raw_count = protocol["raw_x_orbits_formula"]
    limits = protocol["limits"]
    assert 2 * d < n and raw_count == 1 << (d - 1)
    assert not RUN.exists(), "refuse to overwrite frozen R1 run"
    assert shutil.disk_usage(HERE).free >= limits[
        "minimum_free_disk_bytes_before_run"]
    RUN.mkdir(parents=True)
    progress_path = RUN / "progress.jsonl"
    partial_path = RUN / "status_flags.partial"
    final_path = RUN / "status_flags.bin"
    flags = bytearray((raw_count + 3) // 4)
    keys: set[int] = set()
    strata = [{"span": span,
               "raw_x_orbits": 0,
               "rational_x_orbits": 0,
               "identity_projection_orbits": 0,
               "duplicate_projected_orbits": 0}
              for span in range(1, d + 1)]
    controls: list[dict] = []
    sampled = {(span, rational): 0 for span in range(1, d + 1)
               for rational in (False, True)}
    onb = field.Onb(n)
    orbit = OrbitKey(onb)
    start = time.perf_counter()
    written = 0
    processed = 0
    try:
        for cycle_mask, span in representatives(d):
            row = strata[span - 1]
            row["raw_x_orbits"] += 1
            x = onb_x_from_cycle_mask(cycle_mask, onb, orbit)
            rational, projected = projected_x(onb, x)
            key = None
            if not rational:
                code = 0
            else:
                row["rational_x_orbits"] += 1
                if projected is None:
                    row["identity_projection_orbits"] += 1
                    code = 1
                else:
                    code = 2
                    key = canonical_rotation(orbit.cycle_bits(projected), n)
                    assert 0 < key < (1 << n) - 1
                    if key in keys:
                        row["duplicate_projected_orbits"] += 1
                    else:
                        keys.add(key)
            status_code(flags, processed, code)
            if sampled[(span, rational)] < 2:
                controls.append({"span": span,
                                 "raw_cycle_mask": cycle_mask,
                                 "raw_ordinal": processed,
                                 "rational": rational,
                                 "status_code": code,
                                 "projected_orbit_key": key})
                sampled[(span, rational)] += 1
            processed += 1
            if processed % limits["progress_interval_raw_orbits"] == 0:
                written = emit_progress(progress_path, partial_path,
                                        flags, processed, written, keys,
                                        start, limits)
        assert processed == raw_count
        assert written == len(flags)
        assert partial_path.stat().st_size == len(flags)
        partial_path.replace(final_path)
        enumeration_seconds = time.perf_counter() - start
        assert len(keys) == sum(
            row["rational_x_orbits"] - row[
                "identity_projection_orbits"] - row[
                    "duplicate_projected_orbits"] for row in strata)
        assert all(row["raw_x_orbits"] == (
            1 if row["span"] == 1 else 1 << (row["span"] - 2))
            for row in strata)
        sorted_start = time.perf_counter()
        digest = hashlib.sha256()
        width = (n + 7) // 8
        for key in sorted(keys):
            digest.update(key.to_bytes(width, "little"))
        digest_seconds = time.perf_counter() - sorted_start
        assert time.perf_counter() - start <= limits[
            "max_wall_seconds"], "registered total wall cap"
        assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss <= limits[
            "max_peak_rss_bytes"], "registered total RSS cap"
        status_digest = hashlib.sha256(flags).hexdigest()
        receipt = {
            "kind": "q1484_exact_n131_window_base_enumeration",
            "proposal_id": "Q1484", "candidate_id": None,
            "workload_id": None, "run_id": None,
            "attempt_id": "Q1484R1", "isogeny": "none",
            "curve_id": protocol["curve_id"],
            "field_degree_n": n, "cofactor": protocol["cofactor"],
            "nominal_window_dimension_d": d,
            "nominal_raw_x_orbits": raw_count,
            "nominal_raw_x_masks": n * raw_count,
            "geometric_rational_point_count_before_projection": (
                2 * n * sum(row["rational_x_orbits"] for row in strata)),
            "actual_usable_points_B_before_folding": 2 * n * len(keys),
            "signed_frobenius_columns_K": len(keys),
            "enumerated_set_encoding": (
                "Sorted unique canonical projected x keys, 17-byte "
                "little-endian; reconstruct from frozen raw status bitmap "
                "and deterministic [4] projection source"),
            "enumerated_set_sha256": digest.hexdigest(),
            "status_bitmap_sha256": status_digest,
            "status_bitmap_bytes": len(flags),
            "status_bitmap_encoding": protocol["archive_encoding"],
            "strata": strata,
            "independent_group_control_inputs": controls,
            "enumeration_wall_seconds_exploratory": enumeration_seconds,
            "sort_digest_wall_seconds_exploratory": digest_seconds,
            "total_construction_wall_seconds_exploratory": (
                time.perf_counter() - start),
            "peak_rss_raw": resource.getrusage(
                resource.RUSAGE_SELF).ru_maxrss,
            "peak_rss_units": "bytes on Darwin, KiB on Linux",
            "progress_file_sha256": sha(progress_path),
            "design_sha256": sha(HERE / "design_protocol.json"),
            "protocol_sha256": sha(PROTOCOL),
            "source_sha256": sha(Path(__file__)),
            "runtime_info_sha256": sha(
                HERE / "sage_runtime_info.json"),
            "is_empirical_relation_yield": False,
            "complete_solve_work_log2": None,
            "challenge_run_admitted": False,
        }
        (RUN / "receipt.json").write_text(json.dumps(
            receipt, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"status": "complete", "B": receipt[
            "actual_usable_points_B_before_folding"], "K": len(keys),
            "enumerated_set_sha256": digest.hexdigest(),
            "total_seconds": receipt[
                "total_construction_wall_seconds_exploratory"]}),
              flush=True)
        return receipt
    except Exception as error:
        failure = {
            "kind": "q1484_n131_window_base_failed_attempt",
            "proposal_id": "Q1484", "attempt_id": "Q1484R1",
            "candidate_id": None, "run_id": None,
            "isogeny": "none", "curve_id": protocol["curve_id"],
            "status": "infrastructure_or_limit_error",
            "error": repr(error), "processed_raw_x_orbits": processed,
            "unique_projected_orbits_so_far": len(keys),
            "partial_status_bitmap_sha256": (
                sha(partial_path) if partial_path.exists() else None),
            "completed_status_bitmap_sha256": (
                sha(final_path) if final_path.exists() else None),
            "protocol_sha256": sha(PROTOCOL),
            "complete_solve_work_log2": None,
        }
        try:
            (RUN / "failure.json").write_text(json.dumps(
                failure, indent=2, sort_keys=True) + "\n")
        except OSError:
            pass
        raise


def main() -> None:
    protocol = json.loads(PROTOCOL.read_text())
    verify_freeze(protocol)
    enumerate_base(protocol)


if __name__ == "__main__":
    main()
