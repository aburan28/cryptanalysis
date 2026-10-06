"""Measure further optimizations against the merged fused v2 profile.

The frozen v1 image supplies the compiler; v2 is rebuilt as the control.
The control sources are pinned to the merged v2 commit, independently of local
candidate edits. Experiments use temporary files and require no secrets.
"""
import hashlib
import json
import os
import subprocess
from pathlib import Path

import modal

LOCAL = Path(__file__).resolve().parent
BASELINE_COMMIT = "7431819dd836d81707c0cd510a322ec9fdb14282"
if modal.is_local():
    bench_image = modal.Image.from_id(os.environ.get(
        "ECC_BENCH_IMAGE", "im-LEaik53IOCmWvHm1O2UUPQ"))
else:
    bench_image = None

app = modal.App("ecc2k130-frobenius-v3-tuning")

BASE = dict(BATCH=16, THREADS=640, MINBLOCKS=1, PACKED_SINGLE_PRODUCT=1,
    PACKED_CACHE_DENOM=1, PACKED_BY_VALUE=1, PACKED_PERM_SIGMA=3,
    PACKED_POLY_CHAIN=1, PACKED_UNROLL_INV=1, PACKED_PAIR_PRODUCTS=1,
    PACKED_POLY_STATE=1, PACKED_DIRECT_REDUCE=1, PACKED_GENERATED_PRODUCT=1,
    PACKED_CLMAD=1, PACKED_STATE_TILE=256, PACKED_WEIGHTED_PREFIX=2,
    PACKED_COMPACT_STATE=1, PACKED_SHARED_SIGMA=1, WALK_TABLE=0,
    COLLECTIVE_WARPS=4, PACKED_FROM_REDUCED=1, PACKED_INLINE_POLY=3,
    PACKED_L2_PERSIST=1, PACKED_ALU_SQUARE=1,
    FROBENIUS_FUSED=1, PACKED_CHAIN_FIRST=1)

CASES = {
    "inline_sigma_untagged": ({}, "inline_sigma_untagged"),
    "production": ({"PACKED_INLINE_SIGMA": 1}, ""),
    "inline_sigma": ({}, "inline_sigma"),
    "forward_chain_first": ({}, "forward_chain_first"),
    "pair_ilp": ({"PACKED_PAIR_ILP": 1}, ""),
    "fused_unroll2": ({}, "unroll2"),
    "fused_prefetch": ({}, "prefetch"),
    "fused_pipeline": ({}, "pipeline"),
    "inline_inverse": ({}, "inline_inverse"),
    "balanced_l2_normal": ({}, "normal"),
    # Historical screen label: this flag does not change the current polynomial
    # squaring implementation, so the case is a negative control.
    "clmad_square": ({"PACKED_ALU_SQUARE": 0}, ""),
    "flat_clmul": ({"PACKED_CLMUL_FLAT": 1}, ""),
    "dead_mask": ({}, "dead_mask"),
    "dead_mask_inline_sigma": ({}, "dead_mask_inline_sigma"),
    "pair_clmul": ({"PACKED_PAIR_CLMUL": 1}, ""),
    "fixed_directions": ({}, "fixed_directions"),
    "untagged_denominator": ({}, "untagged_denominator"),
    "blocks320": ({"THREADS": 320, "MINBLOCKS": 2, "COLLECTIVE_WARPS": 2}, ""),
}


@app.function(image=bench_image, gpu="RTX-PRO-6000", cpu=4, memory=8192,
              timeout=2700, max_containers=1)
