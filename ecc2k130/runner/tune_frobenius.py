"""Measure Frobenius-only optimizations at the deployed population on one GPU.

ECC_BENCH_IMAGE can override the frozen v1 Modal image used as the control.
Experiments write only container-local temporary files and require no secrets.
"""
import json
import os
from pathlib import Path

import modal

LOCAL = Path(__file__).resolve().parent
if modal.is_local():
    bench_image = modal.Image.from_id(os.environ.get(
        "ECC_BENCH_IMAGE", "im-LEaik53IOCmWvHm1O2UUPQ"))
else:
    bench_image = None

app = modal.App("ecc2k130-frobenius-tuning")

BASE = dict(BATCH=16, THREADS=640, MINBLOCKS=1, PACKED_SINGLE_PRODUCT=1,
    PACKED_CACHE_DENOM=1, PACKED_BY_VALUE=1, PACKED_PERM_SIGMA=3,
    PACKED_POLY_CHAIN=1, PACKED_UNROLL_INV=1, PACKED_PAIR_PRODUCTS=1,
    PACKED_POLY_STATE=1, PACKED_DIRECT_REDUCE=1, PACKED_GENERATED_PRODUCT=1,
    PACKED_CLMAD=1, PACKED_STATE_TILE=256, PACKED_WEIGHTED_PREFIX=2,
    PACKED_COMPACT_STATE=1, PACKED_SHARED_SIGMA=1, WALK_TABLE=0,
    COLLECTIVE_WARPS=4, PACKED_FROM_REDUCED=1, PACKED_INLINE_POLY=3,
    PACKED_L2_PERSIST=1, PACKED_ALU_SQUARE=1)

CASES = {
    "chain_first": ({"PACKED_CHAIN_FIRST": 1}, ""),
    "pair_ilp": ({"PACKED_PAIR_ILP": 1}, ""),
    "prefetch": ({"PACKED_SLOT_PREFETCH": 1}, ""),
    "unroll2": ({"UNROLL_SLOTS": 2}, ""),
    "no_persist": ({"PACKED_L2_PERSIST": 0}, ""),
    "balanced_l2_normal": ({}, "normal"),
    "balanced_l2_streaming": ({}, "streaming"),
    "balanced_l2_chain_first": ({"PACKED_CHAIN_FIRST": 1}, "normal"),
    "fused": ({"FROBENIUS_FUSED": 1}, "fused"),
    "fused_chain_first": ({"FROBENIUS_FUSED": 1, "PACKED_CHAIN_FIRST": 1}, "fused"),
}


@app.function(image=bench_image, gpu="RTX-PRO-6000", cpu=4, memory=8192,
              timeout=2700, max_containers=1)
