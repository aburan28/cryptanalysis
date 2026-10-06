#!/usr/bin/env python3
"""Q1059: replay a nonzero-offset planted scalar with fast keys and h=10."""

import hashlib
import json
import math
import subprocess
from pathlib import Path

import verify_n83_signed_x_planted as control

HERE = Path(__file__).resolve().parent
ORIGINAL = HERE / "runs" / "n83_signed_x_hash10_planted.json"
RUNTIME = HERE / "runs" / "n83_fast_low_memory_planted_runtime_info.json"
OUTPUT = HERE / "runs" / "n83_fast_low_memory_planted.json"
BINARY = Path("/private/tmp/ecc2k83-fast-lowmem-planted")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    runtime = json.loads(RUNTIME.read_text())
    assert runtime["status"] == "verified"
    original = json.loads(ORIGINAL.read_text())
    base_receipt = json.loads(control.BASE_RECEIPT.read_text())
    schedule = json.loads(control.SCHEDULE.read_text())["runs"][1]
    factor = base_receipt["factor_base"]
    identity = base_receipt["curve_identity_record"]
    curve_id = "EC1N83Ckb1h" + hashlib.sha256(json.dumps(
        identity, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False).encode()).hexdigest()[:12]
    assert curve_id == original["curve_id"] == base_receipt["curve_id"]
    assert original["proposal_id"] == "Q1055"
    assert original["verified_relation"]["independent_scalar_replay"]
    assert original["native_source_sha256"] == sha(control.SOURCE)
    assert factor["actual_usable_points_B_before_folding"] == 8000204
    assert factor["signed_frobenius_columns"] == 48194
    key_path = HERE / factor["key_and_log_file"]
    assert sha(key_path) == factor["key_and_log_file_sha256"]
    target = tuple(original["fixture_target"])
    onb = control.field.Onb(83)
    compiler = ["clang++", "-O3", "-std=c++17",
                "-march=armv8.2-a+crypto", "-DECC2K83_ORBITS=48194",
                "-DECC2K83_FAST_KEYER=1",
                str(control.SOURCE), "-o", str(BINARY)]
    subprocess.run(compiler, check=True)
    domain = math.comb(48194, 2) * 166
    table_step = schedule["table_schedule"]["step"]
    table_offset = schedule["table_schedule"]["offset"]
    query_offset = (table_offset + 123456789) % domain
    command = [str(BINARY), str(key_path),
               format(onb.toCoords(target[0]), "x"),
               format(onb.toCoords(target[1]), "x"),
               "4096", "256", "1024", str(table_step), str(table_offset),
               str(table_step), str(query_offset), "20", "10",
               "1024", "256", "8", "8"]
    native = json.loads(subprocess.run(
        command, check=True, capture_output=True, text=True).stdout)
    assert native["bloom_hashes"] == 10
    assert native["actual_B"] == 8000204
    assert native["exact_hit_queries"] >= 1
    expected = original["matched_previously_verified_hit"]
    assert expected in native["hits"]
    keys, logs = control.load_keys_logs(key_path)
    assert len(keys) == len(logs) == 48194
    orbit = control.OrbitKey(onb)
    base = control.CompactOrbitBase(orbit, keys)
    curve = control.curves.Curve(onb)
    generator = tuple(identity["curve"]["generator"])
    order = identity["curve"]["subgroup_order"]
    eigen = factor["frobenius_eigenvalue_mod_r"]
    qfirst, qsecond = original["verified_relation"]["query_pair_indices"]
    adapted = {"table_position": expected["table_position"],
               "query_position": qsecond * (qsecond + 1) // 2 + qfirst,
               "x_key_hex": expected["x_key_hex"]}
    synthetic = dict(schedule)
    synthetic["cross_orbit_zero_pair_class_domain"] = domain
    synthetic["unordered_query_pair_domain"] = len(base) * (len(base) + 1) // 2
    synthetic["query_schedule"] = {"step": 1, "offset": 0}
    certificate = control.verify_hit(curve, orbit, base, logs, target,
                                     generator, order, eigen, adapted, synthetic)
    assert certificate["independent_scalar_replay"] is True
    assert certificate["recovered_scalar"] == original[
        "verified_relation"]["recovered_scalar"]
    assert curve.mul(generator, certificate["recovered_scalar"]) == target
    report = {
        "kind": "n83_fast_low_memory_nonzero_offset_planted_control",
        "scope": "planted correctness control; not natural relation yield or public-target DLP",
        "proposal_id": "Q1059", "candidate_id": None,
        "curve_id": curve_id, "curve_identity_record": identity,
        "isogeny": "none", "fixture_target": list(target),
        "factor_base_enumerated_set_sha256": factor["enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": 8000204,
        "signed_frobenius_columns": 48194,
        "fast_keyer_enabled": True,
        "bloom_hashes": 10, "native_result": native,
        "matched_previously_verified_hit": expected,
        "verified_relation": certificate,
        "natural_relation_yield": False,
        "compiler_command": compiler, "native_command": command,
        "binary_sha256": sha(BINARY),
        "native_source_sha256": sha(control.SOURCE),
        "native_pairs_sha256": sha(control.PAIRS),
        "bloom_core_sha256": sha(control.CORE),
        "base_receipt_sha256": sha(control.BASE_RECEIPT),
        "original_planted_receipt_sha256": sha(ORIGINAL),
        "sage_runtime_info_sha256": sha(RUNTIME),
        "source_sha256": sha(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"exact_hit_queries": native["exact_hit_queries"],
                      "independent_scalar_replay": True}))


if __name__ == "__main__":
    main()
