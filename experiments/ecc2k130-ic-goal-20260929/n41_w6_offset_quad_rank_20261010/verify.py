"""Bind the exact N41 rank, independent replay, and W15 transfer receipts."""

import csv
import hashlib
import json
from collections import defaultdict
from math import comb
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
INPUT = BASE / "n41_coupled_sixpair_full_ic_20261010/heldout_input.txt"
HELPER = BASE / "n131_w18_four_pairs/native_join/frozen_source/helper.cpp"
W15 = BASE / "n131_w15_cross_block_seed_offset_20261010"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((HERE / name).read_text())


def check_hashes(expected, paths):
    assert expected == {name: sha(path) for name, path in paths.items()}


def count_tsv(name):
    grouped = defaultdict(set)
    witnesses = defaultdict(int)
    with (HERE / name).open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            seed = int(row["seed"])
            grouped[seed].add(int(row["x"]))
            witnesses[seed] += 1
    return grouped, witnesses


def main():
    assert not (HERE / "terminal_audit.json").exists()
    protocol = read("protocol.json")
    check_hashes(protocol["source_sha256"], {
        "census.cpp": HERE / "census.cpp", "census": HERE / "census",
        "rank.py": HERE / "rank.py", "run.py": HERE / "run.py", "helper.cpp": HELPER})
    assert protocol["input_sha256"] == sha(INPUT)
    receipt = read("receipt.json")
    assert receipt["status"] == "CENSUS_AND_RANK_COMPLETE"
    assert receipt["protocol_sha256"] == sha(HERE / "protocol.json")
    check_hashes(receipt["outputs_sha256"], {name: HERE / name
                 for name in ("quad_outputs.tsv", "rank_result.json")})
    protocol_b = read("protocol_b.json")
    check_hashes(protocol_b["source_sha256"], {
        **{name: HERE / name for name in ("census_b.cpp", "census_b", "rank.py", "run_b.py")},
        "input": INPUT})
    receipt_b = read("receipt_b.json")
    assert receipt_b["status"] == "SECOND_BLOCK_CENSUS_AND_RANK_COMPLETE"
    assert receipt_b["protocol_sha256"] == sha(HERE / "protocol_b.json")
    check_hashes(receipt_b["outputs_sha256"], {name: HERE / name
                 for name in ("quad_outputs_b.tsv", "rank_b.json")})
    sage_protocol = read("sage_protocol.json")
    check_hashes(sage_protocol["sha256"], {
        "audit_sage.py": HERE / "audit_sage.py", "input": INPUT,
        "quad_outputs.tsv": HERE / "quad_outputs.tsv",
        "rank_result.json": HERE / "rank_result.json",
        "sage_runtime_info.json": HERE / "sage_runtime_info.json"})
    sage = read("sage_audit.json")
    assert sage["status"] == "PASS_INDEPENDENT_SAGE_QUAD_GROUP_AND_ALL_BIN_RANK"
    assert sage["protocol_sha256"] == sha(HERE / "sage_protocol.json")
    assert sage["sampled_witnesses"] == 100 and sage["all_bin_count"] == 63
    assert sage["extra_rank_defect_bins"] == 0
    rotation_protocol = read("rotation_protocol_v2.json")
    check_hashes(rotation_protocol["sha256"], {name: HERE / name for name in
                 ("quad_outputs.tsv", "quad_outputs_b.tsv", "rank_result.json",
                  "rank_b.json", "check_rotation.py")})
    rotation = read("rotation_audit.json")
    assert rotation["status"] == "PASS_ALL_N41_BLOCK_OUTPUT_FROBENIUS_AND_RANK"
    assert rotation["checked_four_atom_witnesses"] == 51840
    assert rotation["protocol_sha256"] == sha(HERE / "rotation_protocol_v2.json")
    failure = read("rotation_failure_v1.json")
    assert failure["status"] == "PRODUCER_FAILURE_UNSUPPORTED_ZIP_STRICT"
    assert failure["protocol_sha256"] == sha(HERE / "rotation_protocol_v1.json")
    for suffix, name in (("", "quad_outputs.tsv"), ("_b", "quad_outputs_b.tsv")):
        rank = read("rank_result.json" if not suffix else "rank_b.json")
        grouped, witnesses = count_tsv(name)
        assert set(grouped) == set(range(1, 64))
        assert sum(witnesses.values()) == rank["witness_rows"] == 51840
        assert sum(len(values) for values in grouped.values()) == 25920
        assert rank["bins_with_extra_rank_defect"] == 0
        for row in rank["bins"]:
            seed = row["seed"]
            assert len(grouped[seed]) == row["distinct_x"]
            assert witnesses[seed] == row["witness_rows"] == 2*len(grouped[seed])
            assert row["quadratic_rank"] == min(len(grouped[seed]), 821)
    transfer_protocol = read("transfer_protocol.json")
    check_hashes(transfer_protocol["source_sha256"], {
        "transfer.py": HERE / "transfer.py",
        "signed_seed_counts.tsv": W15 / "signed_seed_counts.tsv",
        "W15_terminal_audit.json": W15 / "terminal_audit.json",
        "N41_rank_result.json": HERE / "rank_result.json",
        "N41_rank_b.json": HERE / "rank_b.json",
        "N41_sage_audit.json": HERE / "sage_audit.json",
        "N41_rotation_audit.json": HERE / "rotation_audit.json"})
    transfer = read("transfer.json")
    assert transfer["protocol_sha256"] == sha(HERE / "transfer_protocol.json")
    counts = [int(line.split()[1]) for line in (W15 / "signed_seed_counts.tsv").read_text().splitlines()]
    assert len(counts) == transfer["seed_bins"] == 32767
    assert sum(counts) == transfer["signed_pair_states"] == 540579832
    assert min(c*c for c in counts) == transfer["same_seed_four_atom_tuples_per_seed_min_before_cross_column_exclusion"]
    assert max(c*c for c in counts) == transfer["same_seed_four_atom_tuples_per_seed_max_before_cross_column_exclusion"]
    for entry in transfer["optimistic_130_bit_feature_dimensions"]:
        features = sum(comb(130, j) for j in range(entry["degree"]+1))
        assert features == entry["feature_count"]
        assert ((features+7)//8)*16*32767 == entry["bytes_for_16_dense_equations_all_nonzero_seeds"]
    record = {"status": "PASS_N41_BOTH_BLOCKS_RANK_AND_W15_TRANSFER",
              "n41_witnesses_each_block": 51840, "n41_distinct_x_per_seed_sum_each_block": 25920,
              "n41_seed_bins": 63, "n41_extra_quadratic_rank_defect_bins": 0,
              "sage_replayed_witnesses": 100,
              "n131_signed_pair_states": 540579832,
              "degree3_fixed_table_bytes": 24003793520,
              "source_sha256": {name: sha(HERE / name) for name in
                                ("verify.py", "receipt.json", "receipt_b.json", "sage_audit.json",
                                 "rotation_audit.json", "transfer.json", "rank_result.json", "rank_b.json")}}
    with (HERE / "terminal_audit.json").open("x") as output:
        json.dump(record, output, sort_keys=True, indent=2)
        output.write("\n")
    print(record["status"])


if __name__ == "__main__":
    main()
