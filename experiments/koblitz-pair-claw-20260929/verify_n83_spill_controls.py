#!/usr/bin/env python3
"""Q1060: compare disk-spooled candidates to Q1059 and replay planted log."""

import hashlib
import json
import math
import os
import subprocess
from pathlib import Path

import n83_low_memory_smoke_check as smoke_check
import verify_n83_signed_x_planted as control

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
SOURCE = HERE / "native_n83_orbit_query_spill.cpp"
PLANTED = RUNS / "n83_fast_low_memory_planted.json"
PUBLIC = RUNS / "n83_fast_lowmem_k48194_chunk_M20_R14_tstart0_qstart1073741824_b20_h10_rb8.json"
RUNTIME = RUNS / "n83_spill_controls_runtime_info.json"
OUTPUT = RUNS / "n83_spill_controls.json"
BINARY = Path("/private/tmp/ecc2k83-fast-spill-controls")
SPILL_DIR = Path("/Volumes/SSD990/llm/tmp")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact_equal(actual, reference):
    for key in smoke_check.EQUAL_NATIVE_FIELDS:
        assert actual[key] == reference[key], key
    assert actual["candidate_store_mode"] == "unlinked_file"
    assert actual["candidate_spill_bytes"] == (
        actual["bloom_positive_queries"] * 24)
    assert actual["candidate_vector_capacity_bytes"] == 0


def native_run(command):
    env = os.environ.copy()
    env["ECC2K83_CANDIDATE_TMPDIR"] = str(SPILL_DIR)
    return json.loads(subprocess.run(command, check=True, capture_output=True,
                                     text=True, env=env).stdout)


def main():
    runtime = json.loads(RUNTIME.read_text())
    assert runtime["status"] == "verified"
    assert SPILL_DIR.is_dir()
    planted_ref = json.loads(PLANTED.read_text())
    public_ref = json.loads(PUBLIC.read_text())
    assert planted_ref["proposal_id"] == public_ref["proposal_id"] == "Q1059"
    assert planted_ref["curve_id"] == public_ref["curve_id"] == (
        "EC1N83Ckb1h876c2921cb64")
    assert planted_ref["isogeny"] == public_ref["isogeny"] == "none"
    assert planted_ref["factor_base_enumerated_set_sha256"] == public_ref[
        "factor_base"]["enumerated_set_sha256"]
    assert planted_ref["verified_relation"]["independent_scalar_replay"]
    compiler = ["clang++", "-O3", "-std=c++17",
                "-march=armv8.2-a+crypto", "-DECC2K83_ORBITS=48194",
                "-DECC2K83_FAST_KEYER=1", str(SOURCE), "-o", str(BINARY)]
    subprocess.run(compiler, check=True)
    planted_command = list(planted_ref["native_command"])
    planted_command[0] = str(BINARY)
    planted = native_run(planted_command)
    exact_equal(planted, planted_ref["native_result"])
    assert planted["exact_hit_queries"] == 1

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

    public_target = tuple(public_ref["public_target"])
    table_schedule = public_ref["table_schedule"]
    query_schedule = public_ref["query_representative_schedule"]
    public_command = [
        str(BINARY), str(key_path),
        format(onb.toCoords(public_target[0]), "x"),
        format(onb.toCoords(public_target[1]), "x"),
        str(public_ref["table_descriptors"]),
        str(public_ref["query_representatives"]), "1024",
        str(table_schedule["step"]), str(table_schedule["offset"]),
        str(query_schedule["step"]), str(query_schedule["offset"]),
        "20", "10", str(public_ref["table_start"]),
        str(public_ref["query_start"]), "14", "8",
    ]
    public = native_run(public_command)
    exact_equal(public, public_ref["native_result"])
    assert public["exact_hit_queries"] == 0
    report = {
        "kind": "n83_spilled_candidate_exact_controls",
        "scope": "small public-target and planted exact controls; no natural relation, full-size memory, or speedup claim",
        "proposal_id": "Q1060", "candidate_id": None,
        "curve_id": public_ref["curve_id"], "isogeny": "none",
        "public_target": list(public_target),
        "factor_base_enumerated_set_sha256": factor[
            "enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": factor[
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": factor["signed_frobenius_columns"],
        "candidate_spill_directory": str(SPILL_DIR),
        "planted_native_result": planted,
        "planted_verified_relation": certificate,
        "public_native_result": public,
        "public_exact_outcomes_equal_to_Q1059": True,
        "natural_relation_yield": False,
        "complete_solve_work_log2": None,
        "compiler_command": compiler,
        "planted_native_command": planted_command,
        "public_native_command": public_command,
        "binary_sha256": sha(BINARY),
        "native_source_sha256": sha(SOURCE),
        "native_pairs_sha256": sha(control.PAIRS),
        "bloom_core_sha256": sha(control.CORE),
        "Q1059_planted_receipt_sha256": sha(PLANTED),
        "Q1059_public_receipt_sha256": sha(PUBLIC),
        "sage_runtime_info_sha256": sha(RUNTIME),
        "source_sha256": sha(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"planted_exact_hits": planted["exact_hit_queries"],
                      "public_positives": public["bloom_positive_queries"],
                      "public_exact_hits": public["exact_hit_queries"],
                      "independent_scalar_replay": True}))


if __name__ == "__main__":
    main()
