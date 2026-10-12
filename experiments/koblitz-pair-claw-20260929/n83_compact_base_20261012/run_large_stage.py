#!/usr/bin/env python3
"""Match eager and compact point access on the 200,000-orbit N83 base."""

import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAIR = HERE.parent
ROOT = PAIR.parents[1]
CODEGEN = ROOT / "ecc2k130/runner/codegen"
sys.path[:0] = [str(CODEGEN), str(PAIR), str(HERE)]

import field  # noqa: E402
import bench_n83_zero_run_stage as zero_stage  # noqa: E402
from generate import generate  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main():
    assert platform.machine().lower() in ("arm64", "aarch64")
    output = HERE / "large_stage.json"
    assert not output.exists(), "large stage already frozen"
    base_receipt_path = HERE / "large_base.json"
    base_receipt = json.loads(base_receipt_path.read_text())
    key_path = HERE / "large_base_keys_and_logs.bin"
    assert base_receipt["K"] == 200000
    assert sha(key_path) == base_receipt["key_and_log_file_sha256"]
    parent_path = PAIR / "n83_fresh_m32_k23859_20261012/protocol.json"
    parent = json.loads(parent_path.read_text())
    assert all(sha(path) == digest for path, digest in zero_stage.FROZEN.items())
    assert sha(zero_stage.HEADER) == (
        "33219306bc0db8a17e81aa3863a643b94cc96905018ac9ef38aa2c22d354738f")
    K = base_receipt["K"]
    M = parent["workload"]["table_descriptors"]
    step = parent["workload"]["table_step"]
    offset = parent["workload"]["table_offset"]
    domain = base_receipt["pair_rank_domain"]
    assert math.gcd(step, domain) == 1 and M + 80 * (1 << 29) <= domain
    query_offset = (offset + step * M) % domain
    onb = field.Onb(83)
    target_xy = [format(onb.toCoords(x), "x")
                 for x in parent["target_public_point_onb_raw"]]
    report = {
        "kind": "n83_k200000_eager_vs_compact_base_matched_stage",
        "status": "started",
        "workload_id": parent["workload_id"],
        "parent_protocol_sha256": sha(parent_path),
        "large_base_receipt_sha256": sha(base_receipt_path),
        "base_file_sha256": sha(key_path),
        "compact_source_sha256": sha(HERE / "compact_base.inc"),
        "generator_source_sha256": sha(HERE / "generate.py"),
        "driver_source_sha256": sha(Path(__file__)),
        "source_sha256": {str(path.relative_to(ROOT)): sha(path)
                          for path in zero_stage.FROZEN},
        "K": K,
        "B": 166 * K,
        "query_offset": query_offset,
        "M": 1 << 20,
        "R": 1 << 18,
        "timing_tier": "exploratory_local_unisolated",
        "cells": [],
    }
    save(output, report)
    with tempfile.TemporaryDirectory(prefix="n83-compact-large-stage-") as temporary:
        work = Path(temporary)
        bundles = {}
        for mode in ("eager", "compact"):
            bundle = work / mode
            bundle.mkdir()
            if mode == "eager":
                paths = zero_stage.generated_sources(bundle)
                shutil.copyfile(zero_stage.HEADER, bundle / "eccF83.h")
                hashes = {path.name: sha(path) for path in (*paths, bundle / "eccF83.h")}
            else:
                hashes = generate(bundle)
            binary = work / f"pairclaw_{mode}"
            build = ["c++", "-O3", "-std=c++17", "-march=armv8.2-a+crypto",
                     "-DECC2K83_FAST_KEYER=1", "-DECC2K83_ORBITS=200000",
                     str(bundle / "alt_main.cpp"), "-o", str(binary)]
            try:
                compiled = subprocess.run(build, capture_output=True, text=True,
                                          timeout=300)
            except subprocess.TimeoutExpired as exc:
                report["status"] = "build_timeout"
                report["build_timeout_mode"] = mode
                report["build_timeout_seconds"] = exc.timeout
                save(output, report)
                return
            bundles[mode] = {"binary": binary, "source_sha256": hashes,
                             "build_returncode": compiled.returncode,
                             "build_stderr": compiled.stderr[-4000:]}
            if compiled.returncode != 0:
                report["status"] = "build_failure"
                report["builds"] = {key: {k: v for k, v in value.items()
                                          if k != "binary"}
                                    for key, value in bundles.items()}
                save(output, report)
                return
            bundles[mode]["binary_sha256"] = sha(binary)
        report["builds"] = {key: {k: v for k, v in value.items()
                                  if k != "binary"}
                            for key, value in bundles.items()}
        save(output, report)
        for mode in ("eager", "compact"):
            binary = bundles[mode]["binary"]
            native = [str(binary), str(key_path), *target_xy,
                      str(1 << 20), str(1 << 18), "1024", str(step), str(offset),
                      str(step), str(query_offset), "15", "10", "0", "0", "4", "8"]
            environment = os.environ.copy()
            environment["ECC2K83_CANDIDATE_TMPDIR"] = str(work)
            started = time.perf_counter()
            try:
                completed = subprocess.run(native, capture_output=True, text=True,
                                           env=environment, timeout=600)
            except subprocess.TimeoutExpired as exc:
                report["status"] = "native_timeout"
                report["cells"].append({"mode": mode,
                                        "wall_seconds": time.perf_counter() - started,
                                        "timeout_seconds": exc.timeout})
                save(output, report)
                return
            row = {"mode": mode, "returncode": completed.returncode,
                   "wall_seconds": time.perf_counter() - started,
                   "stderr": completed.stderr[-4000:]}
            if completed.returncode == 0:
                result_path = HERE / f"large_{mode}.json"
                result = json.loads(completed.stdout)
                save(result_path, result)
                row["result_sha256"] = sha(result_path)
                row["peak_rss_bytes"] = result["peak_rss_bytes"]
            else:
                row["stdout_tail"] = completed.stdout[-4000:]
            report["cells"].append(row)
            save(output, report)
        if all(row["returncode"] == 0 for row in report["cells"]):
            reference = json.loads((HERE / "large_eager.json").read_text())
            candidate = json.loads((HERE / "large_compact.json").read_text())
            fields = ["actual_B", "table_descriptors", "query_representatives",
                      "lifted_query_pairs", "bloom_bytes", "bloom_positive_queries",
                      "duplicate_positive_keys", "exact_hit_keys", "exact_hit_queries",
                      "false_positive_queries", "complement_identity_queries", "hits"]
            report["parity_fields"] = fields
            report["status"] = "PASS" if all(
                reference[key] == candidate[key] for key in fields) else "result_mismatch"
        else:
            report["status"] = "native_failure"
    save(output, report)
    print(json.dumps({"status": report["status"], "K": K,
                      "peaks": [row.get("peak_rss_bytes") for row in report["cells"]]}))


if __name__ == "__main__":
    main()
