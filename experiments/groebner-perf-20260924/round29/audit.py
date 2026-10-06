"""Validate exact-source receipts and summarize paired single-matrix timings."""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import random
import statistics

HERE = Path(__file__).resolve().parent
EXPECTED = [
    ("pdp-31-3-4-seed1", 2915, 4096, 2596),
    ("pdp-31-3-4-seed2", 2915, 4096, 2597),
    ("random-256-1024", 256, 1024, 256),
    ("random-1536-3072", 1536, 3072, 1536),
    ("random-2048-4096", 2048, 4096, 2048),
    ("captured-seed1-duplicate-row-control", 2915, 4096, 1446),
]
SOURCES = {"round29/active_panel.metal", "round29/active_rref.mm", "round29/run.py", "round29/audit.py",
           "round7/local_panel.metal", "round7/local_rref.mm"}
TIMES = ("cpu_wall_ms", "cpu_thread_ms", "previous_wall_ms", "previous_device_ms",
         "active16_wall_ms", "active16_device_ms", "active32_wall_ms", "active32_device_ms")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def number(x):
    return type(x) in (int, float) and math.isfinite(x)


def correctness(data):
    require(data["schema"] == "active-rref-correctness/1", "correctness schema")
    require(data["exact_rank_and_rref"] is True and data["timing_eligible"] is False, "correctness qualification")
    require(data["checked_matrices"] == 3168 and data["invalid_inputs_rejected"] == 3, "correctness counts")
    require(data["local_runs"] > 0 and data["fallback_runs"] > 0 and data["wide_panels"] > 0, "kernel route coverage")
    require(data["pivot_threads"] in (32, 64, 128, 256, 512, 1024) and data["seed"] == 2026092929, "correctness configuration")
    require(type(data["indirect_dispatch"]) is bool, "dispatch configuration")


