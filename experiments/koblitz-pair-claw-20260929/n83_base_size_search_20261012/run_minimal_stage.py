#!/usr/bin/env python3
"""Run frozen ABBA native stage cells for the minimum-capacity N83 base."""

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


def load(path):
    return json.loads(path.read_text())


def save(value):
    (HERE / "minimal_stage.json").write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n")


def main():
    protocol_path = HERE / "minimal_protocol.json"
    protocol = load(protocol_path)
    assert platform.machine().lower() in ("arm64", "aarch64")
    assert protocol["order_orbit_counts"] == [23859, 24097, 24097, 23859]
    target_path = (HERE / protocol["public_target_fixture"]).resolve()
    target = load(target_path)
    assert target["curve_id"] == protocol["curve_id"]
    onb = field.Onb(83)
    target_xy = [format(onb.toCoords(x), "x") for x in target["public_target"]]
    bases = {}
    for name, K in zip(protocol["base_receipts"], protocol["orbit_counts"]):
        path = (HERE / name).resolve()
        receipt = load(path)
        base = receipt["factor_base"]
        assert receipt["curve_id"] == protocol["curve_id"]
        assert base["selected_point_orbits"] == K
        assert base["actual_usable_points_B_before_folding"] == 166 * K
        key_path = ROOT / base["key_and_log_file"]
        assert sha(key_path) == base["key_and_log_file_sha256"]
        domain = 83 * K * (K - 1)
        M = protocol["full_schedule_table_descriptors"]
        R = protocol["full_schedule_query_representatives"]
        assert domain >= M + R and math.gcd(protocol["table_step"], domain) == 1
        query_offset = (protocol["table_offset"] + protocol["table_step"] * M) % domain
        shift = ((query_offset - protocol["table_offset"]) *
                 pow(protocol["table_step"], -1, domain)) % domain
        assert shift == M and M + R <= domain
        bases[K] = {"receipt_sha256": sha(path), "key_path": key_path,
                    "key_sha256": sha(key_path),
                    "enumerated_set_sha256": base["enumerated_set_sha256"],
                    "B": 166 * K, "pair_domain": domain,
                    "full_schedule_capacity_margin": domain - M - R,
                    "query_offset": query_offset}
    source_hashes = {path.name: sha(path) for path in zero_stage.FROZEN}
    assert all(sha(path) == expected for path, expected in zero_stage.FROZEN.items())
    report = {
        "kind": "n83_minimum_capacity_base_matched_stage_trial",
        "status": "running", "timing_tier": protocol["timing_tier"],
        "curve_id": protocol["curve_id"], "workload_id": target["workload_id"],
        "public_target": target["public_target"],
        "target_fixture_sha256": sha(target_path),
        "protocol_sha256": sha(protocol_path),
        "driver_source_sha256": sha(Path(__file__)),
        "source_hashes": source_hashes,
        "generated_field_sha256": sha(HEADER),
        "host": {"machine": platform.machine(), "system": platform.system(),
                 "release": platform.release()},
        "bases": {str(K): {key: value for key, value in data.items()
                            if key != "key_path"} for K, data in bases.items()},
        "cells": [],
    }
    save(report)
    with tempfile.TemporaryDirectory(prefix="native-minimal-", dir=HERE) as tmp:
        generated = Path(tmp) / "generated"
        generated.mkdir()
        pairs, core, source = zero_stage.generated_sources(generated)
        shutil.copyfile(HEADER, generated / "eccF83.h")
        report["generated_source_hashes"] = {
            path.name: sha(path) for path in (pairs, core, source, generated / "eccF83.h")}
        report["binary_builds"] = []
        for K in protocol["orbit_counts"]:
            binary = Path(tmp) / f"pairclaw_k{K}"
            command = ["c++", *protocol["native_flags"],
                       f"-DECC2K83_ORBITS={K}", str(source), "-o", str(binary)]
            subprocess.run(command, check=True, capture_output=True, text=True)
            report["binary_builds"].append({"K": K, "command": command,
                                             "binary_sha256": sha(binary)})
        save(report)
        for K in protocol["order_orbit_counts"]:
            base = bases[K]
            binary = Path(tmp) / f"pairclaw_k{K}"
            command = [str(binary), str(base["key_path"]), *target_xy,
                       str(protocol["stage_table_descriptors"]),
                       str(protocol["stage_query_representatives"]),
                       str(protocol["table_batch"]), str(protocol["table_step"]),
                       str(protocol["table_offset"]), str(protocol["table_step"]),
                       str(base["query_offset"]), str(protocol["bits_per_key"]),
                       str(protocol["hashes"]), "0", "0", str(protocol["workers"]),
                       str(protocol["representative_batch"])]
            env = os.environ.copy()
            env["ECC2K83_CANDIDATE_TMPDIR"] = tmp
            row = {"K": K, "B": base["B"],
                   "base_enumerated_set_sha256": base["enumerated_set_sha256"],
                   "query_offset": base["query_offset"],
                   "command": command,
                   "started_at_utc": datetime.now(timezone.utc).isoformat()}
            started = time.perf_counter()
            try:
                completed = subprocess.run(command, capture_output=True, text=True,
                                           env=env, timeout=300)
                row["returncode"] = completed.returncode
                row["stderr"] = completed.stderr[-4000:]
                if completed.returncode == 0:
                    row["native_result"] = json.loads(completed.stdout)
                    assert row["native_result"]["actual_B"] == base["B"]
                    row["status"] = "completed"
                else:
                    row["status"] = "native_failure"
            except subprocess.TimeoutExpired as error:
                row["status"] = "timeout"
                row["stderr"] = (error.stderr or b"").decode(errors="replace")[-4000:]
            row["subprocess_wall_seconds"] = time.perf_counter() - started
            row["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
            report["cells"].append(row)
            save(report)
    report["status"] = "completed" if all(
        row["status"] == "completed" for row in report["cells"]) else "partial"
    save(report)
    print(json.dumps({"status": report["status"], "cells": [
        {"K": row["K"], "wall_seconds": row["subprocess_wall_seconds"],
         "peak_rss_bytes": row.get("native_result", {}).get("peak_rss_bytes")}
        for row in report["cells"]]}))


if __name__ == "__main__":
    main()
