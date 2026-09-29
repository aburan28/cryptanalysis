#!/usr/bin/env python3
"""Exact Q1061 CPU-backend controls against the frozen Q1060 outcomes."""

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import tempfile
from pathlib import Path

import n83_low_memory_smoke_check as smoke
import verify_n83_signed_x_planted as control

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
SOURCE = HERE / "native_n83_orbit_query_spill_portable.cpp"
PAIRS = HERE / "native_n83_pairs_portable.cpp"
CORE = HERE / "native_n83_bloom_core_portable.hpp"
REFERENCE = RUNS / "n83_spill_controls.json"
PLANTED = RUNS / "n83_fast_low_memory_planted.json"
PUBLIC = RUNS / "n83_fast_lowmem_k48194_chunk_M20_R14_tstart0_qstart1073741824_b20_h10_rb8.json"
OUTPUT = RUNS / "n83_portable_controls.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compiler(backend, binary):
    command = ["clang++", "-O3", "-std=c++17"]
    x86_arch = ["-arch", "x86_64"] if platform.system() == "Darwin" else []
    command += {"arm_pmull": ["-march=armv8.2-a+crypto"],
                "x86_pclmul": x86_arch + ["-mpclmul", "-msse2"],
                "x86_generic": x86_arch + ["-mno-pclmul", "-msse2"]}[backend]
    command += ["-DECC2K83_ORBITS=48194", "-DECC2K83_FAST_KEYER=1",
                str(SOURCE), "-o", str(binary)]
    return command


def exact_equal(actual, reference):
    for key in smoke.EQUAL_NATIVE_FIELDS:
        assert actual[key] == reference[key], key
    assert actual["candidate_store_mode"] == "unlinked_file"
    assert actual["candidate_spill_bytes"] == 24 * actual["bloom_positive_queries"]
    assert actual["candidate_vector_capacity_bytes"] == 0


def run_command(command, spill_dir):
    env = os.environ.copy()
    env["ECC2K83_CANDIDATE_TMPDIR"] = str(spill_dir)
    return json.loads(subprocess.run(command, check=True, text=True,
                                     capture_output=True, env=env).stdout)


def verify_planted(planted_ref):
    factor = json.loads(control.BASE_RECEIPT.read_text())["factor_base"]
    identity = planted_ref["curve_identity_record"]
    key_path = HERE / factor["key_and_log_file"]
    assert sha(key_path) == factor["key_and_log_file_sha256"]
    onb = control.field.Onb(83)
    keys, logs = control.load_keys_logs(key_path)
    orbit = control.OrbitKey(onb)
    base = control.CompactOrbitBase(orbit, keys)
    curve = control.curves.Curve(onb)
    target = tuple(planted_ref["fixture_target"])
    generator = tuple(identity["curve"]["generator"])
    order = identity["curve"]["subgroup_order"]
    expected = planted_ref["matched_previously_verified_hit"]
    qfirst, qsecond = planted_ref["verified_relation"]["query_pair_indices"]
    adapted = {"table_position": expected["table_position"],
               "query_position": qsecond * (qsecond + 1) // 2 + qfirst,
               "x_key_hex": expected["x_key_hex"]}
    schedule = json.loads(control.SCHEDULE.read_text())["runs"][1]
    domain = math.comb(48194, 2) * 166
    synthetic = dict(schedule)
    synthetic["cross_orbit_zero_pair_class_domain"] = domain
    synthetic["unordered_query_pair_domain"] = len(base) * (len(base) + 1) // 2
    synthetic["query_schedule"] = {"step": 1, "offset": 0}
    certificate = control.verify_hit(
        curve, orbit, base, logs, target, generator, order,
        factor["frobenius_eigenvalue_mod_r"], adapted, synthetic)
    assert certificate["independent_scalar_replay"]
    assert certificate["recovered_scalar"] == planted_ref[
        "verified_relation"]["recovered_scalar"]
    assert curve.mul(generator, certificate["recovered_scalar"]) == target
    return certificate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", required=True,
                        choices=("arm_pmull", "x86_pclmul", "x86_generic"))
    parser.add_argument("--spill-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=OUTPUT)
    args = parser.parse_args()
    assert args.spill_dir.is_dir()
    baseline = json.loads(REFERENCE.read_text())
    planted_ref = json.loads(PLANTED.read_text())
    public_ref = json.loads(PUBLIC.read_text())
    assert baseline["proposal_id"] == "Q1060"
    assert planted_ref["curve_id"] == public_ref["curve_id"] == (
        "EC1N83Ckb1h876c2921cb64")
    assert planted_ref["isogeny"] == public_ref["isogeny"] == "none"
    factor = json.loads(control.BASE_RECEIPT.read_text())["factor_base"]
    assert factor["actual_usable_points_B_before_folding"] == 8000204
    assert factor["signed_frobenius_columns"] == 48194
    assert factor["enumerated_set_sha256"] == (
        "7e3c95f988225da1d586578529953ad61ae5ed62ca740eb92c2aea6d841a5a02")
    assert baseline["factor_base_enumerated_set_sha256"] == (
        factor["enumerated_set_sha256"])
    with tempfile.TemporaryDirectory(prefix="ecc2k83-portable-") as temp:
        binary = Path(temp) / "query"
        build = compiler(args.backend, binary)
        subprocess.run(build, check=True)
        results = {}
        for label, reference in (("planted", planted_ref), ("public", public_ref)):
            command = list(baseline[label + "_native_command"])
            command[0] = str(binary)
            command[1] = str(HERE / factor["key_and_log_file"])
            native = run_command(command, args.spill_dir)
            exact_equal(native, reference["native_result"])
            results[label] = native
        assert results["planted"]["exact_hit_queries"] == 1
        assert results["public"]["exact_hit_queries"] == 0
        certificate = verify_planted(planted_ref)
        report = {
            "kind": "n83_portable_cpu_exact_controls",
            "scope": "translated/host CPU exact controls; no full-size rate or natural relation",
            "proposal_id": "Q1061", "candidate_id": None,
            "curve_id": public_ref["curve_id"], "isogeny": "none",
            "public_target": public_ref["public_target"],
            "factor_base_enumerated_set_sha256": factor["enumerated_set_sha256"],
            "actual_usable_points_B_before_folding": factor[
                "actual_usable_points_B_before_folding"],
            "signed_frobenius_columns": factor["signed_frobenius_columns"],
            "backend": args.backend, "host_arch": platform.machine(),
            "host_os": platform.platform(),
            "x86_test_is_rosetta_translation": (
                args.backend.startswith("x86") and
                platform.system() == "Darwin" and platform.machine() == "arm64"),
            "compiler_command": build, "binary_sha256": sha(binary),
            "native_source_sha256": sha(SOURCE),
            "native_pairs_sha256": sha(PAIRS),
            "bloom_core_sha256": sha(CORE),
            "baseline_Q1060_controls_sha256": sha(REFERENCE),
            "planted_reference_sha256": sha(PLANTED),
            "public_reference_sha256": sha(PUBLIC),
            "planted_native_result": results["planted"],
            "planted_verified_relation": certificate,
            "public_native_result": results["public"],
            "natural_relation_yield": False,
            "complete_solve_work_log2": None,
            "source_sha256": sha(Path(__file__)),
        }
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"backend": args.backend,
                      "planted_exact_hits": results["planted"]["exact_hit_queries"],
                      "public_positives": results["public"]["bloom_positive_queries"],
                      "public_exact_hits": results["public"]["exact_hit_queries"],
                      "independent_scalar_replay": True,
                      "receipt": str(args.out)}))


if __name__ == "__main__":
    main()
