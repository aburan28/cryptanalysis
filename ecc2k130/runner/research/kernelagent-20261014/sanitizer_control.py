"""Calibrate racecheck with a planted hazard, then check the inverse on H100."""

import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import modal

RUNNER = Path(__file__).resolve().parents[2] if modal.is_local() else Path("/opt/ecc2k130")
IMAGE_ID = os.environ.get("ECC_BENCH_IMAGE", "im-LEaik53IOCmWvHm1O2UUPQ")
app = modal.App("ecc2k130-sanitizer-controls")
image = modal.Image.from_id(IMAGE_ID) if modal.is_local() else None

CONTROL_SOURCE = r"""
#include <cuda_runtime.h>
#include <cstdio>
__global__ void control(int *out) {
    __shared__ volatile int word;
#if PLANTED_RACE
    if (threadIdx.x < 2) word = int(threadIdx.x);
#else
    if (threadIdx.x == 0) word = 1;
#endif
    __syncthreads();
    out[threadIdx.x] = word;
}
int main() {
    int *out = nullptr;
    if (cudaMalloc(&out, 64 * sizeof(int)) != cudaSuccess) return 2;
    control<<<1, 64>>>(out);
    if (cudaGetLastError() != cudaSuccess) return 3;
    if (cudaDeviceSynchronize() != cudaSuccess) return 4;
    cudaFree(out);
    return 0;
}
"""


def command_record(command, cwd=None, timeout=300):
    try:
        completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                                   timeout=timeout)
        return {"command": command, "returncode": completed.returncode,
                "output": completed.stdout + completed.stderr, "timed_out": False}
    except subprocess.TimeoutExpired as error:
        stdout, stderr = error.stdout or b"", error.stderr or b""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        return {"command": command, "returncode": None,
                "output": stdout + stderr, "timed_out": True}


