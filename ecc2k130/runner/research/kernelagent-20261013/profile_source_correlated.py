"""Retain a source-correlated Nsight profile of the pinned ECC2K-130 walk.

The build adds -lineinfo solely for CUDA/SASS correlation. Application replay
uses a fresh DP path per pass. These counters are diagnostic, not a throughput
comparison with ordinary production runs.
"""

import base64
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zlib

import modal

RUNNER = Path(__file__).resolve().parents[2] if modal.is_local() else Path("/opt/ecc2k130")
sys.path.insert(0, str(RUNNER))
from codegen.profilereport import NCU_BINARY, NCU_PACKAGE, profileResult, profilerVersionError

BASELINE_COMMIT = "1f8e6847de9e207880bd3be63835c3f56eb182d5"
IMAGE_ID = os.environ.get("ECC_BENCH_IMAGE", "im-LEaik53IOCmWvHm1O2UUPQ")
app = modal.App("ecc2k130-production-source-profile")
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
             "GPUFLAGS=-lineinfo -Xptxas -v",
             *[f"{key}={value}" for key, value in settings.items()]]
    result["build"] = command_record(build, cwd=root)
    if result["build"]["returncode"]:
        result["outcome"] = "build_failed"
        return result
    result["binary_sha256"] = hashlib.sha256((root / "ecc2k130").read_bytes()).hexdigest()
    target = ["./ecc2k130", "--packed", "--curve", "131", "--threads", "120320",
              "--steps", "64", "--launches", "1", "--run-id", "11000",
              "--dp-weight", "32", "--verify", "0", "--dp-file", "/tmp/profile-dp.bin"]
    Path(target[-1]).unlink(missing_ok=True)
    result["normal_run"] = command_record(target, cwd=root, timeout=180)
    if result["normal_run"]["returncode"] or "0 dropped)" not in result["normal_run"]["output"]:
        result["outcome"] = "normal_run_failed"
        return result
    # Application replay starts a fresh process per pass.  The DP file is
    # append-only and also an input on startup, so each pass needs a new path.
    launcher = root / "profile_launch.py"
    launcher.write_text("""import os
import sys
import tempfile

fd, path = tempfile.mkstemp(prefix="ecc2k130-profile-dp-", suffix=".bin")
os.close(fd)
print("PROFILE_DP_FILE=" + path, file=sys.stderr, flush=True)
os.execv("./ecc2k130", ["./ecc2k130", *sys.argv[1:], "--dp-file", path])
""")
    result["profile_launcher_sha256"] = hashlib.sha256(launcher.read_bytes()).hexdigest()
    report_base = Path(tempfile.mkdtemp(prefix="ecc2k130-ncu-")) / "walk"
    command = [NCU_BINARY, "--target-processes", "all", "--kernel-name-base", "demangled",
               "--kernel-name", "regex:eccPacked131::walk", "--launch-count", "1",
               "--section", "SpeedOfLight", "--section", "LaunchStats",
               "--section", "Occupancy", "--section", "WarpStateStats",
               "--section", "SchedulerStats", "--section", "InstructionStats",
               "--section", "ComputeWorkloadAnalysis", "--section", "SourceCounters",
               "--section", "MemoryWorkloadAnalysis", "--replay-mode", "application",
               "--clock-control", "none", "--cache-control", "none",
               "--import-source", "yes", "--source-folders", str(root),
               "--force-overwrite", "--export", str(report_base),
               sys.executable, str(launcher), *target[1:-2]]
    result["profile_command"] = command
    profile = command_record(command, cwd=root, timeout=900)
    result["profile"] = {**profile, **profileResult(profile["returncode"] or 0,
                                                 profile["output"])}
    result["outcome"] = result["profile"].get("kind", "profile_unknown")
    replay_ids = re.findall(r"Application replay pass (\d+)", profile["output"])
    dp_paths = re.findall(r"^PROFILE_DP_FILE=(.+)$", profile["output"], re.MULTILINE)
    finished = re.findall(r"^\s*finished:.*$", profile["output"], re.MULTILINE)
    result["replay_integrity"] = {
        "pass_ids": replay_ids, "dp_paths": dp_paths,
        "finished_count": len(finished),
        "all_one_dp_zero_drop": all("1 distinguished points" in line and
                                    "0 dropped" in line for line in finished),
        "unique_dp_paths": len(set(dp_paths)) == len(dp_paths),
    }
    if result["outcome"] == "profiled" and (
        not replay_ids or replay_ids != [str(i) for i in range(1, len(replay_ids) + 1)]
        or len(dp_paths) != len(replay_ids) or len(finished) != len(replay_ids)
        or not result["replay_integrity"]["all_one_dp_zero_drop"]
        or not result["replay_integrity"]["unique_dp_paths"]
    ):
        result["outcome"] = "replay_integrity_failed"
    report_file = report_base.with_suffix(".ncu-rep")
    if report_file.exists():
        result["profile_raw"] = command_record(
            [NCU_BINARY, "--import", str(report_file), "--page", "raw", "--csv"],
            timeout=180)
        result["profile_details"] = command_record(
            [NCU_BINARY, "--import", str(report_file), "--page", "details"],
            timeout=180)
        result["source_sass"] = command_record(
            [NCU_BINARY, "--import", str(report_file), "--page", "source",
             "--print-source", "sass", "--csv"], timeout=180)
        result["source_cuda_sass"] = command_record(
            [NCU_BINARY, "--import", str(report_file), "--page", "source",
             "--print-source", "cuda,sass", "--csv"], timeout=180)
        result["ncu_report_sha256"] = hashlib.sha256(report_file.read_bytes()).hexdigest()
        result["ncu_report_size_bytes"] = report_file.stat().st_size
        compressed = zlib.compress(report_file.read_bytes(), level=6)
        result["ncu_report_compressed_size_bytes"] = len(compressed)
        if len(compressed) <= 32 * 1024 * 1024:
            result["_ncu_report_zlib_b64"] = base64.b64encode(compressed).decode("ascii")
        elif result["outcome"] == "profiled":
            result["outcome"] = "report_transfer_too_large"
        if any(result[key]["returncode"] for key in
               ("profile_raw", "profile_details", "source_sass", "source_cuda_sass")) \
                and result["outcome"] == "profiled":
            result["outcome"] = "report_import_failed"
    elif result["outcome"] == "profiled":
        result["outcome"] = "report_missing"
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
    # The working tree now includes later default-off tuning switches.  The
    # remote build still receives *only* the files read from this exact commit.
    settings = {**BASE, "PACKED_INLINE_SIGMA": 1, "PACKED_TOP_CLMAD": 0}
    result = profile_exact.remote(sources, settings, baseline_commit)
    result["driver_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    packed_report = result.pop("_ncu_report_zlib_b64", None)
    if packed_report is not None:
        report_path = output_path.with_suffix(".ncu-rep")
        if report_path.exists():
            raise FileExistsError(report_path)
        report_bytes = zlib.decompress(base64.b64decode(packed_report))
        if hashlib.sha256(report_bytes).hexdigest() != result["ncu_report_sha256"]:
            raise ValueError("transferred Nsight report hash differs from remote receipt")
        report_path.write_bytes(report_bytes)
        result["ncu_report_path"] = str(report_path)
    output_path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"receipt": str(output_path), "outcome": result.get("outcome"),
                      "binary_sha256": result.get("binary_sha256")}))
    if result.get("outcome") != "profiled":
        raise SystemExit(1)
