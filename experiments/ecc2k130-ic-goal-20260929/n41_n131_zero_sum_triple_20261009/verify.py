#!/usr/bin/env python3
"""Verify both frozen attempts, independent audit, and transfer arithmetic."""

import hashlib
import json
from pathlib import Path
from fractions import Fraction

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def main():
    protocol = read(HERE / "protocol.json")
    geometry = read(HERE / "geometry_result.json")
    audit = read(HERE / "audit.json")
    transfer = read(HERE / "transfer_result.json")
    assert protocol["status"] == "FROZEN"
    paths = {"freeze": HERE / "freeze.py", "prepare": HERE / "prepare.py",
             "join_source": HERE / "join.cpp", "join_binary": HERE / "join",
             "runner": HERE / "run.py", "audit": HERE / "audit.py",
             "runtime": HERE / "sage_runtime_info.json",
             "screen": GOAL / "n131_w18_four_pairs/screen.json",
             "geometry": HERE / "geometry_result.json",
             "n131_valid_bits": HERE / "n131_valid_mask_bits.bin",
             "input_control": HERE / "input_control.txt",
             "input_public": HERE / "input_public.txt",
             "control_witness": HERE / "control_witness.json",
             "helper": GOAL / "n131_w18_four_pairs/native_join/frozen_source/helper.cpp"}
    assert all(protocol["sha256"][key] == sha(path)
               for key, path in paths.items())
    assert geometry["sha256"]["source"] == sha(HERE / "prepare.py")
    assert geometry["sha256"]["public_input"] == sha(HERE / "input_public.txt")
    assert geometry["sha256"]["control_input"] == sha(HERE / "input_control.txt")
    assert geometry["sha256"]["n131_valid_bits"] == sha(HERE / "n131_valid_mask_bits.bin")
    assert audit["status"] == "PASS_INDEPENDENT_SAGE_AUDIT"
    assert audit["protocol_sha256"] == sha(HERE / "protocol.json")

    first = read(HERE / "attempt1_failure.json")
    assert first["status"] == "PRODUCER_FAILURE"
    assert first["protocol_sha256"] == sha(HERE / "protocol_v1.json")
    assert first["source_sha256"] == sha(HERE / "join_v1.cpp")
    assert first["binary_sha256"] == sha(HERE / "join_v1")
    assert first["control_result_sha256"] == sha(HERE / "control_v1/result.json")
    assert first["public_result_sha256"] == sha(HERE / "public_v1/result.json")
    assert sha(HERE / "join_v1.cpp") == read(HERE / "protocol_v1.json")["sha256"]["join_source"]

    cases = {}
    for mode in ("control", "public"):
        folder = HERE / mode
        result = read(folder / "result.json")
        terminal = read(folder / "terminal.json")
        assert result["status"] == terminal["status"] == "VERIFIED_RAW_ROW"
        assert terminal["protocol_sha256"] == sha(HERE / "protocol.json")
        assert terminal["result_sha256"] == sha(folder / "result.json")
        assert terminal["stdout_sha256"] == sha(folder / "stdout.txt")
        assert terminal["stderr_sha256"] == sha(folder / "stderr.txt")
        assert terminal["returncode"] == 0
        assert result["source_states"] == [2520] * 4
        assert result["triple_column_rejects"] == 64
        assert result["setup_ns"] == sum(result[key] for key in
               ("triple_build_ns", "left_build_ns", "left_sort_ns"))
        assert result["online_ns"] == result["query_ns"] + result["online_overhead_ns"]
        assert result["setup_ns"] < 300 * 10**9
        assert result["online_ns"] < 120 * 10**9
        assert result["peak_rss_bytes"] < 4 * 1024**3
        assert len(result["row"]) == 12
        assert len({leaf["column"] for leaf in result["row"]}) == 12
        cases[mode] = {"setup_ns": result["setup_ns"],
                       "online_ns": result["online_ns"],
                       "right_probes": result["right_probes"]}

    assert transfer["status"] == "EXACT_TRANSFER_SCREEN"
    assert transfer["sha256"]["source"] == sha(HERE / "transfer.py")
    assert transfer["sha256"]["geometry"] == sha(HERE / "geometry_result.json")
    assert transfer["sha256"]["audit"] == sha(HERE / "audit.json")
    assert transfer["sha256"]["public"] == sha(HERE / "public/result.json")
    r = geometry["n131"]["subgroup_order"]
    t = geometry["n131"]["unordered_zero_sum_triples"]
    v = geometry["n131"]["valid_masks"]
    k = geometry["n131"]["existing_folded_columns_K"]
    m = 8 * t
    col_max = v - k + 1
    bad = col_max * (col_max - 1) // 2
    low = 8 * (t - bad)
    inc = 8 * ((v - 1) // 2) * col_max
    entries_low = low * max(0, low - 3 * inc)
    assert transfer["signed_states_per_block_upper"] == m
    assert transfer["bad_triple_shapes_upper"] == bad
    assert transfer["admissible_signed_states_per_block_lower"] == low
    assert transfer["cross_distinct_two_block_descriptor_entries_lower"] == entries_low
    assert transfer["literal_cross_distinct_key_payload_bytes_lower"] == entries_low * 17
    max_keys = 4 * 1024**3 // 17
    probability = Fraction(max_keys * m*m, r - 1)
    assert (probability.numerator, probability.denominator) == (
        transfer["uniform_target_max_keys_full_right_probability_bound_numerator"],
        transfer["uniform_target_max_keys_full_right_probability_bound_denominator"])
    signature = read(HERE / "signature_result.json")
    assert signature["status"] == "PASS_EXACT_SIGNATURE_SCREEN"
    assert signature["sha256"] == {
        "source": sha(HERE / "signature_screen.py"),
        "input": sha(HERE / "input_public.txt"),
        "geometry": sha(HERE / "geometry_result.json"),
        "runtime": sha(HERE / "signature_runtime_info.json")}
    assert signature["source_states"] == 2520
    assert signature["unique_projected_group_sums"] == 2520
    assert signature["unique_z_values"] == 1260
    assert signature["z_binary_linear_rank"] == 41
    assert signature["z_boolean_degree_two_dimension"] == 862
    assert signature["z_boolean_degree_two_rank"] == 862
    fiber = read(HERE / "target_fiber_result.json")
    assert fiber["status"] == "PASS_RAW_TARGET_FIBER"
    assert fiber["sha256"] == {
        "source": sha(HERE / "target_fiber.py"),
        "public_input": sha(HERE / "input_public.txt"),
        "public_result": sha(HERE / "public/result.json"),
        "runtime": sha(HERE / "signature_runtime_info.json")}
    assert len({tuple(point) for point in fiber["raw_target_fiber"]}) == 4
    assert fiber["public_row_fiber_index"] == 2
    assert fiber["public_row_raw_sum"] == fiber["raw_target_fiber"][2]
    print(json.dumps({"status": "PASS_FROZEN_TRIPLE_EVIDENCE",
                      "cases": cases, "n131_triples": t,
                      "literal_key_payload_lower_bytes": entries_low * 17},
                     sort_keys=True))


if __name__ == "__main__":
    main()
