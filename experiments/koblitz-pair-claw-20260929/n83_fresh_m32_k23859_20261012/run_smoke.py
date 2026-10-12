#!/usr/bin/env python3
"""Run the fresh public point through a bounded native M20/R18 smoke cell."""

import argparse
import hashlib
import json
import os
import platform
import resource
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=int, default=1)
    parser.add_argument("--full-shape", action="store_true",
                        help="run one M32/R29 wave under an 8 GiB address-space cap on Linux")
    args = parser.parse_args()
    assert args.attempt >= 1
    if args.full_shape:
        assert platform.system() == "Linux", "full-shape cap requires Linux"
    prefix = "fullshape" if args.full_shape else "smoke"
    stem = prefix if args.attempt == 1 else f"{prefix}_attempt{args.attempt}"
    result_path = HERE / f"{stem}_result.json"
    receipt_path = HERE / f"{stem}_receipt.json"
    assert not result_path.exists() and not receipt_path.exists(), "smoke exists"
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    target = json.loads((HERE / "target_fixture.json").read_text())
    assert sha(HERE / "target_fixture.json") == protocol["target_fixture_sha256"]
    base = json.loads((PAIR / "n83_base_size_search_20261012/minimal_base.json").read_text())
    assert protocol["factor_base_receipt_sha256"] == sha(
        PAIR / "n83_base_size_search_20261012/minimal_base.json")
    key_path = PAIR / base["factor_base"]["key_and_log_file"]
    assert sha(key_path) == protocol["factor_base_file_sha256"]
    workload = protocol["workload"]
    table_count = workload["table_descriptors"] if args.full_shape else 1 << 20
    query_count = (workload["query_representatives_per_wave"]
                   if args.full_shape else 1 << 18)
    timeout_seconds = protocol["single_wave_timeout_seconds"] if args.full_shape else 300
    assert all(sha(path) == digest for path, digest in zero_stage.FROZEN.items())
    assert sha(HEADER) == (
        "33219306bc0db8a17e81aa3863a643b94cc96905018ac9ef38aa2c22d354738f")
    onb = field.Onb(83)
    target_xy = [format(onb.toCoords(value), "x")
                 for value in target["public_point_onb_raw"]]
    architecture = platform.machine().lower()
    if architecture in ("arm64", "aarch64"):
        architecture_flags = ["-march=armv8.2-a+crypto"]
    elif architecture in ("x86_64", "amd64"):
        architecture_flags = ["-mpclmul", "-msse2"]
    else:
        raise RuntimeError(f"unsupported architecture {architecture}")
    receipt = {
        "kind": "n83_fresh_minimum_base_native_smoke",
        "status": "started",
        "workload_id": protocol["workload_id"],
        "target_public_point_onb_raw": target["public_point_onb_raw"],
        "protocol_sha256": sha(protocol_path),
        "target_fixture_sha256": sha(HERE / "target_fixture.json"),
        "base_file_sha256": sha(key_path),
        "source_sha256": {str(path.relative_to(ROOT)): sha(path)
                          for path in zero_stage.FROZEN},
        "generated_field_header_sha256": sha(HEADER),
        "driver_sha256": sha(Path(__file__)),
        "architecture": architecture,
        "shape": "M32_R29_wave0" if args.full_shape else "M20_R18_smoke",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "limits": {"table_descriptors": table_count,
                   "query_representatives": query_count,
                   "timeout_seconds": timeout_seconds,
                   "address_space_cap_bytes": workload["memory_cap_bytes"]
                   if args.full_shape else None},
        "timing_tier": "exploratory_local_unisolated",
    }
    save(receipt_path, receipt)
    with tempfile.TemporaryDirectory(prefix="n83-fresh-smoke-") as tmp:
        work = Path(tmp)
        generated = work / "generated"
        generated.mkdir()
        pairs, core, source = zero_stage.generated_sources(generated)
        shutil.copyfile(HEADER, generated / "eccF83.h")
        binary = work / "pairclaw"
        build = ["c++", "-O3", "-std=c++17", *architecture_flags,
                 "-DECC2K83_FAST_KEYER=1", "-DECC2K83_ORBITS=23859",
                 str(source), "-o", str(binary)]
        compile_result = subprocess.run(build, capture_output=True, text=True,
                                        timeout=300)
        receipt["build_returncode"] = compile_result.returncode
        receipt["build_stderr"] = compile_result.stderr[-4000:]
        receipt["generated_source_sha256"] = {
            path.name: sha(path) for path in (pairs, core, source, generated / "eccF83.h")}
        if compile_result.returncode != 0:
            receipt["status"] = "build_failure"
            save(receipt_path, receipt)
            return
        receipt["binary_sha256"] = sha(binary)
        command = [str(binary), str(key_path), *target_xy,
                   str(table_count), str(query_count), str(protocol["table_batch"]),
                   str(workload["table_step"]), str(workload["table_offset"]),
                   str(workload["table_step"]), str(workload["query_offset"]),
                   str(workload["bits_per_key"]), str(workload["hashes"]),
                   "0", "0", str(workload["workers"]),
                   str(protocol["representative_batch"])]
        receipt["command_without_executable_or_base_path"] = command[2:]
        started = time.perf_counter()
        def bounded_address_space():
            cap = workload["memory_cap_bytes"]
            resource.setrlimit(resource.RLIMIT_AS, (cap, cap))

        try:
            environment = os.environ.copy()
            environment["ECC2K83_CANDIDATE_TMPDIR"] = str(work)
            completed = subprocess.run(command, capture_output=True, text=True,
                                       timeout=timeout_seconds, env=environment,
                                       preexec_fn=bounded_address_space
                                       if args.full_shape else None)
            receipt["subprocess_wall_seconds"] = time.perf_counter() - started
            receipt["native_returncode"] = completed.returncode
            receipt["native_stderr"] = completed.stderr[-4000:]
            if completed.returncode == 0:
                native = json.loads(completed.stdout)
                save(result_path, native)
                receipt["native_result_sha256"] = sha(result_path)
                receipt["status"] = "completed"
            else:
                receipt["status"] = "native_failure"
                receipt["native_stdout_tail"] = completed.stdout[-4000:]
        except subprocess.TimeoutExpired as error:
            receipt["status"] = "timeout"
            receipt["subprocess_wall_seconds"] = time.perf_counter() - started
            receipt["native_stderr"] = (error.stderr or b"").decode(
                errors="replace")[-4000:]
    receipt["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    save(receipt_path, receipt)
    print(json.dumps({"status": receipt["status"],
                      "workload_id": protocol["workload_id"]}))


if __name__ == "__main__":
    main()