def experiment(mode: str, selected: str, candidate_sources: dict, baseline_sources: dict):
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
              "mode": mode, "population": 120320, "base_settings": BASE,
              "baseline_commit": BASELINE_COMMIT, "variants": []}

    def run(command, timeout=600):
        process = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=timeout)
        output = process.stdout + process.stderr
        if process.returncode or "MISMATCH" in output or "stopping:" in output:
            raise RuntimeError(json.dumps({"command": command, "returncode": process.returncode,
                                           "output": output[-8000:]}))
        return output

    def build(name, destination):
        print(json.dumps({"building": name}), flush=True)
        overrides, policy = ({}, "") if name == "baseline" else CASES[name]
        # Prototype screens always start from v2. Only production measures
        # the current working tree, without rewriting its candidate sources.
        sources = candidate_sources if name == "production" else baseline_sources
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

        fused = "include/packedfrobeniusfused.cuh"
        if policy == "inline_sigma":
            replace("include/packedsigma131.h",
                "static ECC_BIG SigmaWalkPair131 sigmaWalkNetworkPairShared131(",
                "static ECC_HD SigmaWalkPair131 sigmaWalkNetworkPairShared131(")
        elif policy == "forward_chain_first":
            replace(fused, """const PolynomialPair pair = mulPolynomialPair131(*prod, ep, dp);
        store(statePrefix, slot, tid, p.threads, pair.first);
        *prod = pair.second;""", """const PolynomialPair pair = mulPolynomialPair131(*prod, dp, ep);
        store(statePrefix, slot, tid, p.threads, pair.second);
        *prod = pair.first;""")
        elif policy == "unroll2":
            replace(fused, "#pragma unroll 1\n        for (int i = 0; i < ECC_BATCH; ++i)",
                           "#pragma unroll 2\n        for (int i = 0; i < ECC_BATCH; ++i)")
        elif policy == "prefetch":
            replace(fused, "const int slot = forward ? i : ECC_BATCH - 1 - i;",
                """const int slot = forward ? i : ECC_BATCH - 1 - i;
            if (i + 1 < ECC_BATCH) {
                const int following = forward ? slot + 1 : slot - 1;
                compactPrefetch131(stateX, following, tid);
                compactPrefetch131(stateY, following, tid);
                compactPrefetch131(statePrefix, following, tid);
                compactPrefetch131(denominators, following, tid);
            }""")
        elif policy == "pipeline":
            replace(fused, "P131 next = {};", """P131 next = {};
        const int firstSlot = forward ? 0 : ECC_BATCH - 1;
        P131 pipeX = load(stateX, firstSlot, tid, p.threads);
        P131 pipeY = load(stateY, firstSlot, tid, p.threads);
        P131 pipeW = load(statePrefix, firstSlot, tid, p.threads);
        P131 pipeD = load(denominators, firstSlot, tid, p.threads);""")
            replace(fused, """const P131 x = load(stateX, slot, tid, p.threads);
            const P131 y = load(stateY, slot, tid, p.threads);
            const P131 w = load(statePrefix, slot, tid, p.threads);
            P131 dp = load(denominators, slot, tid, p.threads);""", """const P131 x = pipeX, y = pipeY, w = pipeW;
            P131 dp = pipeD;
            if (i + 1 < ECC_BATCH) {
                const int following = forward ? slot + 1 : slot - 1;
                pipeX = load(stateX, following, tid, p.threads);
                pipeY = load(stateY, following, tid, p.threads);
                pipeW = load(statePrefix, following, tid, p.threads);
                pipeD = load(denominators, following, tid, p.threads);
            }""")
        elif policy == "inline_inverse":
            replace("include/collective_inverse.cuh",
                "__device__ __noinline__ P131 goal22CollectiveInverse",
                "__device__ __forceinline__ P131 goal22CollectiveInverse")
        elif policy == "fixed_directions":
            path = root / fused
            text = path.read_text()
            begin = text.index("#pragma unroll 1\n        for (int i = 0; i < ECC_BATCH; ++i)")
            end = text.index("        prod = next;", begin)
            body = text[begin:end]
            forward = body.replace("const int slot = forward ? i : ECC_BATCH - 1 - i;", "const int slot = i;")
            reverse = body.replace("const int slot = forward ? i : ECC_BATCH - 1 - i;", "const int slot = ECC_BATCH - 1 - i;")
            text = text[:begin] + "        if (forward) {\n" + forward + "        } else {\n" + reverse + "        }\n" + text[end:]
            path.write_text(text)
        elif policy in ("untagged_denominator", "inline_sigma_untagged"):
            replace(fused, "    dp.v[4] |= unsigned(jump) << 3;\n", "")
            replace(fused, "            dp.v[4] &= 7;\n", "")
            if policy == "inline_sigma_untagged":
                replace("include/packedsigma131.h",
                    "static ECC_BIG SigmaWalkPair131 sigmaWalkNetworkPairShared131(",
                    "static ECC_HD SigmaWalkPair131 sigmaWalkNetworkPairShared131(")
        elif policy in ("dead_mask", "dead_mask_inline_sigma"):
            replace(fused, "bool guard, bool first, P131 *prod)",
                "bool guard, bool first, P131 *prod, unsigned *deadMask)")
            replace(fused, "if (!goal22ReadDead(stateDead, id))",
                "if (!(*deadMask & (1u << slot)))")
            path = root / fused
            text = path.read_text()
            before = "goal22WriteDead(stateDead, id, 1);"
            if text.count(before) != 2:
                raise ValueError("unexpected dead-flag write count")
            path.write_text(text.replace(before,
                "*deadMask |= 1u << slot;\n            " + before))
            replace(fused, "P131 prod;", """P131 prod;
    static_assert(ECC_BATCH <= 32, "dead mask covers at most 32 slots");
    unsigned deadMask = 0;
#pragma unroll
    for (int slot = 0; slot < ECC_BATCH; ++slot)
        deadMask |= unsigned(goal22ReadDead(stateDead, size_t(slot) * p.threads + tid) != 0) << slot;""")
            replace(fused, "initialGuard, slot == 0, &prod);",
                "initialGuard, slot == 0, &prod, &deadMask);")
            replace(fused, "now, guard, i == 0, &next);",
                "now, guard, i == 0, &next, &deadMask);")
            if policy == "dead_mask_inline_sigma":
                replace("include/packedsigma131.h",
                    "static ECC_BIG SigmaWalkPair131 sigmaWalkNetworkPairShared131(",
                    "static ECC_HD SigmaWalkPair131 sigmaWalkNetworkPairShared131(")
        elif policy == "normal":
            before = "window.num_bytes = bytes < size_t(maxPersist) ? bytes : size_t(maxPersist);\n        window.hitRatio = 1.0f;"
            after = """int maxWindow = 0;
        CUDA_CHECK(cudaDeviceGetAttribute(&maxWindow,
            cudaDevAttrMaxAccessPolicyWindowSize, device));
        window.num_bytes = bytes < size_t(maxWindow) ? bytes : size_t(maxWindow);
        window.hitRatio = window.num_bytes > size_t(maxPersist)
            ? float(maxPersist) / float(window.num_bytes) : 1.0f;"""
            if source.count(before) != 1:
                raise ValueError("baseline cache implementation changed")
            source = source.replace(before, after).replace(
                "window.missProp = cudaAccessPropertyStreaming;",
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
                "source_variant": policy or name,
                "build_seconds": time.monotonic() - started, "build_command": command,
                "build_output_tail": output[-6000:],
                "binary_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
                "engine_header_sha256": hashlib.sha256(source.encode()).hexdigest(),
                "kernel_header_sha256": hashlib.sha256(kernel_source.encode()).hexdigest(),
                "candidate_source_sha256": {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                                             for name in sources}}

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
        if launches == 128 and (len(records) != 705 or digest != "530de6e2e95f910cb8ce89e9db3ad681917296817650c4a5a5492d75e6d18e4e"):
            raise AssertionError("candidate changed the confirmed v2 DP32 corpus")
        return {"command": command, "output": output, "records": len(records),
                "sorted_sha256": digest,
                "billions_per_second": float(re.search(r"finished: ([0-9.]+) M it/s", output)[1]) / 1000}

    try:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            baseline = temporary / "baseline"
            result["image_binary_sha256"] = hashlib.sha256((root / "ecc2k130").read_bytes()).hexdigest()
            result["baseline_build"] = build("baseline", baseline)
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
                    probe = ["make", "test-shared-sigma-cuda",
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
def main(mode: str = "screen", selected: str = "", output: str = ""):
    path = LOCAL / (output or f"research/production/2026-09-21-frobenius-v3-{mode}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    tree = f"{BASELINE_COMMIT}:ecc2k130/runner"
    names = subprocess.check_output(
        ["git", "ls-tree", "-r", "--full-tree", "--name-only", tree, "--",
         "Makefile", "include", "src", "generated", "codegen"], cwd=LOCAL, text=True).splitlines()
    if "Makefile" not in names or "include/packedfrobeniusfused.cuh" not in names:
        raise ValueError("pinned v2 sources are missing; fetch the baseline commit")
    baseline_sources = {name: subprocess.check_output(
        ["git", "show", f"{tree}/{name}"], cwd=LOCAL, text=True) for name in names}
    sources = {name: (LOCAL / name).read_text() for name in names}
    driver_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result = experiment.remote(mode, selected, sources, baseline_sources)
    result["driver_sha256"] = driver_sha256
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"receipt": str(path), "winner": result["winner"], "ok": result["ok"]}))
