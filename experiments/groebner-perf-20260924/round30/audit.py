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
SOURCES = {"round30/row_map.metal", "round30/row_map.mm", "round30/run.py", "round30/audit.py",
           "round29/active_panel.metal", "round29/active_rref.mm",
           "round7/local_panel.metal", "round7/local_rref.mm"}
TIMES = ("cpu_wall_ms", "cpu_thread_ms", "previous_wall_ms", "previous_device_ms",
         "mapped16_wall_ms", "mapped16_device_ms", "mapped32_wall_ms", "mapped32_device_ms", "other32_wall_ms", "other32_device_ms")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def number(x):
    return type(x) in (int, float) and math.isfinite(x)


def correctness(data):
    require(data["schema"] == "row-map-correctness/2", "correctness schema")
    require(data["exact_rank_and_rref"] is True and data["timing_eligible"] is False, "correctness qualification")
    require(data["checked_matrices"] == 6336 and data["invalid_inputs_rejected"] == 3, "correctness counts")
    require(data["tested_word_skip"] == [True, False], "both word-skip paths required")
    require(data["mapped_calls"] > 0 and data["fallback_calls"] > 0, "kernel route coverage")
    require(data["pivot_threads"] in (256, 512, 1024) and data["seed"] == 2026092930, "correctness configuration")
    require(type(data["word_skip"]) is bool, "word-skip configuration")


def measurement(data):
    require(data["schema"] == "row-map-measurement/2", "measurement schema")
    require(data["exact_rank_and_rref"] is True and data["timing_eligible"] is True, "measurement qualification")
    require(data["checked_matrices"] == 768 and len(data["cells"]) == 6, "measurement counts")
    require(data["previous_pivot_threads"] == 512 and data["previous_indirect"] is False, "frozen GPU configuration")
    require(data["seed"] == 2026092507 and data["m4ri_k"] == 5 and data["cpu_qos"] == "USER_INITIATED", "measurement configuration")
    require(data["pivot_threads"] in (256, 512, 1024), "pivot threads")
    require(type(data["word_skip"]) is bool, "word-skip configuration")
    require(data["other32_word_skip"] is (not data["word_skip"]), "paired ablation configuration")
    cpus = data["logical_cpus"]
    require(type(cpus) is int and cpus > 0, "CPU count")
    for key in ("load_initial", "load_final"):
        require(number(data[key]) and 0 <= data[key] <= cpus, "load admission")
    for cell, (name, rows, cols, rank) in zip(data["cells"], EXPECTED):
        require((cell["name"], cell["rows"], cell["cols"], cell["matrix_count"]) == (name, rows, cols, 1), "frozen matrix identity")
        require(len(cell["samples"]) == 32, "paired sample count")
        for rep, sample in enumerate(cell["samples"]):
            require(sample["warmup"] is (rep == 0), "warmup identity")
            require(sorted(sample["order"]) == [0, 1, 2, 3, 4], "paired arm order")
            require(sample["rank"] == rank, "frozen exact rank")
            require(number(sample["load1"]) and 0 <= sample["load1"] <= cpus, "group load admission")
            for key in TIMES:
                require(number(sample[key]) and sample[key] > 0, "invalid timing")
            for arm in ("previous", "mapped16", "mapped32", "other32"):
                require(sample[f"{arm}_device_ms"] <= sample[f"{arm}_wall_ms"] + 0.001, "device interval exceeds wall interval")
            for arm in ("mapped16", "mapped32", "other32"):
                require(type(sample[f"{arm}_fallback"]) is bool, "fallback route")
                require(sample[f"{arm}_fallback"] is False, "measurement used fallback")


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
                      "previous_over_mapped16": ratio(samples, "previous_wall_ms", "mapped16_wall_ms"),
                      "previous_over_mapped32": ratio(samples, "previous_wall_ms", "mapped32_wall_ms"),
                      "cpu_over_mapped16": ratio(samples, "cpu_wall_ms", "mapped16_wall_ms"),
                      "cpu_over_mapped32": ratio(samples, "cpu_wall_ms", "mapped32_wall_ms"),
                      "word_skip_gain": ratio(samples, "other32_wall_ms" if data["word_skip"] else "mapped32_wall_ms",
                                              "mapped32_wall_ms" if data["word_skip"] else "other32_wall_ms")})
    return {"schema": "row-map-summary/2", "device": data["device"], "pivot_threads": data["pivot_threads"], "word_skip": data["word_skip"],
            "scope": "single-matrix RREF only", "checked_matrices": data["checked_matrices"],
            "measured_pairs_per_cell": 31, "included_warmup_pairs_per_cell": 1, "cells": cells}