def experiment(mode: str, selected: str, candidate_sources: dict):
    import datetime
    import hashlib
    import re
    import shutil
    import statistics
    import subprocess
    import tempfile
    import time

    names = selected.split(",") if selected else list(CASES)
    if mode not in ("screen", "confirm") or any(name not in CASES for name in names):
        raise ValueError("choose screen or confirm with known candidates")
    if mode == "confirm" and len(names) != 1:
        raise ValueError("confirm exactly one candidate")
    root = Path("/opt/ecc2k130")
    header = root / "include/packedengine.cuh"
    original = header.read_text()
    kernels = root / "include/packedkernels.cuh"
    original_kernels = kernels.read_text()
    saved_sources = {name: (root / name).read_text() if (root / name).exists() else None
                     for name in candidate_sources}
    result = {"started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "mode": mode, "population": 120320, "base_settings": BASE, "variants": []}

    def run(command, timeout=600):
        process = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=timeout)
        output = process.stdout + process.stderr
        if process.returncode or "MISMATCH" in output or "stopping:" in output:
            raise RuntimeError(json.dumps({"command": command, "returncode": process.returncode,
                                           "output": output[-8000:]}))
        return output

    def build(name, destination):
        print(json.dumps({"building": name}), flush=True)
        overrides, policy = CASES[name]
        for relative, content in candidate_sources.items():
            (root / relative).write_text(content)
        source = header.read_text()
        kernel_source = kernels.read_text()
        if policy in ("normal", "streaming"):
            before = "window.num_bytes = bytes < size_t(maxPersist) ? bytes : size_t(maxPersist);\n        window.hitRatio = 1.0f;"
            after = """int maxWindow = 0;
        CUDA_CHECK(cudaDeviceGetAttribute(&maxWindow,
            cudaDevAttrMaxAccessPolicyWindowSize, device));
        window.num_bytes = bytes < size_t(maxWindow) ? bytes : size_t(maxWindow);
        window.hitRatio = window.num_bytes > size_t(maxPersist)
            ? float(maxPersist) / float(window.num_bytes) : 1.0f;"""
            if source.count(before) != 1:
                raise ValueError("baseline cache implementation changed")
            source = source.replace(before, after)
            if policy == "normal":
                source = source.replace("window.missProp = cudaAccessPropertyStreaming;",
                                        "window.missProp = cudaAccessPropertyNormal;")
        header.write_text(source)
        kernels.write_text(kernel_source)
        settings = {**BASE, **overrides}
        command = ["make", "-B", "ecc2k130", "ARCH=-gencode arch=compute_120,code=sm_120",
                   *[f"{key}={value}" for key, value in settings.items()]]
        started = time.monotonic()
        output = run(command)
        shutil.copy2(root / "ecc2k130", destination)
        return {"settings": settings,
                "cache_policy": policy if policy in ("normal", "streaming") else "prefix",
                "kernel_variant": "fused" if policy == "fused" else "two-pass",
                "build_seconds": time.monotonic() - started, "build_command": command,
                "build_output_tail": output[-6000:],
                "binary_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
                "engine_header_sha256": hashlib.sha256(source.encode()).hexdigest(),
                "kernel_header_sha256": hashlib.sha256(kernel_source.encode()).hexdigest(),
                "candidate_source_sha256": {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                                             for name in candidate_sources}}

    counter = 0
    def measure(binary, temporary, launches):
        nonlocal counter
        counter += 1
        path = temporary / f"reports-{counter}.bin"
        command = [str(binary), "--packed", "--curve", "131", "--threads", "120320",
                   "--steps", "1024", "--launches", str(launches), "--run-id", "11000",
                   "--dp-weight", "32", "--verify", "0", "--dp-file", str(path)]
        output = run(command, timeout=180)
        if "0 dropped)" not in output:
            raise AssertionError(output)
        blob = path.read_bytes()
        if not blob or len(blob) % 32:
            raise AssertionError("empty or partial DP corpus")
        records = sorted(blob[n:n+32] for n in range(0, len(blob), 32))
        if any(int.from_bytes(record[8:], "little").bit_count() > 32 for record in records):
            raise AssertionError("record does not satisfy DP32")
        digest = hashlib.sha256(b"".join(records)).hexdigest()
        if launches == 64 and (len(records) != 355 or digest != "c80bb8db34e419d53bc946a5fef01c99fd60214a16f9b42ff87b5d52f3668a90"):
            raise AssertionError("candidate changed the frozen legacy DP32 corpus")
        return {"command": command, "output": output, "records": len(records),
                "sorted_sha256": digest,
                "billions_per_second": float(re.search(r"finished: ([0-9.]+) M it/s", output)[1]) / 1000}

    try:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            baseline = temporary / "baseline"
            shutil.copy2(root / "ecc2k130", baseline)
            result["baseline_binary_sha256"] = hashlib.sha256(baseline.read_bytes()).hexdigest()
            result["gpu"] = run(["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"]).strip()
            result["compiler"] = run(["nvcc", "--version"])
            result["source_sha256"] = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
                for folder in ("include", "src", "generated", "codegen")
                for path in sorted((root / folder).rglob("*"))
                if path.is_file() and "__pycache__" not in path.parts}
            # Warm the baseline before any paired measurements.
            result["warmup"] = measure(baseline, temporary, 64)
            for name in names:
                candidate = temporary / name
                row = {"name": name, **build(name, candidate), "pairs": []}
                if mode == "confirm":
                    # Compilation leaves the GPU idle. Warm it again before
                    # measuring a sub-percent gain, which thermal drift can mask.
                    row["post_build_warmup"] = measure(baseline, temporary, 512)
                for repetition in range(2 if mode == "screen" else 5):
                    samples = {}
                    order = [("baseline", baseline), ("candidate", candidate)]
                    if repetition % 2:
                        order.reverse()
                    for label, binary in order:
                        samples[label] = measure(binary, temporary, 64 if mode == "screen" else 128)
                    assert samples["baseline"]["sorted_sha256"] == samples["candidate"]["sorted_sha256"]
                    samples["ratio"] = samples["candidate"]["billions_per_second"] / samples["baseline"]["billions_per_second"]
                    row["pairs"].append(samples)
                row["median_ratio"] = statistics.median(pair["ratio"] for pair in row["pairs"])
                row["baseline_median_Bps"] = statistics.median(pair["baseline"]["billions_per_second"] for pair in row["pairs"])
                row["candidate_median_Bps"] = statistics.median(pair["candidate"]["billions_per_second"] for pair in row["pairs"])
                result["variants"].append(row)
                print(json.dumps({key: row[key] for key in
                    ("name", "median_ratio", "baseline_median_Bps", "candidate_median_Bps")}), flush=True)
                print("VARIANT_RECEIPT " + json.dumps(row), flush=True)
                if mode == "confirm":
                    import sys
                    sys.path.insert(0, str(root / "codegen"))
                    from testwalkcompat import compare
                    result["compatibility"] = compare(baseline, candidate, workers=(640, 641, 256))
                    if CASES[name][0].get("FROBENIUS_FUSED"):
                        result["odd_launch_compatibility"] = [
                            compare(baseline, candidate, workers=(640, 641, 256),
                                    steps=steps, weights=(0,)) for steps in (1, 3, 17)]
                        # Cross the 4096-step guard with sparse reports so that
                        # reseeding and resume are checked without long CPU trails.
                        result["guard_compatibility"] = compare(baseline, candidate,
                            workers=(640, 641), steps=4097, weights=(0,), max_iters=1)
            result["winner"] = max(result["variants"], key=lambda row: row["median_ratio"])["name"]
            result["ok"] = True
    finally:
        header.write_text(original)
        kernels.write_text(original_kernels)
        for name, content in saved_sources.items():
            path = root / name
            if content is None:
                path.unlink(missing_ok=True)
            else:
                path.write_text(content)
    result["completed_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return result


@app.local_entrypoint()
def main(mode: str = "screen", selected: str = "", output: str = ""):
    path = LOCAL / (output or f"research/production/2026-09-21-frobenius-tuning-{mode}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    sources = {name: (LOCAL / name).read_text() for name in (
        "Makefile", "include/packedkernels.cuh", "include/packedengine.cuh",
        "include/packedfrobeniusfused.cuh", "codegen/testwalkcompat.py")}
    result = experiment.remote(mode, selected, sources)
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"receipt": str(path), "winner": result["winner"], "ok": result["ok"]}))
