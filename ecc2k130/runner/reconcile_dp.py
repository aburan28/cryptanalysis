"""Bounded comparison: preserve the legacy walk while retaining fast arithmetic."""
import json
import os
from pathlib import Path
import modal

LOCAL = Path(__file__).resolve().parent if modal.is_local() else Path("/opt/ecc2k130")
if modal.is_local():
    import modal_worker as production
    experiment_image = production.image
else:
    experiment_image = None
app = modal.App("ecc2k130-dp-reconciliation")


@app.function(image=experiment_image, gpu="RTX-PRO-6000", cpu=4, memory=8192,
              timeout=2700, secrets=[modal.Secret.from_name(os.environ.get("ECC_MODAL_SECRET", "ecc2k130-cloud"))])
def experiment(mode: str = "screen"):
    import hashlib
    import re
    import statistics
    import shutil
    import subprocess
    import tempfile
    import time
    import boto3
    root = Path("/opt/ecc2k130")
    if mode not in ("screen", "geometry", "cache"):
        raise ValueError("mode must be screen, geometry or cache")
    population = 120320 if mode == "screen" else 385024
    launches = 64 if mode == "screen" else 32
    result = {"started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "mode": mode, "screen_workers": population, "screen_launches": launches, "variants": []}
    base = dict(BATCH=16, THREADS=256, MINBLOCKS=2, PACKED_SINGLE_PRODUCT=1,
        PACKED_CACHE_DENOM=1, PACKED_BY_VALUE=1, PACKED_PERM_SIGMA=3,
        PACKED_POLY_CHAIN=1, PACKED_UNROLL_INV=1, PACKED_PAIR_PRODUCTS=1,
        PACKED_POLY_STATE=1, PACKED_DIRECT_REDUCE=1, PACKED_GENERATED_PRODUCT=1,
        PACKED_CLMAD=1, PACKED_STATE_TILE=256, PACKED_WEIGHTED_PREFIX=2,
        PACKED_COMPACT_STATE=1, PACKED_SHARED_SIGMA=1, WALK_TABLE=0,
        PACKED_FROM_REDUCED=1, PACKED_INLINE_POLY=3, PACKED_L2_PERSIST=1,
        PACKED_ALU_SQUARE=1, COLLECTIVE_WARPS=0)

    def run(command, timeout=600):
        p = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=timeout)
        row = {"command": command, "returncode": p.returncode, "output": p.stdout + p.stderr}
        if p.returncode or "MISMATCH" in row["output"] or "stopping:" in row["output"]:
            print(json.dumps(row), flush=True)
            raise RuntimeError("experiment command failed")
        return row

    def flags(config):
        return [f"{k}={v}" for k, v in config.items()]

    def records(path, cutoff):
        blob = path.read_bytes()
        assert blob and len(blob) % 32 == 0
        items = sorted(blob[n:n+32] for n in range(0, len(blob), 32))
        histogram = {}
        for rec in items:
            point = int.from_bytes(rec[8:], "little")
            assert point >> 131 == 0
            weight = point.bit_count()
            assert weight <= cutoff and weight % 2 == 0
            histogram[weight] = histogram.get(weight, 0) + 1
        return {"records": len(items), "sorted_sha256": hashlib.sha256(b"".join(items)).hexdigest(),
                "weight_histogram": histogram}

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        legacy = tmp / "legacy"
        s3 = boto3.client("s3")
        config = json.loads(s3.get_object(Bucket=os.environ["ECC_BUCKET"], Key="campaign.json")["Body"].read())
        assert config["dpWeight"] == 32
        assert config["binarySha256"] == "0c02a3cfec9553a5def6e9df530c027a246648f6a6b8b7fef39c67e582aae9f4"
        s3.download_file(os.environ["ECC_BUCKET"], config["binaryKey"], str(legacy))
        assert hashlib.sha256(legacy.read_bytes()).hexdigest() == config["binarySha256"]
        legacy.chmod(0o700)
        production_binary = tmp / "production"
        shutil.copyfile(root / "ecc2k130", production_binary)
        production_binary.chmod(0o700)
        variants = [("legacy_control", None), ("production256", "production"),
                    ("frobenius640_collective", {**base, "THREADS":640, "MINBLOCKS":1, "COLLECTIVE_WARPS":4}),
                    ("frobenius512_collective4", {**base, "THREADS":512, "MINBLOCKS":1, "COLLECTIVE_WARPS":4}),
                    ("frobenius512_collective8", {**base, "THREADS":512, "MINBLOCKS":1, "COLLECTIVE_WARPS":8}),
                    ("frobenius640_collective2", {**base, "THREADS":640, "MINBLOCKS":1, "COLLECTIVE_WARPS":2}),
                    ("table640", "table")]
        if mode == "geometry":
            variants = [("legacy_control", None), ("production256", "production"),
                        ("frobenius256_collective4", {**base, "COLLECTIVE_WARPS": 4}),
                        ("frobenius256_collective2", {**base, "COLLECTIVE_WARPS": 2}),
                        ("frobenius256_scalar", base)]
        elif mode == "cache":
            variants = [("legacy_control", None),
                        ("frobenius640_no_persist", {**base, "THREADS": 640, "MINBLOCKS": 1,
                            "COLLECTIVE_WARPS": 4, "PACKED_L2_PERSIST": 0}),
                        ("frobenius256_no_persist", {**base, "COLLECTIVE_WARPS": 4, "PACKED_L2_PERSIST": 0}),
                        ("frobenius256_scalar_no_persist", {**base, "PACKED_L2_PERSIST": 0})]
        result["gpu"] = run(["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"])["output"].strip()
        result["compiler"] = run(["nvcc", "--version"])["output"]
        # Identify the exact local sources, including headers behind the profile.
        result["source_sha256"] = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ("include", "src", "generated", "codegen")
            for p in sorted((root / folder).rglob("*")) if p.is_file() and "__pycache__" not in p.parts}
        result["source_sha256"]["Makefile"] = hashlib.sha256((root / "Makefile").read_bytes()).hexdigest()
        expected = None
        for name, settings in variants:
            row = {"name": name, "settings": settings, "samples": []}
            binary = legacy if settings is None else production_binary if settings == "production" else root / "ecc2k130"
            if settings is not None and settings != "production":
                command = ["make", "gpu-goal22"] if settings == "table" else ["make", "-B", "ecc2k130",
                    "ARCH=-gencode arch=compute_120,code=sm_120", *flags(settings)]
                built = run(command)
                row["build"] = {**built, "output": built["output"][-6000:]}
            row["binary_sha256"] = hashlib.sha256(binary.read_bytes()).hexdigest()
            if isinstance(settings, dict):
                shutil.copyfile(binary, tmp / name)
                (tmp / name).chmod(0o700)
            for n in range(3):
                corpus = tmp / f"{name}-{n}.bin"
                sample = run([str(binary), "--packed", "--curve", "131", "--threads", str(population),
                    "--steps", "1024", "--launches", str(launches), "--run-id", "11000", "--dp-weight", "32",
                    "--verify", "0", "--dp-file", str(corpus)])
                assert "0 dropped)" in sample["output"]
                sample.update(records(corpus, 32))
                sample["billions_per_second"] = float(re.search(r"finished: ([0-9.]+) M it/s", sample["output"])[1]) / 1000
                if expected is None:
                    expected = sample["sorted_sha256"]
                sample["legacy_corpus_identical"] = sample["sorted_sha256"] == expected
                assert settings == "table" or sample["legacy_corpus_identical"], name
                row["samples"].append(sample)
            row["median_billions_per_second"] = statistics.median(s["billions_per_second"] for s in row["samples"])
            if mode == "screen" and (settings is None or settings == "table"):
                corpus = tmp / f"{name}-dp34.bin"
                sample = run([str(binary), "--packed", "--curve", "131", "--threads", "120320",
                    "--steps", "1024", "--launches", "64", "--run-id", "11000", "--dp-weight", "34",
                    "--verify", "0", "--dp-file", str(corpus)])
                assert "0 dropped)" in sample["output"]
                sample.update(records(corpus, 34))
                row["dp34"] = sample
                row["dp34_already_meeting_dp32"] = sum(v for k,v in sample["weight_histogram"].items() if k <= 32)
            result["variants"].append(row)
            print(json.dumps({"completed": name, "median_Bps": row["median_billions_per_second"],
                              "legacy_corpus_identical": row["samples"][0]["legacy_corpus_identical"],
                              "records": row["samples"][0]["records"]}), flush=True)
            # Keep each complete result recoverable even if the local launcher
            # loses its working directory or disconnects after the GPU finishes.
            print("VARIANT_RECEIPT " + json.dumps(row), flush=True)
        result["winner"] = max((r for r in result["variants"] if r["name"] != "table640"),
                               key=lambda r:r["median_billions_per_second"])["name"]
        winner = next(r for r in result["variants"] if r["name"] == result["winner"])
        candidate = (legacy if winner["settings"] is None else production_binary
                     if winner["settings"] == "production" else tmp / result["winner"])
        if mode != "screen":
            block_threads = winner["settings"]["THREADS"] if isinstance(winner["settings"], dict) else 256
            run(["python3", "-c", "import json,sys; from pathlib import Path; "
                 "from codegen.testwalkcompat import compare; "
                 "n=int(sys.argv[4]); "
                 "Path(sys.argv[3]).write_text(json.dumps(compare(Path(sys.argv[1]), Path(sys.argv[2]), (n,n+1))))",
                 str(legacy), str(candidate), str(tmp / "compatibility.json"), str(block_threads)], timeout=900)
        else:
            run(["python3", "codegen/testwalkcompat.py", str(legacy), str(candidate),
                 "--output", str(tmp / "compatibility.json")], timeout=1200)
        result["compatibility"] = json.loads((tmp / "compatibility.json").read_text())
        # Five fresh paired timing samples at the existing campaign population.
        # Identical records are required in every repetition, including the
        # final partial block when the winning block size is 640.
        result["confirmation"] = []
        expected_full = None
        for repetition in range(5):
            for name, binary in (("legacy_control", legacy), ("candidate", candidate)):
                corpus = tmp / f"confirm-{name}-{repetition}.bin"
                sample = run([str(binary), "--packed", "--curve", "131", "--threads", "385024",
                    "--steps", "1024", "--launches", str(launches), "--run-id", "11000", "--dp-weight", "32",
                    "--verify", "0", "--dp-file", str(corpus)])
                assert "0 dropped)" in sample["output"]
                sample.update(records(corpus, 32))
                if expected_full is None:
                    expected_full = sample["sorted_sha256"]
                assert sample["sorted_sha256"] == expected_full, "confirmation corpus differs"
                sample.update(name=name, repetition=repetition, legacy_corpus_identical=True,
                    billions_per_second=float(re.search(r"finished: ([0-9.]+) M it/s", sample["output"])[1]) / 1000)
                result["confirmation"].append(sample)
                print(json.dumps({"confirmation": name, "repetition": repetition,
                    "Bps": sample["billions_per_second"], "records": sample["records"]}), flush=True)
        result["confirmed_medians"] = {name: statistics.median(s["billions_per_second"]
            for s in result["confirmation"] if s["name"] == name)
            for name in ("legacy_control", "candidate")}
        result["confirmed_speedup"] = result["confirmed_medians"]["candidate"] / result["confirmed_medians"]["legacy_control"]
        result["faster_at_existing_population"] = (result["winner"] != "legacy_control"
                                                   and result["confirmed_speedup"] > 1)
        result["ok"] = True
    result["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    print("FINAL_RECEIPT " + json.dumps(result), flush=True)
    return result


@app.local_entrypoint()
def main(mode: str = "screen"):
    # Resolve and create the destination before the long remote call. Resolving
    # relative __file__ afterwards previously lost a complete run to getcwd().
    if mode not in ("screen", "geometry", "cache"):
        raise ValueError("mode must be screen, geometry or cache")
    name = {"screen": "dp-reconciliation-v2", "geometry": "dp-geometry-reconciliation",
            "cache": "dp-cache-reconciliation"}[mode]
    path = LOCAL / f"research/production/2026-09-21-{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    result = experiment.remote(mode)
    staging = path.with_suffix(".tmp")
    staging.write_text(json.dumps(result, indent=2) + "\n")
    staging.replace(path)
    print(json.dumps({"screen_winner": result["winner"],
                      "confirmed_medians": result["confirmed_medians"],
                      "faster_at_existing_population": result["faster_at_existing_population"],
                      "receipt": str(path)}))
