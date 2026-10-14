"""Profile the pinned ECC2K-130 production walk on one Modal GPU.

This is a bounded Nsight Compute application replay. Its counters describe the
kernel under replay; paired ordinary runs remain the throughput evidence.
"""

import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import modal

RUNNER = Path(__file__).resolve().parents[2] if modal.is_local() else Path("/opt/ecc2k130")
sys.path.insert(0, str(RUNNER))
from codegen.profilereport import NCU_BINARY, NCU_PACKAGE, profileResult, profilerVersionError

BASELINE_COMMIT = "1f8e6847de9e207880bd3be63835c3f56eb182d5"
IMAGE_ID = os.environ.get("ECC_BENCH_IMAGE", "im-LEaik53IOCmWvHm1O2UUPQ")
app = modal.App("ecc2k130-production-kernel-profile")
image = modal.Image.from_id(IMAGE_ID).apt_install(NCU_PACKAGE)


def command_record(command, cwd=None, timeout=900):
    try:
        completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                                   timeout=timeout)
        return {"command": command, "returncode": completed.returncode,
                "output": completed.stdout + completed.stderr, "timed_out": False}
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout or b""
        stderr = error.stderr or b""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        return {"command": command, "returncode": None,
                "output": stdout + stderr, "timed_out": True}


@app.function(image=image, gpu="RTX-PRO-6000", cpu=4, memory=8192,
              timeout=1800, max_containers=1)
def profile_exact(sources: dict, settings: dict, baseline_commit: str):
    root = Path("/opt/ecc2k130")
    result = {"started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "baseline_commit": baseline_commit, "image_id": IMAGE_ID,
              "settings": settings, "source_sha256": {name: hashlib.sha256(content.encode()).hexdigest()
                                                  for name, content in sources.items()}}
    for name, content in sources.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    result["gpu"] = command_record(["nvidia-smi", "--query-gpu=name,uuid,driver_version,compute_cap",
                                     "--format=csv,noheader"])
    result["compiler"] = command_record(["nvcc", "--version"])
    result["profiler_version"] = command_record([NCU_BINARY, "--version"])
    version = result["profiler_version"]
    if version["returncode"] or profilerVersionError(version["output"]):
        result["outcome"] = "profiler_version_failed"
        return result
    build = ["make", "-B", "ecc2k130", "ARCH=-gencode arch=compute_120,code=sm_120",
             *[f"{key}={value}" for key, value in settings.items()]]
    result["build"] = command_record(build, cwd=root)
    if result["build"]["returncode"]:
        result["outcome"] = "build_failed"
        return result
    result["binary_sha256"] = hashlib.sha256((root / "ecc2k130").read_bytes()).hexdigest()
    target = ["./ecc2k130", "--packed", "--curve", "131", "--threads", "120320",
              "--steps", "4", "--launches", "1", "--run-id", "11000",
              "--dp-weight", "32", "--verify", "0", "--dp-file", "/tmp/profile-dp.bin"]
    result["normal_run"] = command_record(target, cwd=root, timeout=180)
    if result["normal_run"]["returncode"] or "0 dropped)" not in result["normal_run"]["output"]:
        result["outcome"] = "normal_run_failed"
        return result
    command = [NCU_BINARY, "--target-processes", "all", "--kernel-name-base", "demangled",
               "--kernel-name", "regex:eccPacked131::walk", "--launch-count", "1",
               "--section", "SpeedOfLight", "--section", "LaunchStats",
               "--section", "Occupancy", "--section", "WarpStateStats",
               "--section", "SchedulerStats", "--section", "InstructionStats",
               "--section", "MemoryWorkloadAnalysis", "--replay-mode", "application",
               "--clock-control", "none", "--cache-control", "none", *target]
    result["profile_command"] = command
    profile = command_record(command, cwd=root, timeout=900)
    result["profile"] = {**profile, **profileResult(profile["returncode"] or 0,
                                                 profile["output"])}
    result["outcome"] = result["profile"].get("kind", "profile_unknown")
    result["completed_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return result


@app.local_entrypoint()
def main(output: str, baseline_commit: str = BASELINE_COMMIT):
    from tune_frobenius_v3 import BASE

    output_path = Path(output)
    if output_path.exists():
        raise FileExistsError(output_path)
    tree = f"{baseline_commit}:ecc2k130/runner"
    names = subprocess.check_output(
        ["git", "ls-tree", "-r", "--full-tree", "--name-only", tree, "--",
         "Makefile", "include", "src", "generated", "codegen"],
        cwd=RUNNER, text=True).splitlines()
    if "Makefile" not in names or "include/packedfrobeniusfused.cuh" not in names:
        raise ValueError("incomplete pinned public source")
    sources = {name: subprocess.check_output(["git", "show", f"{tree}/{name}"],
                                             cwd=RUNNER, text=True) for name in names}
    if any((RUNNER / name).read_text() != content for name, content in sources.items()):
        raise ValueError("working source differs from pinned public commit")
    settings = {**BASE, "PACKED_INLINE_SIGMA": 1, "PACKED_TOP_CLMAD": 0}
    result = profile_exact.remote(sources, settings, baseline_commit)
    result["driver_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"receipt": str(output_path), "outcome": result.get("outcome"),
                      "binary_sha256": result.get("binary_sha256")}))
    if result.get("outcome") != "profiled":
        raise SystemExit(1)