def diagnostic(arch: str, include_sources: dict, test_source: str, check_candidate: bool):
    root = Path("/opt/ecc2k130")
    result = {"started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "image_id": IMAGE_ID, "arch": arch, "check_candidate": check_candidate,
              "control_source_sha256": hashlib.sha256(CONTROL_SOURCE.encode()).hexdigest(),
              "candidate_source_sha256": {name: hashlib.sha256(content.encode()).hexdigest()
                                          for name, content in include_sources.items()},
              "test_source_sha256": hashlib.sha256(test_source.encode()).hexdigest()}

    def finish(outcome):
        result["outcome"] = outcome
        result["completed_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return result

    (root / "sanitizer-control.cu").write_text(CONTROL_SOURCE)
    result["gpu"] = command_record(["nvidia-smi", "--query-gpu=name,uuid,driver_version,compute_cap",
                                     "--format=csv,noheader"])
    result["confidential_compute"] = command_record(["nvidia-smi", "-q", "-d", "CONFIDENTIAL_COMPUTE"])
    result["compiler"] = command_record(["nvcc", "--version"])
    sanitizer = shutil.which("compute-sanitizer")
    if sanitizer is None:
        return finish("race_checker_unavailable")
    result["race_checker_version"] = command_record([sanitizer, "--version"])
    result["controls"] = []
    for planted in (False, True):
        binary = root / ("sanitizer-planted" if planted else "sanitizer-clean")
        record = {"planted_race": planted}
        record["build"] = command_record(
            ["nvcc", "-O3", "-std=c++17", f"-arch={arch}", "-lineinfo",
             f"-DPLANTED_RACE={int(planted)}", "sanitizer-control.cu", "-o", str(binary)],
            cwd=root)
        result["controls"].append(record)
        if record["build"]["returncode"]:
            return finish("control_build_failed")
        record["binary_sha256"] = hashlib.sha256(binary.read_bytes()).hexdigest()
        record["run"] = command_record([str(binary)], cwd=root)
        if record["run"]["returncode"]:
            return finish("control_run_failed")
        record["racecheck"] = command_record(
            [sanitizer, "--tool", "racecheck", "--error-exitcode", "86", str(binary)],
            cwd=root)
        if "Error: Device not supported" in record["racecheck"]["output"]:
            return finish("race_checker_unsupported_device")
        output = record["racecheck"]["output"]
        zero = bool(re.search(r"(?:RACECHECK SUMMARY: 0 hazards|ERROR SUMMARY: 0 errors)", output))
        hazard = "hazard" in output.lower() or "race reported" in output.lower()
        if (not planted and (record["racecheck"]["returncode"] or not zero)):
            return finish("clean_control_failed_or_ambiguous")
        if planted and (record["racecheck"]["returncode"] != 86 or not hazard):
            return finish("planted_race_not_detected")

    if not check_candidate:
        return finish("controls_passed")
    for name, content in include_sources.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    (root / "test-sanitized-inverse.cu").write_text(test_source)
    binary = root / "test-sanitized-inverse"
    record = {}
    result["candidate"] = record
    record["build"] = command_record(
        ["nvcc", "-O3", "-std=c++17", f"-arch={arch}", "-lineinfo",
         "-DECC_INVERSE_DOUBLE_BUFFER=1", "-DGOAL22_GROUP_BARRIER_TEST=1",
         "-DGOAL22_TEST_W4_ONLY=1", "-DECC_THREADS=640",
         "-DECC_PACKED_SINGLE_PRODUCT=1", "-DECC_PACKED_CLMAD=1",
         "-DECC_PACKED_DIRECT_REDUCE=1", "-DECC_PACKED_PERM_SIGMA=3",
         "-DECC_PACKED_UNROLL_INV=1", "-Iinclude", "test-sanitized-inverse.cu",
         "-o", str(binary)], cwd=root)
    if record["build"]["returncode"]:
        return finish("candidate_build_failed")
    record["binary_sha256"] = hashlib.sha256(binary.read_bytes()).hexdigest()
    record["run"] = command_record([str(binary)], cwd=root, timeout=180)
    if record["run"]["returncode"] or "FAIL" in record["run"]["output"]:
        return finish("candidate_reference_failed")
    record["racecheck"] = command_record(
        [sanitizer, "--tool", "racecheck", "--error-exitcode", "86", str(binary)],
        cwd=root, timeout=600)
    output = record["racecheck"]["output"]
    if record["racecheck"]["returncode"] or not re.search(
            r"(?:RACECHECK SUMMARY: 0 hazards|ERROR SUMMARY: 0 errors)", output):
        return finish("candidate_racecheck_failed_or_ambiguous")
    return finish("candidate_cross_device_racecheck_passed")


@app.function(image=image, gpu="RTX-PRO-6000", cpu=4, memory=8192,
              timeout=1200, max_containers=1)
def blackwell_controls(include_sources: dict, test_source: str):
    return diagnostic("sm_120", include_sources, test_source, False)


@app.function(image=image, gpu="H100", cpu=4, memory=8192,
              timeout=1800, max_containers=1)
def h100_controls_and_candidate(include_sources: dict, test_source: str):
    return diagnostic("sm_90", include_sources, test_source, True)


@app.local_entrypoint()
def main(gpu: str, output: str):
    output_path = Path(output)
    if output_path.exists():
        raise FileExistsError(output_path)
    if gpu not in ("blackwell", "h100"):
        raise ValueError("gpu must be blackwell or h100")
    names = subprocess.check_output(["git", "ls-files", "--", "include"],
                                    cwd=RUNNER, text=True).splitlines()
    sources = {name: (RUNNER / name).read_text() for name in names}
    test_source = (RUNNER / "research/test_collective_inverse.cu").read_text()
    if gpu == "blackwell":
        result = blackwell_controls.remote(sources, test_source)
    else:
        result = h100_controls_and_candidate.remote(sources, test_source)
    result["driver_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result["source_commit"] = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=RUNNER, text=True).strip()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"receipt": str(output_path), "outcome": result["outcome"]}))
