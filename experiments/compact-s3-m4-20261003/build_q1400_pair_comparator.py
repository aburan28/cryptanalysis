#!/usr/bin/env python3
"""Compile the frozen Q1400 ARM64 native pair comparator without Sage work."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEFAULT_BUILD_ROOT = Path("/private/tmp/q1400-native-pair-20261004")
RECEIPT = HERE / "native_q1400_pair_build_receipt.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-root", type=Path, default=DEFAULT_BUILD_ROOT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    protocol_path = HERE / "q1400_pair_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["proposal_id"] == "Q1400"
    assert protocol["candidate_id"] is None and protocol["run_id"] is None
    assert protocol["isogeny"] == "none"
    source = HERE / "native_q1400_pair_comparator.cpp"
    pdp = protocol["point_decomposition"]
    assert pdp["native_source_sha256"] == sha(source)
    for name, digest in pdp["native_dependency_sha256"].items():
        assert sha(ROOT / name) == digest, name
    assert platform.machine() == "arm64"
    compiler = shutil.which("clang++")
    assert compiler is not None
    flags = pdp["native_compile_flags"]
    build_root = args.build_root.resolve()
    binary = build_root / "native_q1400_pair_comparator"
    log_path = build_root / "clang-build.log"
    command = [compiler, *flags, str(source), "-o", str(binary)]
    if args.check:
        receipt = json.loads(RECEIPT.read_text())
        assert receipt["status"] == "PASS"
        assert receipt["command"] == command
        assert receipt["native_source_sha256"] == sha(source)
        assert receipt["stage_protocol_sha256"] == sha(protocol_path)
        assert receipt["binary_sha256"] == sha(binary)
        assert receipt["build_log_sha256"] == sha(log_path)
        assert receipt["source_sha256"] == sha(Path(__file__))
        print(f"PASS {RECEIPT}")
        return
    build_root.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter_ns()
    with log_path.open("w") as log:
        completed = subprocess.run(command, stdout=log,
                                   stderr=subprocess.STDOUT, check=False)
    build_ns = time.perf_counter_ns() - started
    if completed.returncode:
        print(log_path.read_text()[-5000:])
        raise SystemExit(completed.returncode)
    assert binary.is_file()
    record = {
        "kind": "q1400_native_pair_comparator_build",
        "status": "PASS",
        "proposal_id": "Q1400",
        "candidate_id": None,
        "run_id": None,
        "curve_id": protocol["curve_id"],
        "isogeny": "none",
        "field_degree": 83,
        "architecture": platform.machine(),
        "operating_system": platform.system(),
        "command": command,
        "compiler_version": subprocess.check_output(
            [compiler, "--version"], text=True).splitlines()[0],
        "build_wall_ns": build_ns,
        "binary_path": str(binary),
        "binary_sha256": sha(binary),
        "build_log_sha256": sha(log_path),
        "stage_protocol_sha256": sha(protocol_path),
        "native_source_sha256": sha(source),
        "native_dependency_sha256": pdp["native_dependency_sha256"],
        "source_sha256": sha(Path(__file__)),
    }
    RECEIPT.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "PASS", "binary_sha256": record[
        "binary_sha256"], "build_wall_ns": build_ns}))


if __name__ == "__main__":
    main()
