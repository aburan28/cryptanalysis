"""Build and race-check the default-off grouped-inverse double buffer on Modal."""

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
sys.path.insert(0, str(RUNNER))
IMAGE_ID = os.environ.get("ECC_BENCH_IMAGE", "im-LEaik53IOCmWvHm1O2UUPQ")
app = modal.App("ecc2k130-double-buffer-inverse-gate")
image = modal.Image.from_id(IMAGE_ID) if modal.is_local() else None


def command_record(command, cwd=None, timeout=600):
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


@app.function(image=image, gpu="RTX-PRO-6000", cpu=4, memory=8192,
              timeout=1800, max_containers=1)
def check_inverse(sources: dict, test_source: str, settings: dict):
    root = Path("/opt/ecc2k130")
    result = {"started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "image_id": IMAGE_ID, "settings": settings,
              "source_sha256": {name: hashlib.sha256(content.encode()).hexdigest()
                                for name, content in sources.items()},
              "test_source_sha256": hashlib.sha256(test_source.encode()).hexdigest()}

    def finish(outcome):
        result["outcome"] = outcome
        result["completed_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return result

    for name, content in sources.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    (root / "test-double-buffer.cu").write_text(test_source)
    result["gpu"] = command_record(["nvidia-smi", "--query-gpu=name,uuid,driver_version,compute_cap",
                                     "--format=csv,noheader"])
    result["compiler"] = command_record(["nvcc", "--version"])
    build = ["make", "-B", "ecc2k130", "ARCH=-gencode arch=compute_120,code=sm_120",
             *[f"{key}={value}" for key, value in settings.items()]]
    result["production_build"] = command_record(build, cwd=root)
    if result["production_build"]["returncode"]:
        return finish("production_build_failed")
    result["production_binary_sha256"] = hashlib.sha256((root / "ecc2k130").read_bytes()).hexdigest()

    result["device_tests"] = []
    for threads, extra in ((512, []), (640, ["-DGOAL22_TEST_W4_ONLY=1"])):
        binary = root / f"test-double-buffer-{threads}"
        command = ["nvcc", "-O3", "-std=c++17", "-arch=sm_120", "-lineinfo",
                   "-DECC_INVERSE_DOUBLE_BUFFER=1", "-DGOAL22_GROUP_BARRIER_TEST=1",
                   f"-DECC_THREADS={threads}", "-DECC_PACKED_SINGLE_PRODUCT=1",
                   "-DECC_PACKED_CLMAD=1", "-DECC_PACKED_DIRECT_REDUCE=1",
                   "-DECC_PACKED_PERM_SIGMA=3", "-DECC_PACKED_UNROLL_INV=1",
                   *extra, "-Iinclude", "test-double-buffer.cu", "-o", str(binary)]
        record = {"threads": threads, "build": command_record(command, cwd=root)}
        result["device_tests"].append(record)
        if record["build"]["returncode"]:
            return finish("device_build_failed")
        record["binary_sha256"] = hashlib.sha256(binary.read_bytes()).hexdigest()
        record["check"] = command_record([str(binary)], cwd=root, timeout=180)
        if record["check"]["returncode"] or "FAIL" in record["check"]["output"]:
            return finish("device_reference_failed")
        if threads == 640:
            sanitizer = shutil.which("compute-sanitizer")
            if sanitizer is None:
                return finish("race_checker_unavailable")
            result["race_checker_version"] = command_record([sanitizer, "--version"])
            record["racecheck"] = command_record(
                [sanitizer, "--tool", "racecheck", "--error-exitcode", "86", str(binary)],
                cwd=root, timeout=600)
            if "Error: Device not supported" in record["racecheck"]["output"]:
                return finish("race_checker_unsupported_device")
            if record["racecheck"]["returncode"] or not re.search(
                    r"(?:RACECHECK SUMMARY: 0 hazards|ERROR SUMMARY: 0 errors)",
                    record["racecheck"]["output"]):
                return finish("racecheck_failed_or_ambiguous")
    return finish("passed")


@app.local_entrypoint()
def main(output: str):
    from tune_frobenius_v3 import BASE

    output_path = Path(output)
    if output_path.exists():
        raise FileExistsError(output_path)
    names = subprocess.check_output(
        ["git", "ls-files", "--", "Makefile", "include", "src", "generated", "codegen"],
        cwd=RUNNER, text=True).splitlines()
    sources = {name: (RUNNER / name).read_text() for name in names}
    test_source = (RUNNER / "research/test_collective_inverse.cu").read_text()
    settings = {**BASE, "PACKED_INLINE_SIGMA": 1, "PACKED_TOP_CLMAD": 0,
                "GPUFLAGS": "-Xptxas -v -DECC_INVERSE_DOUBLE_BUFFER=1"}
    result = check_inverse.remote(sources, test_source, settings)
    result["driver_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"receipt": str(output_path), "outcome": result["outcome"]}))
    if result["outcome"] != "passed":
        raise SystemExit(1)
