"""Validate the compatible Frobenius production profile against a pinned control.

The frozen benchmark image contains CUDA 13.3 and 13.4. Controls use CUDA 13.3
and pinned v3, v5 or v6 sources; the current candidate uses CUDA 13.4.
Experiments use temporary files and require no secrets.
"""
import hashlib
import json
import os
import subprocess
from pathlib import Path

import modal

LOCAL = Path(__file__).resolve().parent
BASELINE_COMMIT = "fabf83100654f531e6501ad703dbd103549d9c34"
CONTROLS = {
    "v3": {"commit": BASELINE_COMMIT, "settings": {}},
    "v5": {"commit": "afd9ba7fbd529b55a5372b30209f5961bbf49c9b",
           "settings": {"PACKED_ONB_INV": 1, "PACKED_TOP_HOIST": 1}},
    "v6": {"commit": "69f5e687e937d04902f195eca5228d029c4d29cd",
           "settings": {"PACKED_ONB_INV": 1, "PACKED_TOP_HOIST": 1}},
}
BENCH_IMAGE_ID = os.environ.get("ECC_BENCH_IMAGE", "im-vZ6bOy9hMYSLXvtmTF7CiD")
if modal.is_local():
    bench_image = modal.Image.from_id(BENCH_IMAGE_ID)
else:
    bench_image = None

app = modal.App("ecc2k130-frobenius-20b-validation")

BASE = dict(BATCH=16, THREADS=640, MINBLOCKS=1, PACKED_SINGLE_PRODUCT=1,
    PACKED_CACHE_DENOM=1, PACKED_BY_VALUE=1, PACKED_PERM_SIGMA=3,
    PACKED_POLY_CHAIN=1, PACKED_UNROLL_INV=1, PACKED_PAIR_PRODUCTS=1,
    PACKED_POLY_STATE=1, PACKED_DIRECT_REDUCE=1, PACKED_GENERATED_PRODUCT=1,
    PACKED_CLMAD=1, PACKED_STATE_TILE=256, PACKED_WEIGHTED_PREFIX=2,
    PACKED_COMPACT_STATE=1, PACKED_SHARED_SIGMA=1, WALK_TABLE=0,
    COLLECTIVE_WARPS=4, PACKED_FROM_REDUCED=1, PACKED_INLINE_POLY=3,
    PACKED_L2_PERSIST=1, PACKED_ALU_SQUARE=1,
    FROBENIUS_FUSED=1, PACKED_CHAIN_FIRST=1, PACKED_INLINE_SIGMA=1)

CASES = {
    "production_onb": ({"PACKED_ONB_INV": 1, "PACKED_TOP_HOIST": 1,
                        "NVCC": "/usr/local/cuda-13.4/bin/nvcc"}, ""),
    "production_cuda133": ({"PACKED_ONB_INV": 1, "PACKED_TOP_HOIST": 1}, ""),
}


@app.function(image=bench_image, gpu="RTX-PRO-6000", cpu=4, memory=8192,
              timeout=2700, max_containers=1)