def audit(directory):
    receipt = json.loads((directory / "receipt.json").read_text())
    require(receipt["schema"] == "row-map-receipt/1" and receipt["status"] == "PASS", "receipt status")
    require(receipt["compile_returncode"] == 0, "compile status")
    require(set(receipt["sources"]) == SOURCES, "source inventory")
    for name, digest in receipt["sources"].items():
        require(sha(directory / "sources" / name) == digest, "snapshot hash")
        require(sha(HERE.parent / name) == digest, "trusted current source hash")
    require(sha(directory / "row-map") == receipt["binary_sha256"], "binary hash")
    require(sha(directory / "matrices.json") == receipt["matrix_sha256"], "matrix hash")
    frozen = HERE.parent / "round3/matrices.json.gz"
    require(sha(frozen) == receipt["matrix_gz_sha256"], "frozen input source")
    require(hashlib.sha256(gzip.decompress(frozen.read_bytes())).hexdigest() == receipt["matrix_sha256"], "frozen input content")
    require(f"-DMAP_THREADS={receipt['pivot_threads']}" in receipt["compile_command"], "compile thread configuration")
    require(f"-DMAP_SKIP_WORDS={int(receipt['word_skip'])}" in receipt["compile_command"], "compile word-skip configuration")
    require("-DACTIVE_THREADS=512" in receipt["compile_command"] and "-DACTIVE_INDIRECT=0" in receipt["compile_command"], "frozen GPU compilation")
    require(receipt["previous_pivot_threads"] == 512 and receipt["previous_indirect"] is False, "frozen GPU receipt")
    frozen = (directory / "sources/round29/active_rref.mm").read_text()
    marker = "int main(int argc,char**argv)"
    require(frozen.count(marker) == 1, "frozen baseline entrypoint")
    generated = directory / "sources/round29/active_rref_library.mm"
    require(generated.read_text() == frozen.replace(marker, "int unused_round29_main(int argc,char**argv)"), "generated baseline content")
    require(sha(generated) == receipt["generated_library_sha256"], "generated baseline hash")
    compile_command = receipt["compile_command"]
    require(compile_command[:4] == ["clang++", "-O3", "-std=c++17", "-fobjc-arc"], "compiler configuration")
    require(compile_command[-2] == "-o" and Path(compile_command[-1]).name == "row-map", "compiler output")
    require(sum(str(x).endswith("/sources/round30/row_map.mm") for x in compile_command) == 1, "compiler source")
    modes = {"correctness", "measure"} if receipt["mode"] == "all" else {"correctness"}
    require(receipt["mode"] in ("correctness", "all") and set(receipt["runs"]) == modes, "run modes")
    summary = None
    for mode, run in receipt["runs"].items():
        require(run["status"] == "PASS" and run["returncode"] == 0, "run status")
        command = run["command"]
        require(len(command) == 6 and Path(command[0]).name == "row-map" and command[-1] == mode, "run entrypoint")
        require(command[1].endswith("/sources/round7/local_panel.metal") and command[2].endswith("/sources/round29/active_panel.metal")
                and command[3].endswith("/sources/round30/row_map.metal") and Path(command[4]).name == "matrices.json", "run source/input binding")
        report_path = directory / f"{mode}.json"
        require(sha(report_path) == run["report_sha256"], "report hash")
        data = json.loads(report_path.read_text())
        require(data["pivot_threads"] == receipt["pivot_threads"], "shader/host threads")
        require(data["word_skip"] is receipt["word_skip"], "shader/host word skip")
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
