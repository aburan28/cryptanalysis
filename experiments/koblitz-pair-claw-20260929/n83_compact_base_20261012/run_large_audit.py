#!/usr/bin/env python3
"""Audit all 33.2 million compact indexed points at K=200000."""

import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAIR = HERE.parent
ROOT = PAIR.parents[1]
sys.path[:0] = [str(ROOT / "ecc2k130/runner/codegen"), str(PAIR), str(HERE)]

import field  # noqa: E402
from generate import generate  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main():
    assert platform.machine().lower() in ("arm64", "aarch64")
    receipt_path = HERE / "large_audit.json"
    result_path = HERE / "large_compact_audit.json"
    assert not receipt_path.exists() and not result_path.exists()
    base_path = HERE / "large_base_keys_and_logs.bin"
    base = json.loads((HERE / "large_base.json").read_text())
    stage = json.loads((HERE / "large_stage.json").read_text())
    assert stage["status"] == "PASS" and base["K"] == 200000
    assert sha(base_path) == base["key_and_log_file_sha256"]
    parent_path = PAIR / "n83_fresh_m32_k23859_20261012/protocol.json"
    parent = json.loads(parent_path.read_text())
    assert stage["parent_protocol_sha256"] == sha(parent_path)
    onb = field.Onb(83)
    target_xy = [format(onb.toCoords(x), "x")
                 for x in parent["target_public_point_onb_raw"]]
    report = {
        "kind": "n83_k200000_complete_compact_expansion_audit",
        "status": "started",
        "K": base["K"],
        "B": base["actual_usable_points_B_before_folding"],
        "base_receipt_sha256": sha(HERE / "large_base.json"),
        "base_file_sha256": sha(base_path),
        "stage_receipt_sha256": sha(HERE / "large_stage.json"),
        "parent_protocol_sha256": sha(parent_path),
        "compact_source_sha256": sha(HERE / "compact_base.inc"),
        "driver_source_sha256": sha(Path(__file__)),
        "audit_define": "COMPACT_BASE_AUDIT=1",
        "timing_tier": "exploratory_local_unisolated",
    }
    save(receipt_path, report)
    with tempfile.TemporaryDirectory(prefix="n83-k200000-audit-") as temporary:
        work = Path(temporary)
        sources = work / "source"
        sources.mkdir()
        report["generated_source_sha256"] = generate(sources)
        binary = work / "pairclaw_audit"
        build = ["c++", "-O3", "-std=c++17", "-march=armv8.2-a+crypto",
                 "-DECC2K83_FAST_KEYER=1", "-DECC2K83_ORBITS=200000",
                 "-DCOMPACT_BASE_AUDIT=1", str(sources / "alt_main.cpp"),
                 "-o", str(binary)]
        try:
            compiled = subprocess.run(build, capture_output=True, text=True,
                                      timeout=300)
        except subprocess.TimeoutExpired as exc:
            report.update(status="build_timeout", timeout_seconds=exc.timeout)
            save(receipt_path, report)
            return
        report["build_returncode"] = compiled.returncode
        report["build_stderr"] = compiled.stderr[-4000:]
        if compiled.returncode != 0:
            report["status"] = "build_failure"
            save(receipt_path, report)
            return
        report["binary_sha256"] = sha(binary)
        native = [str(binary), str(base_path), *target_xy,
                  str(stage["M"]), str(stage["R"]), "1024",
                  str(parent["workload"]["table_step"]),
                  str(parent["workload"]["table_offset"]),
                  str(parent["workload"]["table_step"]),
                  str(stage["query_offset"]), "15", "10", "0", "0", "4", "8"]
        environment = os.environ.copy()
        environment["ECC2K83_CANDIDATE_TMPDIR"] = str(work)
        started = time.perf_counter()
        try:
            completed = subprocess.run(native, capture_output=True, text=True,
                                       env=environment, timeout=600)
        except subprocess.TimeoutExpired as exc:
            report.update(status="native_timeout", timeout_seconds=exc.timeout,
                          native_wall_seconds=time.perf_counter() - started)
            save(receipt_path, report)
            return
        report["native_wall_seconds"] = time.perf_counter() - started
        report["native_returncode"] = completed.returncode
        report["native_stderr"] = completed.stderr[-4000:]
        if completed.returncode != 0:
            report["status"] = "native_failure"
            report["native_stdout_tail"] = completed.stdout[-4000:]
            save(receipt_path, report)
            return
        save(result_path, json.loads(completed.stdout))
        report["result_sha256"] = sha(result_path)
        reference = json.loads((HERE / "large_compact.json").read_text())
        result = json.loads(result_path.read_text())
        fields = stage["parity_fields"]
        report["parity_fields"] = fields
        report["status"] = ("PASS" if all(result[key] == reference[key]
                                           for key in fields) else "result_mismatch")
    save(receipt_path, report)
    print(json.dumps({"status": report["status"], "K": base["K"],
                      "B": base["actual_usable_points_B_before_folding"]}))


if __name__ == "__main__":
    main()
