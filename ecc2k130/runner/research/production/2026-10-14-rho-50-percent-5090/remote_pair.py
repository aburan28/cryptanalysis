"""Bounded pinned-versus-four-warp comparison on one isolated RTX 5090 pod."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import statistics
import subprocess
import sys
import tempfile
import time

PINNED_SHA256 = "0c02a3cfec9553a5def6e9df530c027a246648f6a6b8b7fef39c67e582aae9f4"
POPULATIONS = (87040, 108800, 120320)
STEPS = 1024
LAUNCHES = 64
BATCH = 16
PAIRS = 5
RUN_ID = 11000


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def experiment(root: Path, pinned: Path, driver_sha256: str, source_commit: str,
               source_dirty: list[str], source_tar_sha256: str):
    sys.path.insert(0, str(root))
    from codegen.testwalkcompat import compare
    result = {
        "record_type": "ecc2k130_rho_pinned_four_warp_geometry_v1",
        "started_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "driver_sha256": driver_sha256,
        "source_commit": source_commit,
        "source_dirty": source_dirty,
        "source_tar_sha256": source_tar_sha256,
        "parameters": {
            "curve": 131, "walk": "signed_frobenius", "dp_weight": 32,
            "batch": BATCH, "run_id": RUN_ID, "steps": STEPS,
            "launches": LAUNCHES, "populations": POPULATIONS,
            "pairs": PAIRS, "gpu": "NVIDIA GeForce RTX 5090",
            "timeout_seconds": 2400, "retries": 0,
        },
        "checks": [], "samples": [], "valid": False,
    }

    def command(args, timeout=600):
        p = subprocess.run(args, cwd=root, capture_output=True, text=True, timeout=timeout)
        row = {"command": args, "returncode": p.returncode, "stdout": p.stdout, "stderr": p.stderr}
        result["checks"].append(row)
        if p.returncode or "MISMATCH" in p.stdout + p.stderr or "stopping:" in p.stdout + p.stderr:
            raise RuntimeError("command failed: " + json.dumps(row)[-6000:])
        return p.stdout + p.stderr

    def record_summary(path):
        blob = path.read_bytes()
        if not blob or len(blob) % 32:
            raise AssertionError("missing or partial DP32 records")
        items = sorted(blob[i:i + 32] for i in range(0, len(blob), 32))
        for item in items:
            x = int.from_bytes(item[8:], "little")
            if x >> 131 or x.bit_count() > 32 or x.bit_count() % 2:
                raise AssertionError("invalid DP32 endpoint")
        return len(items), hashlib.sha256(b"".join(items)).hexdigest()

    try:
        result["gpu"] = command(["nvidia-smi", "--query-gpu=name,uuid,driver_version,compute_cap",
                                 "--format=csv,noheader"]).strip()
        if "RTX 5090" not in result["gpu"]:
            raise RuntimeError("wrong GPU: " + result["gpu"])
        result["compiler"] = command(["nvcc", "--version"])
        result["makefile_sha256"] = sha(root / "Makefile")
        result["candidate_binary_sha256"] = sha(root / "ecc2k130")
        result["candidate_binary_config"] = command([
            str(root / "ecc2k130"), "--curve", "131", "--packed", "--bench",
            "--threads", "640", "--steps", "1", "--launches", "1", "--verify", "0"])
        if "packed collective inverse warps: 4" not in result["candidate_binary_config"]:
            raise AssertionError("candidate image does not contain four-warp inverse")
        if "packed table walk: 0" not in result["candidate_binary_config"]:
            raise AssertionError("candidate changed walk")
        if sha(pinned) != PINNED_SHA256:
            raise AssertionError("pinned binary SHA-256 mismatch")
        result["pinned_binary_sha256"] = sha(pinned)
        result["pinned_binary_s3_key"] = "bin/f3ab725a533b777e/ecc2k130"
        with tempfile.TemporaryDirectory(prefix="ecc-rho50-5090-") as tmpdir:
            tmp = Path(tmpdir)
            candidate = root / "ecc2k130"
            result["compatibility"] = compare(pinned, candidate, workers=(640, 641, 256))
            if not result["compatibility"].get("ok"):
                raise AssertionError("cross-binary compatibility failed")
            print("COMPATIBILITY_RECEIPT " + json.dumps({
                "ok": True, "checks": len(result["compatibility"]["checks"]),
                "verified": sum(run["verified"] for c in result["compatibility"]["checks"]
                                for run in c["runs"])}), flush=True)

            def measure(label, binary, population, repetition, phase):
                dpfile = tmp / f"dp-{population}-{repetition}-{phase}-{label}.bin"
                args = [
                    str(binary), "--curve", "131", "--packed", "--threads", str(population),
                    "--steps", str(STEPS), "--launches", str(LAUNCHES), "--run-id", str(RUN_ID),
                    "--dp-weight", "32", "--verify", "0", "--dp-file", str(dpfile),
                ]
                out = command(args, timeout=240)
                if "0 dropped)" not in out:
                    raise AssertionError("dropped or unreported DP records")
                shape = re.findall(
                    r"backend cuda-packed131: (\d+) threads x (\d+) slots x 1 lanes = (\d+) walks, "
                    r"dp weight (\d+), (\d+) steps per launch", out)
                if len(shape) != 1 or tuple(map(int, shape[0])) != (
                    population, BATCH, population * BATCH, 32, STEPS):
                    raise AssertionError("worker geometry mismatch")
                counts = [int(x) for x in re.findall(r"M it/s\s+(\d+) iterations", out)]
                expected = population * BATCH * STEPS * LAUNCHES
                if not counts or counts[-1] != expected or counts != sorted(counts):
                    raise AssertionError(f"incorrect completed updates: {counts[-1:]}, want {expected}")
                match = re.search(r"finished: ([0-9.]+) M it/s, (\d+) distinguished points", out)
                if not match:
                    raise AssertionError("missing final rate")
                n, digest = record_summary(dpfile)
                if n != int(match[2]):
                    raise AssertionError("DP file/report count mismatch")
                telem = command([
                    "nvidia-smi", "--query-gpu=uuid,pstate,clocks.current.sm,power.draw,temperature.gpu",
                    "--format=csv,noheader"]).strip()
                sample = {
                    "population": population, "repetition": repetition, "phase": phase,
                    "arm": label, "binary_sha256": sha(binary), "command": args,
                    "raw": out, "complete_updates": expected,
                    "rate_billion_per_second": float(match[1]) / 1000,
                    "dp_records": n, "dp_sorted_sha256": digest, "dropped": 0,
                    "gpu_telemetry": telem,
                }
                result["samples"].append(sample)
                print("SAMPLE_RECEIPT " + json.dumps({k: v for k, v in sample.items()
                    if k not in ("raw", "command", "gpu_telemetry")}), flush=True)
                return sample

            result["population_results"] = []
            for population in POPULATIONS:
                expected_digest = None
                measure("A", pinned, population, -1, "warm")
                measure("B", candidate, population, -1, "warm")
                pairs = []
                for rep in range(PAIRS):
                    order = (("A", pinned), ("B", candidate))
                    if rep % 2:
                        order = tuple(reversed(order))
                    samples = {}
                    for label, binary in order:
                        sample = measure(label, binary, population, rep, "timed")
                        if expected_digest is None:
                            expected_digest = sample["dp_sorted_sha256"]
                        if sample["dp_sorted_sha256"] != expected_digest:
                            raise AssertionError("DP32 corpus changed between arms or repetitions")
                        samples[label] = sample
                    ratio = samples["B"]["rate_billion_per_second"] / samples["A"]["rate_billion_per_second"]
                    pairs.append(ratio)
                    print("PAIR_RECEIPT " + json.dumps({
                        "population": population, "repetition": rep, "ratio": ratio}), flush=True)
                returning = measure("A", pinned, population, PAIRS, "return")
                if returning["dp_sorted_sha256"] != expected_digest:
                    raise AssertionError("return-control corpus changed")
                row = {
                    "population": population, "pairs": pairs,
                    "median_ratio": statistics.median(pairs),
                    "minimum_ratio": min(pairs), "maximum_ratio": max(pairs),
                    "corpus_sha256": expected_digest,
                    "return_rate_billion_per_second": returning["rate_billion_per_second"],
                    "screen_target_met": min(pairs) >= 1.5,
                }
                result["population_results"].append(row)
                print("POPULATION_RECEIPT " + json.dumps(row), flush=True)
            result["valid"] = True
    except Exception as exc:
        result["error"] = repr(exc)
        print("ERROR_RECEIPT " + repr(exc), flush=True)
    finally:
        result["completed_at_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--pinned", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-dirty-json", required=True)
    parser.add_argument("--source-tar-sha256", required=True)
    args = parser.parse_args()
    dest = args.output.expanduser().resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        raise FileExistsError(dest)
    driver_hash = sha(Path(__file__).resolve())
    result = experiment(args.root.resolve(), args.pinned.resolve(), driver_hash,
                        args.source_commit, json.loads(args.source_dirty_json),
                        args.source_tar_sha256)
    dest.write_text(json.dumps(result, indent=2) + "\n")
    print("SAVED_RECEIPT " + str(dest), flush=True)
    print(json.dumps({"valid": result["valid"], "error": result.get("error"),
        "population_results": result.get("population_results", [])}), flush=True)


if __name__ == "__main__":
    main()