def measurement(data):
    require(data["schema"] == "active-rref-measurement/1", "measurement schema")
    require(data["exact_rank_and_rref"] is True and data["timing_eligible"] is True, "measurement qualification")
    require(data["checked_matrices"] == 576 and len(data["cells"]) == 6, "measurement counts")
    require(data["seed"] == 2026092507 and data["m4ri_k"] == 5 and data["cpu_qos"] == "USER_INITIATED", "measurement configuration")
    require(data["pivot_threads"] in (32, 64, 128, 256, 512, 1024), "pivot threads")
    require(type(data["indirect_dispatch"]) is bool, "dispatch configuration")
    cpus = data["logical_cpus"]
    require(type(cpus) is int and cpus > 0, "CPU count")
    for key in ("load_initial", "load_final"):
        require(number(data[key]) and 0 <= data[key] <= cpus, "load admission")
    for cell, (name, rows, cols, rank) in zip(data["cells"], EXPECTED):
        require((cell["name"], cell["rows"], cell["cols"], cell["matrix_count"]) == (name, rows, cols, 1), "frozen matrix identity")
        require(len(cell["samples"]) == 32, "paired sample count")
        for rep, sample in enumerate(cell["samples"]):
            require(sample["warmup"] is (rep == 0), "warmup identity")
            require(sorted(sample["order"]) == [0, 1, 2, 3], "paired arm order")
            require(sample["rank"] == rank, "frozen exact rank")
            require(number(sample["load1"]) and 0 <= sample["load1"] <= cpus, "group load admission")
            for key in TIMES:
                require(number(sample[key]) and sample[key] > 0, "invalid timing")
            for arm in ("previous", "active16", "active32"):
                require(sample[f"{arm}_device_ms"] <= sample[f"{arm}_wall_ms"] + 0.001, "device interval exceeds wall interval")
            require(type(sample["active16_local"]) is bool and type(sample["active32_local"]) is bool, "local route")
            for key in ("active32_panels16", "active32_panels32"):
                require(type(sample[key]) is int and sample[key] >= 0, "panel histogram")
            small, large = sample["active32_panels16"], sample["active32_panels32"]
            if sample["active32_local"]:
                require(small*16 + large*32 >= rank, "insufficient panels for rank")
                require(small + large <= (min(rows, cols)+15)//16, "excess panel count")
            else:
                require(small == large == 0, "fallback panel histogram")


def ratio(samples, numerator, denominator):
    logs = [math.log(s[numerator]/s[denominator]) for s in samples]
    rng = random.Random(2026092929)
    boots = sorted(math.exp(statistics.fmean(rng.choices(logs, k=len(logs)))) for _ in range(5000))
    return {"paired_geometric_mean": math.exp(statistics.fmean(logs)), "individual_95_percent": [boots[124], boots[4874]]}


def summarize(data):
    measurement(data)
    cells = []
    for cell in data["cells"]:
        samples = cell["samples"][1:]
        cells.append({"name": cell["name"], "rows": cell["rows"], "cols": cell["cols"],
                      "medians_ms": {key: statistics.median(s[key] for s in samples) for key in TIMES},
                      "previous_over_active16": ratio(samples, "previous_wall_ms", "active16_wall_ms"),
                      "previous_over_active32": ratio(samples, "previous_wall_ms", "active32_wall_ms"),
                      "cpu_over_active16": ratio(samples, "cpu_wall_ms", "active16_wall_ms"),
                      "cpu_over_active32": ratio(samples, "cpu_wall_ms", "active32_wall_ms")})
    return {"schema": "active-rref-summary/1", "device": data["device"], "pivot_threads": data["pivot_threads"], "indirect_dispatch": data["indirect_dispatch"],
            "scope": "single-matrix RREF only", "checked_matrices": data["checked_matrices"],
            "measured_pairs_per_cell": 31, "included_warmup_pairs_per_cell": 1, "cells": cells}


def audit(directory):
    receipt = json.loads((directory / "receipt.json").read_text())
    require(receipt["schema"] == "active-rref-receipt/1" and receipt["status"] == "PASS", "receipt status")
    require(receipt["compile_returncode"] == 0, "compile status")
    require(set(receipt["sources"]) == SOURCES, "source inventory")
    for name, digest in receipt["sources"].items():
        require(sha(directory / "sources" / name) == digest, "snapshot hash")
        require(sha(HERE.parent / name) == digest, "trusted current source hash")
    require(sha(directory / "active-rref") == receipt["binary_sha256"], "binary hash")
    require(sha(directory / "matrices.json") == receipt["matrix_sha256"], "matrix hash")
    frozen = HERE.parent / "round3/matrices.json.gz"
    require(sha(frozen) == receipt["matrix_gz_sha256"], "frozen input source")
    require(hashlib.sha256(gzip.decompress(frozen.read_bytes())).hexdigest() == receipt["matrix_sha256"], "frozen input content")
    require(f"-DACTIVE_THREADS={receipt['pivot_threads']}" in receipt["compile_command"], "compile thread configuration")
    require(f"-DACTIVE_INDIRECT={int(receipt['indirect_dispatch'])}" in receipt["compile_command"], "compile dispatch configuration")
    compile_command = receipt["compile_command"]
    require(compile_command[:4] == ["clang++", "-O3", "-std=c++17", "-fobjc-arc"], "compiler configuration")
    require(compile_command[-2] == "-o" and Path(compile_command[-1]).name == "active-rref", "compiler output")
    require(sum(str(x).endswith("/sources/round29/active_rref.mm") for x in compile_command) == 1, "compiler source")
    modes = {"correctness", "measure"} if receipt["mode"] == "all" else {"correctness"}
    require(receipt["mode"] in ("correctness", "all") and set(receipt["runs"]) == modes, "run modes")
    summary = None
    for mode, run in receipt["runs"].items():
        require(run["status"] == "PASS" and run["returncode"] == 0, "run status")
        command = run["command"]
        require(len(command) == 5 and Path(command[0]).name == "active-rref" and command[-1] == mode, "run entrypoint")
        require(command[1].endswith("/sources/round7/local_panel.metal") and command[2].endswith("/sources/round29/active_panel.metal")
                and Path(command[3]).name == "matrices.json", "run source/input binding")
        report_path = directory / f"{mode}.json"
        require(sha(report_path) == run["report_sha256"], "report hash")
        data = json.loads(report_path.read_text())
        require(data["pivot_threads"] == receipt["pivot_threads"], "shader/host threads")
        require(data["indirect_dispatch"] is receipt["indirect_dispatch"], "shader/host dispatch")
        require(run["loaded_m4ri_sha256"] == receipt["m4ri_sha256"], "loaded library identity")
        require(run["checked_matrices"] == data["checked_matrices"], "receipt result count")
        if mode == "correctness":
            correctness(data)
        else:
            require(data["logical_cpus"] == receipt["logical_cpus"], "load CPU envelope")
            summary = summarize(data)
    return {"status": "PASS", "exact_sources": len(SOURCES), "receipt_sha256": sha(directory / "receipt.json"),
            "summary": summary}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.directory), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
