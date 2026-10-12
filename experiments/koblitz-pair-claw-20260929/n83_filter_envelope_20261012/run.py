#!/usr/bin/env python3
"""Check the exact Bloom allocation frontier and measure small N83 cells."""

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


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bloom_bytes(entries, bits):
    # native_n83_bloom_core_portable.hpp: 512 bits per cache-line block.
    return 64 * ((entries * bits + 511) // 512 + 1024)


def save(report, filename):
    (HERE / filename).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


def main():
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert platform.machine().lower() in ("arm64", "aarch64")
    base_path = (HERE / protocol["base_receipt"]).resolve()
    base = json.loads(base_path.read_text())
    factor_base = base["factor_base"]
    target_path = (HERE / protocol["target_fixture"]).resolve()
    target = json.loads(target_path.read_text())
    assert base["curve_id"] == target["curve_id"] == protocol["curve_id"]
    K = factor_base["signed_frobenius_columns"]
    assert K == 23859 and factor_base["actual_usable_points_B_before_folding"] == 166 * K
    base_file = ROOT / factor_base["key_and_log_file"]
    assert sha(base_file) == factor_base["key_and_log_file_sha256"]
    assert base_file.stat().st_size == K * 32
    domain = 83 * K * (K - 1)
    M = protocol["full_table_descriptors"]
    R = protocol["full_query_representatives_per_shard"] * protocol["full_shards"]
    assert M + R <= domain and math.gcd(protocol["table_step"], domain) == 1
    query_offset = (protocol["table_offset"] + protocol["table_step"] * M) % domain
    assert ((query_offset - protocol["table_offset"]) *
            pow(protocol["table_step"], -1, domain)) % domain == M
    frontier = {"kind": "n83_m32_bloom_exact_allocation_frontier",
                "curve_id": protocol["curve_id"],
                "base_receipt_sha256": sha(base_path),
                "base_enumerated_set_sha256": factor_base["enumerated_set_sha256"],
                "actual_usable_points_B_before_folding": 166 * K,
                "memory_cap_bytes": protocol["memory_cap_bytes"],
                "full_table_descriptors": M,
                "full_query_representatives": R,
                "pair_rank_domain": domain,
                "query_offset": query_offset,
                "bloom_source_sha256": sha(zero_stage.CORE),
                "protocol_sha256": sha(protocol_path),
                "filter_rows": []}
    for bits in range(8, 21):
        required = bloom_bytes(M, bits)
        frontier["filter_rows"].append({
            "bits_per_key": bits,
            "bloom_bytes": required,
            "remaining_bytes_before_base_and_other_allocations":
                protocol["memory_cap_bytes"] - required,
            "bloom_alone_within_cap": required <= protocol["memory_cap_bytes"],
        })
    assert bloom_bytes(M, 15) < protocol["memory_cap_bytes"]
    assert bloom_bytes(M, 16) > protocol["memory_cap_bytes"]
    save(frontier, "allocation_frontier.json")

    onb = field.Onb(83)
    target_xy = [format(onb.toCoords(x), "x") for x in target["public_target"]]
    assert all(sha(path) == digest for path, digest in zero_stage.FROZEN.items())
    report = {
        "kind": "n83_m32_filter_bit_stage_screen",
        "status": "running", "timing_tier": protocol["timing_tier"],
        "curve_id": protocol["curve_id"], "workload_id": target["workload_id"],
        "public_target": target["public_target"],
        "target_fixture_sha256": sha(target_path),
        "base_receipt_sha256": sha(base_path),
        "base_file_sha256": sha(base_file),
        "protocol_sha256": sha(protocol_path),
        "driver_source_sha256": sha(Path(__file__)),
        "allocation_frontier_sha256": sha(HERE / "allocation_frontier.json"),
        "source_hashes": {p.name: sha(p) for p in zero_stage.FROZEN},
        "generated_field_sha256": sha(HEADER),
        "host": {"machine": platform.machine(), "system": platform.system(),
                 "release": platform.release()},
        "cells": [],
    }
    save(report, "stage_runs.json")
    with tempfile.TemporaryDirectory(prefix="native-filter-", dir=HERE) as tmp:
        generated = Path(tmp) / "generated"
        generated.mkdir()
        pairs, core, source = zero_stage.generated_sources(generated)
        shutil.copyfile(HEADER, generated / "eccF83.h")
        report["generated_source_hashes"] = {
            path.name: sha(path) for path in (pairs, core, source, generated / "eccF83.h")}
        binary = Path(tmp) / "pairclaw_k23859"
        compile_command = ["c++", *protocol["native_flags"],
                           f"-DECC2K83_ORBITS={K}", str(source), "-o", str(binary)]
        subprocess.run(compile_command, check=True, capture_output=True, text=True)
        report["binary_build"] = {"command": compile_command,
                                  "binary_sha256": sha(binary)}
        save(report, "stage_runs.json")
        for bits in protocol["stage_order_bits_per_key"]:
            command = [str(binary), str(base_file), *target_xy,
                       str(protocol["stage_table_descriptors"]),
                       str(protocol["stage_query_representatives"]),
                       str(protocol["table_batch"]), str(protocol["table_step"]),
                       str(protocol["table_offset"]), str(protocol["table_step"]),
                       str(query_offset), str(bits), str(protocol["hashes"]),
                       "0", "0", str(protocol["workers"]),
                       str(protocol["representative_batch"])]
            env = os.environ.copy()
            env["ECC2K83_CANDIDATE_TMPDIR"] = tmp
            row = {"bits_per_key": bits, "command": command,
                   "started_at_utc": datetime.now(timezone.utc).isoformat()}
            started = time.perf_counter()
            try:
                completed = subprocess.run(command, capture_output=True, text=True,
                                           env=env, timeout=300)
                row["returncode"] = completed.returncode
                row["stderr"] = completed.stderr[-4000:]
                if completed.returncode == 0:
                    row["native_result"] = json.loads(completed.stdout)
                    assert row["native_result"]["actual_B"] == 166 * K
                    assert row["native_result"]["bloom_bytes"] == bloom_bytes(
                        protocol["stage_table_descriptors"], bits)
                    row["status"] = "completed"
                else:
                    row["status"] = "native_failure"
            except subprocess.TimeoutExpired as error:
                row["status"] = "timeout"
                row["stderr"] = (error.stderr or b"").decode(errors="replace")[-4000:]
            row["subprocess_wall_seconds"] = time.perf_counter() - started
            row["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
            report["cells"].append(row)
            save(report, "stage_runs.json")
    report["status"] = "completed" if all(
        row["status"] == "completed" for row in report["cells"]) else "partial"
    save(report, "stage_runs.json")
    print(json.dumps({"status": report["status"], "cells": [
        {"bits": row["bits_per_key"], "positives": row.get("native_result", {}).get(
            "bloom_positive_queries"), "wall_seconds": row["subprocess_wall_seconds"]}
        for row in report["cells"]]}))


if __name__ == "__main__":
    main()