def experiment(mode: str, selected: str, candidate_sources: dict, baseline_sources: dict,
               control: dict):
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
              "benchmark_image_id": control["benchmark_image_id"],
              "mode": mode, "population": 120320, "base_settings": BASE,
              "baseline_commit": control["commit"], "control_name": control["name"],
              "variants": []}

    def run(command, timeout=600):
        process = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=timeout)
        output = process.stdout + process.stderr
        if process.returncode or "MISMATCH" in output or "stopping:" in output:
            raise RuntimeError(json.dumps({"command": command, "returncode": process.returncode,
                                           "output": output[-8000:]}))
        return output

    def build(name, destination):
        print(json.dumps({"building": name}), flush=True)
        overrides, policy = (control["settings"], "") if name == "baseline" else CASES[name]
        # The control is pinned independently; production measures the current
        # working tree without rewriting its candidate arithmetic.
        sources = candidate_sources if name.startswith("production") else baseline_sources
        for relative, content in sources.items():
            (root / relative).write_text(content)
        source = header.read_text()
        kernel_source = kernels.read_text()
        def replace(relative, before, after):
            path = root / relative
            text = path.read_text()
            if text.count(before) != 1:
                raise ValueError(f"unexpected source for {policy}: {relative}")
            path.write_text(text.replace(before, after))

        diagnostic = '''        int activeBlocks = 0;
        CUDA_CHECK(cudaOccupancyMaxActiveBlocksPerMultiprocessor(&activeBlocks, eccPacked131::walk, ECC_THREADS, 0));
        printf("packed diagnostic active blocks/SM: %d\\n", activeBlocks);
'''
        source = source.replace("        CUDA_CHECK(cudaFuncGetAttributes(&attrs, eccPacked131::walk));",
            "        CUDA_CHECK(cudaFuncGetAttributes(&attrs, eccPacked131::walk));\n" + diagnostic)
        header.write_text(source)
        kernels.write_text(kernel_source)
        settings = {**BASE, "NVCC": "/usr/local/cuda-13.3/bin/nvcc", **overrides}
        command = ["make", "-B", "ecc2k130", "ARCH=-gencode arch=compute_120,code=sm_120",
                   *[f"{key}={value}" for key, value in settings.items()]]
        started = time.monotonic()
        output = run(command)
        shutil.copy2(root / "ecc2k130", destination)
        return {"compiler_version": run([settings["NVCC"], "--version"]),
                "settings": settings,
                "cache_policy": policy if policy in ("normal", "streaming") else "prefix",
                "source_variant": policy or name,
                "build_seconds": time.monotonic() - started, "build_command": command,
                "build_output_tail": output[-6000:],
                "binary_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
                "engine_header_sha256": hashlib.sha256(source.encode()).hexdigest(),
                "kernel_header_sha256": hashlib.sha256(kernel_source.encode()).hexdigest(),
                "candidate_source_sha256": {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                                             for name in sources}}

    counter = 0
    def measure(binary, temporary, launches, workers=120320):
        nonlocal counter
        counter += 1
        path = temporary / f"reports-{counter}.bin"
        command = [str(binary), "--packed", "--curve", "131", "--threads", str(workers),
                   "--steps", "1024", "--launches", str(launches), "--run-id", "11000",
                   "--dp-weight", "32", "--verify", "0", "--dp-file", str(path)]
        telemetry_path = temporary / f"telemetry-{counter}.csv"
        with telemetry_path.open("w") as telemetry_file:
            sampler = subprocess.Popen([
                "nvidia-smi", "--query-gpu=clocks.sm,power.draw,temperature.gpu",
                "--format=csv,noheader,nounits", "-lms", "500"],
                stdout=telemetry_file, stderr=subprocess.STDOUT, text=True)
            try:
                output = run(command, timeout=180)
            finally:
                sampler.terminate()
                try:
                    sampler.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    sampler.kill()
                    sampler.wait(timeout=5)
        telemetry_rows = []
        for line in telemetry_path.read_text().splitlines():
            try:
                row = [float(value.strip()) for value in line.split(",")]
            except ValueError:
                continue
            if len(row) == 3:
                telemetry_rows.append(row)
        active = [row for row in telemetry_rows if row[0] >= 2000]
        telemetry = {"columns": ["sm_clock_MHz", "power_W", "temperature_C"],
                     "samples": telemetry_rows, "active_samples": len(active)}
        if active:
            telemetry["active_medians"] = [statistics.median(row[i] for row in active)
                                           for i in range(3)]
        if "0 dropped)" not in output:
            raise AssertionError(output)
        blob = path.read_bytes()
        if not blob or len(blob) % 32:
            raise AssertionError("empty or partial DP corpus")
        records = sorted(blob[n:n+32] for n in range(0, len(blob), 32))
        if any(int.from_bytes(record[8:], "little").bit_count() > 32 for record in records):
            raise AssertionError("record does not satisfy DP32")
        digest = hashlib.sha256(b"".join(records)).hexdigest()
        # Larger-population screens must reproduce every original seed stream.
        # Seed bits 16..47 encode the point index; low bits count its reseeds.
        original_records = [record for record in records
                            if ((int.from_bytes(record[:8], "little") >> 16) & 0xffffffff) < 120320*16]
        original_digest = hashlib.sha256(b"".join(original_records)).hexdigest()
        if launches == 64 and (len(original_records) != 355 or original_digest != "c80bb8db34e419d53bc946a5fef01c99fd60214a16f9b42ff87b5d52f3668a90"):
            raise AssertionError("candidate changed the frozen legacy DP32 corpus")
        if launches == 128 and (len(original_records) != 705 or original_digest != "530de6e2e95f910cb8ce89e9db3ad681917296817650c4a5a5492d75e6d18e4e"):
            raise AssertionError("candidate changed the confirmed v3 DP32 corpus")
        return {"command": command, "output": output, "records": len(records),
                "gpu_telemetry": telemetry,
                "sorted_sha256": digest, "original_corpus_sha256": original_digest,
                "billions_per_second": float(re.search(r"finished: ([0-9.]+) M it/s", output)[1]) / 1000}

    try:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            baseline = temporary / "baseline"
            result["image_binary_sha256"] = hashlib.sha256((root / "ecc2k130").read_bytes()).hexdigest()
            result["baseline_build"] = build("baseline", baseline)
            result["baseline_binary_sha256"] = hashlib.sha256(baseline.read_bytes()).hexdigest()
            result["gpu"] = run(["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"]).strip()
            result["gpu_uuid"] = run(["nvidia-smi", "--query-gpu=uuid", "--format=csv,noheader"]).strip()
            result["cpu_models"] = sorted({line.split(":", 1)[1].strip()
                for line in Path("/proc/cpuinfo").read_text().splitlines()
                if line.startswith("model name")})
            result["compiler"] = result["baseline_build"]["compiler_version"]
            result["source_sha256"] = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
                for folder in ("include", "src", "generated", "codegen")
                for path in sorted((root / folder).rglob("*"))
                if path.is_file() and "__pycache__" not in path.parts}
            # Warm the baseline before any paired measurements.
            result["warmup"] = measure(baseline, temporary, 64)
            for name in names:
                candidate = temporary / name
                row = {"name": name, **build(name, candidate), "pairs": []}
                if 120320 * 16 % row["settings"]["BATCH"]:
                    raise ValueError("candidate must preserve the exact number of walk points")
                row["runtime_workers"] = 120320 * 16 // row["settings"]["BATCH"]
                if mode == "confirm" and row["settings"]["BATCH"] != 16:
                    raise ValueError("alternate batch geometry requires separate checkpoint validation")
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
                        samples[label] = measure(binary, temporary, 64 if mode == "screen" else 128,
                                                 row["runtime_workers"] if label == "candidate" else 120320)
                    assert samples["baseline"]["original_corpus_sha256"] == samples["candidate"]["original_corpus_sha256"]
                    assert samples["baseline"]["sorted_sha256"] == samples["candidate"]["sorted_sha256"]
                    samples["ratio"] = samples["candidate"]["billions_per_second"] / samples["baseline"]["billions_per_second"]
                    row["pairs"].append(samples)
                    print(json.dumps({"pair": repetition + 1, "name": name,
                        "baseline_Bps": samples["baseline"]["billions_per_second"],
                        "candidate_Bps": samples["candidate"]["billions_per_second"],
                        "ratio": samples["ratio"]}), flush=True)
                row["median_ratio"] = statistics.median(pair["ratio"] for pair in row["pairs"])
                row["baseline_median_Bps"] = statistics.median(pair["baseline"]["billions_per_second"] for pair in row["pairs"])
                row["candidate_median_Bps"] = statistics.median(pair["candidate"]["billions_per_second"] for pair in row["pairs"])
                result["variants"].append(row)
                print(json.dumps({key: row[key] for key in
                    ("name", "median_ratio", "baseline_median_Bps", "candidate_median_Bps")}), flush=True)
                print("VARIANT_RECEIPT " + json.dumps(row), flush=True)
                if mode == "confirm":
                    probe = ["make", "test-packed-cuda", "test-packed-storage-cuda", "test-shared-sigma-cuda",
                             "ARCH=-gencode arch=compute_120,code=sm_120",
                             *[f"{key}={value}" for key, value in row["settings"].items()]]
                    result["shared_sigma_probe"] = {"command": probe, "output": run(probe)}
                    print(json.dumps({"shared_sigma_probe": "passed"}), flush=True)
                    import sys
                    sys.path.insert(0, str(root / "codegen"))
                    from testwalkcompat import compare
                    result["compatibility"] = compare(baseline, candidate, workers=(640, 641, 256))
                    print(json.dumps({"standard_compatibility": "passed"}), flush=True)
                    if BASE["FROBENIUS_FUSED"]:
                        result["odd_launch_compatibility"] = [
                            compare(baseline, candidate, workers=(640, 641, 256),
                                    steps=steps, weights=(0,)) for steps in (1, 3, 17)]
                        # Cross the 4096-step guard with sparse reports so that
                        # reseeding and resume are checked without long CPU trails.
                        result["guard_compatibility"] = compare(baseline, candidate,
                            workers=(640, 641), steps=4097, weights=(0,), max_iters=1)
                    print(json.dumps({"compatibility": "passed"}), flush=True)
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
def main(mode: str = "confirm", selected: str = "production_onb", output: str = "",
         control: str = "v3"):
    if control not in CONTROLS:
        raise ValueError("control must be v3, v5 or v6")
    reference = {"name": control, "benchmark_image_id": BENCH_IMAGE_ID, **CONTROLS[control]}
    path = LOCAL / (output or f"research/production/2026-09-22-frobenius-20b-{mode}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    tree = f"{reference['commit']}:ecc2k130/runner"
    names = subprocess.check_output(
        ["git", "ls-tree", "-r", "--full-tree", "--name-only", tree, "--",
         "Makefile", "include", "src", "generated", "codegen"], cwd=LOCAL, text=True).splitlines()
    if "Makefile" not in names or "include/packedfrobeniusfused.cuh" not in names:
        raise ValueError("pinned control sources are missing; fetch the baseline commit")
    baseline_sources = {name: subprocess.check_output(
        ["git", "show", f"{tree}/{name}"], cwd=LOCAL, text=True) for name in names}
    sources = {name: (LOCAL / name).read_text() for name in names}
    for name in ("codegen/inverse_sigma_routes.json", "codegen/genshiftedsigma.py", "codegen/shifted_sigma_routes.json", "include/packedshiftedsigma131.h",
                 "codegen/gensquareraw.py", "include/packedsquareraw131.h",
                 "include/canonical131.h", "src/testcanonical131.cpp"):
        sources[name] = (LOCAL / name).read_text()
    driver_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result = experiment.remote(mode, selected, sources, baseline_sources, reference)
    result["driver_sha256"] = driver_sha256
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"receipt": str(path), "winner": result["winner"], "ok": result["ok"]}))
