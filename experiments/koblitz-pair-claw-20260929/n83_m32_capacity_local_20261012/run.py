#!/usr/bin/env python3
"""Build an M32 Bloom table for the frozen N83 base under an RSS watchdog."""

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
PAIR = HERE.parent
ROOT = PAIR.parents[1]
CODEGEN = ROOT / "ecc2k130/runner/codegen"
HEADER = ROOT / "ecc2k130/runner/generated/eccF83.h"
sys.path[:0] = [str(CODEGEN), str(PAIR)]

import field  # noqa: E402
import bench_n83_zero_run_stage as zero_stage  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def rss_bytes(pid):
    result = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)],
                            capture_output=True, text=True, timeout=5)
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return int(result.stdout.strip().split()[0]) * 1024


def stop_child(process):
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def main():
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    parent_path = (HERE / protocol["parent_protocol"]).resolve()
    assert sha(parent_path) == protocol["parent_protocol_sha256"]
    parent = json.loads(parent_path.read_text())
    assert parent["workload_id"] == protocol["workload_id"]
    assert parent["target_public_point_onb_raw"] == protocol[
        "public_target_onb_raw"]
    assert parent["factor_base_orbits_K"] == protocol["K"]
    assert parent["actual_usable_points_B_before_folding"] == protocol["B"]
    key_path = PAIR / "n83_base_size_search_20261012/minimal_base_keys_and_logs.bin"
    assert sha(key_path) == protocol["base_file_sha256"]
    assert all(sha(path) == digest for path, digest in zero_stage.FROZEN.items())
    assert sha(HEADER) == (
        "33219306bc0db8a17e81aa3863a643b94cc96905018ac9ef38aa2c22d354738f")
    assert platform.system() == "Darwin" and platform.machine().lower() == "arm64"
    assert protocol["M"] == 1 << 32 and protocol["Q"] == 1
    assert protocol["bits_per_key"] == 15 and protocol["hashes"] == 10
    domain = 83 * protocol["K"] * (protocol["K"] - 1)
    assert math.gcd(protocol["table_step"], domain) == 1
    assert ((protocol["query_offset"] - protocol["table_offset"]) *
            pow(protocol["table_step"], -1, domain)) % domain == protocol["M"]
    assert protocol["M"] + protocol["Q"] <= domain
    assert rss_bytes(os.getpid()) is not None, "RSS monitor unavailable"
    assert shutil.disk_usage(HERE).free >= protocol["minimum_free_disk_bytes"]
    output_path = HERE / "run_record.json"
    result_path = HERE / "native_result.json"
    progress_path = HERE / "progress.json"
    assert not output_path.exists() and not result_path.exists(), "frozen run exists"
    onb = field.Onb(83)
    target_xy = [format(onb.toCoords(value), "x")
                 for value in protocol["public_target_onb_raw"]]
    record = {
        "kind": "n83_m32_full_filter_local_capacity_run",
        "status": "started",
        "curve_id": protocol["curve_id"],
        "workload_id": protocol["workload_id"],
        "protocol_sha256": sha(protocol_path),
        "parent_protocol_sha256": sha(parent_path),
        "base_file_sha256": sha(key_path),
        "driver_sha256": sha(Path(__file__)),
        "source_sha256": {str(path.relative_to(ROOT)): sha(path)
                          for path in zero_stage.FROZEN},
        "header_sha256": sha(HEADER),
        "host": {"system": platform.system(), "machine": platform.machine(),
                 "release": platform.release()},
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "rss_cap_bytes": protocol["rss_cap_bytes"],
        "rss_sample_interval_ms": protocol["rss_watchdog_sample_ms"],
        "timeout_seconds": protocol["timeout_seconds"],
        "measurement_tier": protocol["measurement_tier"],
    }
    save(output_path, record)
    with tempfile.TemporaryDirectory(prefix="n83-m32-capacity-") as temporary:
        work = Path(temporary)
        generated = work / "generated"
        generated.mkdir()
        pairs, core, source = zero_stage.generated_sources(generated)
        shutil.copyfile(HEADER, generated / "eccF83.h")
        record["generated_source_sha256"] = {
            path.name: sha(path) for path in (pairs, core, source, generated / "eccF83.h")}
        binary = work / "pairclaw"
        build = ["c++", "-O3", "-std=c++17", "-march=armv8.2-a+crypto",
                 "-DECC2K83_FAST_KEYER=1", "-DECC2K83_ORBITS=23859",
                 str(source), "-o", str(binary)]
        compiled = subprocess.run(build, capture_output=True, text=True,
                                  timeout=300)
        record["build_returncode"] = compiled.returncode
        record["build_stderr"] = compiled.stderr[-4000:]
        if compiled.returncode != 0:
            record["status"] = "build_failure"
            save(output_path, record)
            return
        record["binary_sha256"] = sha(binary)
        command = [str(binary), str(key_path), *target_xy,
                   str(protocol["M"]), str(protocol["Q"]),
                   str(protocol["table_batch"]), str(protocol["table_step"]),
                   str(protocol["table_offset"]), str(protocol["table_step"]),
                   str(protocol["query_offset"]), str(protocol["bits_per_key"]),
                   str(protocol["hashes"]), "0", str(protocol["query_start"]),
                   str(protocol["workers"]), str(protocol["representative_batch"])]
        record["command_arguments_after_base_path"] = command[2:]
        environment = os.environ.copy()
        environment["ECC2K83_CANDIDATE_TMPDIR"] = str(work)
        stdout_path = HERE / "native.stdout.txt"
        stderr_path = HERE / "native.stderr.txt"
        with stdout_path.open("x") as stdout, stderr_path.open("x") as stderr:
            process = subprocess.Popen(command, env=environment, stdout=stdout,
                                       stderr=stderr)
            record["native_pid"] = process.pid
            record["native_started_at_utc"] = datetime.now(timezone.utc).isoformat()
            started = time.monotonic()
            max_sampled_rss = 0
            missing_samples = 0
            last_progress = started
            while process.poll() is None:
                current = rss_bytes(process.pid)
                if current is None:
                    missing_samples += 1
                    if missing_samples >= 3:
                        record["status"] = "rss_monitor_failure"
                        stop_child(process)
                        break
                else:
                    missing_samples = 0
                    max_sampled_rss = max(max_sampled_rss, current)
                    if current >= protocol["rss_cap_bytes"]:
                        record["status"] = "rss_watchdog_cap_reached"
                        stop_child(process)
                        break
                now = time.monotonic()
                if now - started >= protocol["timeout_seconds"]:
                    record["status"] = "timeout"
                    stop_child(process)
                    break
                if now - last_progress >= 5:
                    save(progress_path, {
                        "native_pid": process.pid,
                        "elapsed_seconds": now - started,
                        "max_sampled_rss_bytes": max_sampled_rss,
                        "status": "running",
                    })
                    last_progress = now
                time.sleep(protocol["rss_watchdog_sample_ms"] / 1000)
            record["native_returncode"] = process.wait()
            record["native_wall_seconds"] = time.monotonic() - started
            record["max_sampled_rss_bytes"] = max_sampled_rss
        record["native_stdout_sha256"] = sha(stdout_path)
        record["native_stderr_sha256"] = sha(stderr_path)
        record["native_stderr_tail"] = stderr_path.read_text(errors="replace")[-4000:]
        if record["status"] == "started":
            if record["native_returncode"] == 0:
                native = json.loads(stdout_path.read_text())
                save(result_path, native)
                record["native_result_sha256"] = sha(result_path)
                record["status"] = "completed"
            else:
                record["status"] = "native_failure"
    record["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    save(output_path, record)
    save(progress_path, {"status": record["status"],
                         "max_sampled_rss_bytes": record.get("max_sampled_rss_bytes")})
    print(json.dumps({"status": record["status"],
                      "max_sampled_rss_bytes": record.get("max_sampled_rss_bytes"),
                      "native_returncode": record.get("native_returncode")}))


if __name__ == "__main__":
    main()
