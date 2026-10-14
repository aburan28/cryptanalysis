#!/usr/bin/env python3
"""Audit Q1090/Q1091 base capacity and compare frozen native stage cells."""

import argparse
import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CODEGEN = ROOT.parents[1] / "ecc2k130" / "runner" / "codegen"
HEADER = ROOT.parents[1] / "ecc2k130" / "runner" / "generated" / "eccF83.h"
sys.path.insert(0, str(CODEGEN))
sys.path.insert(0, str(ROOT))

import field  # noqa: E402
import bench_n83_zero_run_stage as zero_stage  # noqa: E402


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def load_relative(name):
    path = (HERE / name).resolve()
    return path, json.loads(path.read_text())


def minimum_orbits(required):
    # Smallest integer K with 166 * binom(K, 2) >= required.
    estimate = (1 + math.isqrt(1 + 4 * ((required + 82) // 83))) // 2
    while 83 * estimate * (estimate - 1) < required:
        estimate += 1
    while estimate > 1 and 83 * (estimate - 1) * (estimate - 2) >= required:
        estimate -= 1
    return estimate


def prefix_overlap(domain, table, queries, shift):
    """Intersection of [0,table) and shifted [0,queries) on Z/domain."""
    assert 0 <= shift < domain and table <= domain and queries <= domain
    first = max(0, min(table, shift + queries) - shift)
    wrapped = max(0, shift + queries - domain)
    return first + min(table, wrapped)


def audit(protocol):
    schedule = protocol["schedule"]
    target_path, target = load_relative(protocol["public_target_fixture"])
    terminal_path, terminal = load_relative(protocol["terminal_reconciliation"])
    assert target["curve_id"] == protocol["curve_id"]
    assert target["workload"]["targets"] == [target["public_target"]]
    assert target["fixture_scalar_retained"] is False
    planned_queries = (schedule["planned_shards"] *
                       schedule["query_representatives_per_shard"])
    table = schedule["table_descriptors_per_shard"]
    assert terminal["curve_id"] == protocol["curve_id"]
    assert terminal["workload_id"] == target["workload_id"]
    assert terminal["Q1091_verified_relations"] == 1
    assert terminal["verified_fresh_target_scalar"] == "1228047131163538399404643"
    plans = [load_relative(name) for name in protocol["wave_plans"]]
    starts = []
    for path, plan in plans:
        assert plan["curve_id"] == protocol["curve_id"]
        assert plan["workload_id"] == target["workload_id"]
        assert plan["public_target"] == target["public_target"]
        assert plan["table_start"] == schedule["table_start"]
        assert plan["table_descriptors"] == table
        assert plan["query_representatives"] == schedule["query_representatives_per_shard"]
        starts.extend(plan["query_starts"])
    assert starts == [i * schedule["query_representatives_per_shard"]
                      for i in range(schedule["planned_shards"])]
    assert schedule["query_offset"] - schedule["table_offset"] == 123456789
    assert planned_queries == 80 * (1 << 29)
    bases = []
    for name in protocol["base_receipts"]:
        path, receipt = load_relative(name)
        base = receipt["factor_base"]
        K = base["signed_frobenius_columns"]
        B = base["actual_usable_points_B_before_folding"]
        domain = 166 * math.comb(K, 2)
        assert receipt["curve_id"] == protocol["curve_id"]
        assert base["selected_point_orbits"] == K
        assert base["signed_frobenius_orbit_size"] == 166
        assert B == 166 * K
        assert base["initially_known_log_columns"] == K
        assert base["unknown_log_columns"] == 0
        assert math.gcd(schedule["table_step"], domain) == 1
        assert math.gcd(schedule["query_step"], domain) == 1
        key_path = ROOT / base["key_and_log_file"]
        assert digest(key_path) == base["key_and_log_file_sha256"]
        assert key_path.stat().st_size == base["key_and_log_file_bytes"]
        shift = ((schedule["query_offset"] - schedule["table_offset"]) *
                 pow(schedule["table_step"], -1, domain)) % domain
        original_overlap = prefix_overlap(domain, table, planned_queries, shift)
        proposed_offset = ((schedule["table_offset"] +
                            schedule["table_step"] * table) % domain)
        proposed_shift = ((proposed_offset - schedule["table_offset"]) *
                          pow(schedule["table_step"], -1, domain)) % domain
        proposed_overlap = prefix_overlap(domain, table, planned_queries,
                                          proposed_shift)
        bases.append({
            "base_receipt": name,
            "base_receipt_sha256": digest(path),
            "key_and_log_file_sha256": digest(key_path),
            "orbit_count_K": K,
            "actual_usable_points_B_before_folding": B,
            "enumerated_set_sha256": base["enumerated_set_sha256"],
            "cross_orbit_pair_domain": domain,
            "planned_query_capacity_margin": domain - planned_queries,
            "planned_query_plus_table_capacity_margin": domain - planned_queries - table,
            "table_query_affine_position_shift": shift,
            "original_offset_table_query_pair_rank_overlap": original_overlap,
            "disjoint_query_offset": proposed_offset,
            "disjoint_query_affine_position_shift": proposed_shift,
            "disjoint_offset_table_query_pair_rank_overlap": proposed_overlap,
        })
    assert len(bases) == 2 and [b["orbit_count_K"] for b in bases] == [24097, 48194]
    assert all(b["planned_query_plus_table_capacity_margin"] >= 0 and
               b["disjoint_offset_table_query_pair_rank_overlap"] == 0
               for b in bases)
    assert bases[0]["original_offset_table_query_pair_rank_overlap"] == table
    assert bases[1]["original_offset_table_query_pair_rank_overlap"] == 0
    return {
        "kind": "n83_pair_claw_base_capacity_audit",
        "curve_id": protocol["curve_id"],
        "workload_id": target["workload_id"],
        "public_target": target["public_target"],
        "target_fixture_sha256": digest(target_path),
        "terminal_reconciliation_sha256": digest(terminal_path),
        "credited_disjoint_query_representatives": terminal[
            "credited_disjoint_query_representatives"],
        "verified_fresh_target_scalar": terminal["verified_fresh_target_scalar"],
        "wave_plan_sha256": [digest(path) for path, _ in plans],
        "planned_shards": schedule["planned_shards"],
        "planned_query_representatives": planned_queries,
        "table_descriptors_per_shard": table,
        "minimum_K_for_planned_queries": minimum_orbits(planned_queries),
        "minimum_K_for_planned_queries_plus_one_table": minimum_orbits(planned_queries + table),
        "bases": bases,
        "status": "exact_schedule_capacity_only",
    }


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def stage(protocol, capacity):
    cell = protocol["stage_trial"]
    arch = platform.machine().lower()
    assert cell["cpu_backend"] == "arm_pmull" and arch in ("arm64", "aarch64")
    assert cell["order_orbit_counts"] == [24097, 48194, 48194, 24097]
    target = tuple(capacity["public_target"])
    onb = field.Onb(83)
    target_xy = [format(onb.toCoords(value), "x") for value in target]
    source_hashes = {path.name: digest(path) for path in zero_stage.FROZEN}
    assert all(digest(path) == expected for path, expected in zero_stage.FROZEN.items())
    receipts = {b["orbit_count_K"]: b for b in capacity["bases"]}
    output = {
        "kind": "n83_pair_claw_base_size_matched_stage_trial",
        "status": "running",
        "timing_tier": "exploratory_local_unisolated",
        "curve_id": protocol["curve_id"],
        "workload_id": capacity["workload_id"],
        "public_target": list(target),
        "target_fixture_sha256": capacity["target_fixture_sha256"],
        "protocol_sha256": digest(HERE / "protocol.json"),
        "source_hashes": source_hashes,
        "generated_field_sha256": digest(HEADER),
        "host": {"machine": arch, "system": platform.system(),
                 "release": platform.release(), "processor": platform.processor()},
        "cells": [],
    }
    out_path = HERE / "stage_runs.json"
    write_json(out_path, output)
    with tempfile.TemporaryDirectory(prefix="native-", dir=HERE) as temp_name:
        temp = Path(temp_name)
        generated = temp / "generated"
        generated.mkdir()
        pairs, core, source = zero_stage.generated_sources(generated)
        shutil.copyfile(HEADER, generated / "eccF83.h")
        output["generated_source_hashes"] = {
            path.name: digest(path) for path in (pairs, core, source, generated / "eccF83.h")}
        for K in (24097, 48194):
            binary = temp / f"pairclaw_k{K}"
            flags = cell["native_flags"]
            command = ["c++", *flags, f"-DECC2K83_ORBITS={K}",
                       str(source), "-o", str(binary)]
            subprocess.run(command, check=True, capture_output=True, text=True)
            output.setdefault("binary_builds", []).append({
                "orbit_count_K": K, "command": command,
                "binary_sha256": digest(binary),
            })
        write_json(out_path, output)
        schedule = protocol["schedule"]
        for K in cell["order_orbit_counts"]:
            base = receipts[K]
            receipt = json.loads((HERE / base["base_receipt"]).read_text())
            key_path = ROOT / receipt["factor_base"]["key_and_log_file"]
            binary = temp / f"pairclaw_k{K}"
            query_offset = (base["disjoint_query_offset"] if K == 24097
                            else schedule["query_offset"])
            command = [str(binary), str(key_path), *target_xy,
                       str(cell["table_descriptors"]), str(cell["query_representatives"]),
                       str(cell["table_batch"]), str(schedule["table_step"]),
                       str(schedule["table_offset"]), str(schedule["query_step"]),
                       str(query_offset), str(cell["bits_per_key"]),
                       str(cell["hashes"]), str(schedule["table_start"]),
                       str(schedule["query_start"]), str(cell["workers"]),
                       str(cell["representative_batch"])]
            env = os.environ.copy()
            env["ECC2K83_CANDIDATE_TMPDIR"] = temp_name
            row = {"orbit_count_K": K,
                   "actual_usable_points_B_before_folding": base["actual_usable_points_B_before_folding"],
                   "base_enumerated_set_sha256": base["enumerated_set_sha256"],
                   "query_offset": query_offset,
                   "started_at_utc": utc(), "command": command}
            started = time.perf_counter()
            try:
                completed = subprocess.run(command, env=env, capture_output=True,
                                           text=True, timeout=300)
                row["subprocess_returncode"] = completed.returncode
                row["stderr"] = completed.stderr[-4000:]
                if completed.returncode == 0:
                    row["native_result"] = json.loads(completed.stdout)
                    assert row["native_result"]["actual_B"] == 166 * K
                    row["status"] = "completed"
                else:
                    row["status"] = "native_failure"
            except subprocess.TimeoutExpired as error:
                row["status"] = "timeout"
                row["stderr"] = (error.stderr or b"").decode(errors="replace")[-4000:]
            row["subprocess_wall_seconds"] = time.perf_counter() - started
            row["finished_at_utc"] = utc()
            output["cells"].append(row)
            write_json(out_path, output)
    output["status"] = "completed" if all(row["status"] == "completed" for row in output["cells"]) else "partial"
    write_json(out_path, output)
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", action="store_true", help="run the four local stage cells")
    args = parser.parse_args()
    protocol = json.loads((HERE / "protocol.json").read_text())
    capacity = audit(protocol)
    write_json(HERE / "capacity.json", capacity)
    print(json.dumps({"capacity": capacity["bases"],
                      "minimum_K_for_planned_queries_plus_one_table":
                      capacity["minimum_K_for_planned_queries_plus_one_table"]}))
    if args.stage:
        result = stage(protocol, capacity)
        print(json.dumps({"status": result["status"], "cells": [
            {"K": row["orbit_count_K"], "status": row["status"],
             "wall_seconds": row["subprocess_wall_seconds"]}
            for row in result["cells"]]}))


if __name__ == "__main__":
    main()
