#!/usr/bin/env python3
"""Compare the exact zero-run keyer on frozen planted and public N83 work."""

import argparse
import hashlib
import json
import os
import platform
import subprocess
import tempfile
from pathlib import Path

from n83_identity_contract import validate_reference

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
MAIN = HERE / "native_n83_orbit_query_spill_portable.cpp"
CORE = HERE / "native_n83_bloom_core_portable.hpp"
PAIRS = HERE / "native_n83_pairs_portable.cpp"
HEADER = HERE.parents[1] / "ecc2k130/runner/generated/eccF83.h"
CONTROL = RUNS / "n83_spill_controls.json"
PLANTED = RUNS / "n83_fast_low_memory_planted.json"
SCREEN = HERE / "n83_full_spill_screen.json"

FROZEN = {
    MAIN: "b82473977ebef9326060774ca396bccfc8a5486432a5637069ee4fb3656aaf54",
    CORE: "8aeab4dade9964d59183706ea73225c43c17a20021c52cf8b147692f1709269f",
    PAIRS: "7cc57186096c8dd4cb2a7cdcb044397aa90f2476838770c6cb602ccc0f93be7d",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(source, old, new):
    assert source.count(old) == 1, old[:70]
    return source.replace(old, new)


def generated_sources(temp):
    pairs = PAIRS.read_text()
    pairs = replace_once(pairs, '#include "../../ecc2k130/runner/generated/eccF83.h"',
                         '#include "eccF83.h"')
    old = '''        V best = bits;
        for (unsigned j = 1; j < N; ++j) {
            bits = ((bits << 1) | (bits >> (N - 1))) & CYCLE_MASK;
            if (bits < best) best = bits;
        }
        return best;'''
    new = '''        if (bits == 0 || bits == CYCLE_MASK) return bits;
        auto rotate = [](V value, unsigned offset) -> V {
            return offset ? ((value << offset) | (value >> (N - offset))) & CYCLE_MASK
                          : value;
        };
        V zeros = (~bits) & CYCLE_MASK;
        V candidates = CYCLE_MASK;
        for (unsigned length = 0; length < N; ++length) {
            V extended = candidates & rotate(zeros, length);
            if (!extended) break;
            candidates = extended;
        }
        V best = CYCLE_MASK;
        while (candidates) {
            unsigned bit = U(candidates) ? unsigned(__builtin_ctzll(U(candidates)))
                : 64 + unsigned(__builtin_ctzll(U(candidates >> 64)));
            best = std::min(best, rotate(bits, N - 1 - bit));
            candidates &= candidates - 1;
        }
        return best;'''
    pairs = replace_once(pairs, old, new)
    core = replace_once(CORE.read_text(),
                        '#include "native_n83_pairs_portable.cpp"',
                        '#include "alt_pairs.cpp"')
    main = replace_once(MAIN.read_text(),
                        '#include "native_n83_bloom_core_portable.hpp"',
                        '#include "alt_core.hpp"')
    paths = [temp / name for name in ("alt_pairs.cpp", "alt_core.hpp", "alt_main.cpp")]
    for path, source in zip(paths, (pairs, core, main)):
        path.write_text(source)
    return paths


def compile_binary(source, binary, backend):
    flags = {"arm_pmull": ["-march=armv8.2-a+crypto"],
             "x86_pclmul": ["-mpclmul", "-msse2"]}[backend]
    command = ["clang++", "-O3", "-std=c++17", *flags,
               "-DECC2K83_ORBITS=48194", "-DECC2K83_FAST_KEYER=1",
               "-I", str(HEADER.parent), str(source), "-o", str(binary)]
    subprocess.run(command, check=True)
    return command


def native(command, spill):
    env = os.environ.copy()
    env["ECC2K83_CANDIDATE_TMPDIR"] = str(spill)
    result = subprocess.run(command, capture_output=True, text=True, env=env)
    assert result.returncode == 0, (
        f"native exit {result.returncode}: {result.stderr[-2000:]}")
    return json.loads(result.stdout)


def same_outcome(a, b):
    for key in ("actual_B", "table_descriptors", "query_representatives",
                "lifted_query_pairs", "bloom_positive_queries",
                "duplicate_positive_keys", "exact_hit_keys", "exact_hit_queries",
                "false_positive_queries", "complement_identity_queries", "hits"):
        assert a[key] == b[key], key


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cpu-backend", required=True,
                        choices=("arm_pmull", "x86_pclmul"))
    parser.add_argument("--out-dir", type=Path, default=RUNS)
    parser.add_argument("--runtime-info", type=Path)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    output = args.out_dir / "n83_zero_run_stage_bounded_comparison.json"
    planted_output = args.out_dir / "n83_zero_run_stage_planted_receipt.json"
    assert not output.exists() and not planted_output.exists()
    arch = platform.machine().lower()
    if args.cpu_backend == "arm_pmull":
        assert arch in ("arm64", "aarch64"), "physical ARM PMULL host required"
        assert args.runtime_info is not None, "local ARM measurement needs checked Sage runtime"
    else:
        assert arch in ("x86_64", "amd64"), "physical x86 PCLMUL host required"
        if Path("/proc/cpuinfo").exists():
            flags = Path("/proc/cpuinfo").read_text().lower()
            assert "pclmulqdq" in flags or "pclmul" in flags
    assert all(sha(path) == digest for path, digest in FROZEN.items())
    if args.runtime_info:
        assert json.loads(args.runtime_info.read_text())["status"] == "verified"
    control = json.loads(CONTROL.read_text())
    planted = json.loads(PLANTED.read_text())
    screen = json.loads(SCREEN.read_text())
    validate_reference(screen)
    assert planted["curve_id"] == screen["curve_id"] == (
        "EC1N83Ckb1h876c2921cb64")
    assert planted["curve_identity_record"] == screen["curve_identity_record"]
    assert planted["factor_base_enumerated_set_sha256"] == screen[
        "factor_base"]["enumerated_set_sha256"]
    assert control["factor_base_enumerated_set_sha256"] == screen[
        "factor_base"]["enumerated_set_sha256"]
    key_path = HERE / screen["factor_base"]["key_and_log_file"]
    assert sha(key_path) == screen["factor_base"]["key_and_log_file_sha256"]
    with tempfile.TemporaryDirectory(prefix="n83-zero-run-stage-") as directory:
        temp = Path(directory)
        alternate_sources = generated_sources(temp)
        original_binary, alternate_binary = temp / "original", temp / "zero_run"
        original_compile = compile_binary(MAIN, original_binary, args.cpu_backend)
        alternate_compile = compile_binary(alternate_sources[2], alternate_binary,
                                           args.cpu_backend)
        seed_command = list(control["planted_native_command"])
        seed_command[1] = str(key_path)
        original_planted = native([str(original_binary), *seed_command[1:]], temp)
        alternate_planted = native([str(alternate_binary), *seed_command[1:]], temp)
        same_outcome(original_planted, alternate_planted)
        assert alternate_planted["exact_hit_queries"] == 1
        assert alternate_planted["hits"] == [planted[
            "matched_previously_verified_hit"]]
        public_command = list(control["public_native_command"])
        public_command[1] = str(key_path)
        public_command[4] = str(1 << 20)
        public_command[5] = str(1 << 18)
        public_command[15] = "4"
        results = {"original": [], "zero_run": []}
        for label, binary in (("original", original_binary),
                              ("zero_run", alternate_binary),
                              ("zero_run", alternate_binary),
                              ("original", original_binary)):
            results[label].append(native([str(binary), *public_command[1:]], temp))
        for row in results["original"] + results["zero_run"]:
            same_outcome(row, results["original"][0])
            assert row["exact_hit_queries"] == 0
        report = {
            "kind": "n83_zero_run_keyer_bounded_native_stage_comparison",
            "scope": "physical ARM, paired M20/R18 public-target stage; plant is a correctness control, no natural relation",
            "proposal_id": "Q1078", "candidate_id": None, "run_id": None,
            "curve_id": planted["curve_id"],
            "curve_identity_record": screen["curve_identity_record"],
            "isogeny": "none",
            "public_target": screen["public_target"],
            "factor_base": screen["factor_base"],
            "factor_base_enumerated_set_sha256": planted[
                "factor_base_enumerated_set_sha256"],
            "actual_usable_points_B_before_folding": 8000204,
            "signed_frobenius_columns": 48194,
            "host_arch": platform.machine(), "host_os": platform.platform(),
            "cpu_backend": args.cpu_backend,
            "planted_original_native_result": original_planted,
            "planted_zero_run_native_result": alternate_planted,
            "public_original_native_results": results["original"],
            "public_zero_run_native_results": results["zero_run"],
            "original_compile_command": original_compile,
            "zero_run_compile_command": alternate_compile,
            "original_binary_sha256": sha(original_binary),
            "zero_run_binary_sha256": sha(alternate_binary),
            "zero_run_generated_source_sha256": {path.name: sha(path)
                                                 for path in alternate_sources},
            "frozen_sources_sha256": {path.name: digest for path, digest in FROZEN.items()},
            "base_control_sha256": sha(CONTROL),
            "planted_reference_sha256": sha(PLANTED),
            "screen_sha256": sha(SCREEN),
            "checked_sage_runtime_info_sha256": (
                sha(args.runtime_info) if args.runtime_info else None),
            "source_sha256": sha(Path(__file__)),
            "natural_relation_yield": False,
            "complete_solve_work_log2": None,
        }
        planted_receipt = {
            "kind": "n83_zero_run_keyer_planted_relation_for_sage_replay",
            "proposal_id": "Q1078", "candidate_id": None, "run_id": None,
            "curve_id": planted["curve_id"],
            "curve_identity_record": planted["curve_identity_record"],
            "isogeny": "none", "fixture_target": planted["fixture_target"],
            "factor_base_enumerated_set_sha256": planted[
                "factor_base_enumerated_set_sha256"],
            "factor_base": screen["factor_base"],
            "native_result": alternate_planted,
            "verified_relation": planted["verified_relation"],
            "zero_run_generated_source_sha256": report["zero_run_generated_source_sha256"],
            "source_sha256": sha(Path(__file__)),
        }
        output.write_text(json.dumps(report, indent=2) + "\n")
        planted_output.write_text(json.dumps(planted_receipt, indent=2) + "\n")
    print(json.dumps({"original_query_seconds": [row["query_seconds"] for row in
                                                  results["original"]],
                      "zero_run_query_seconds": [row["query_seconds"] for row in
                                                 results["zero_run"]],
                      "planted_exact_hits": alternate_planted["exact_hit_queries"],
                      "out": str(output)}))


if __name__ == "__main__":
    main()
