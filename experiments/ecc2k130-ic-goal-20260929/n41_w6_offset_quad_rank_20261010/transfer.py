"""Exact W15 source-tuple and fixed interpolation-table arithmetic."""

import hashlib
import json
from math import comb
from pathlib import Path

HERE = Path(__file__).resolve().parent
W15 = HERE.parent / "n131_w15_cross_block_seed_offset_20261010"
COUNTS = W15 / "signed_seed_counts.tsv"
REFERENCE = W15 / "terminal_audit.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path, record):
    with path.open("x") as output:
        json.dump(record, output, sort_keys=True, indent=2)
        output.write("\n")


def main():
    sources = {"transfer.py": sha(Path(__file__)),
               "signed_seed_counts.tsv": sha(COUNTS),
               "W15_terminal_audit.json": sha(REFERENCE),
               "N41_rank_result.json": sha(HERE / "rank_result.json"),
               "N41_rank_b.json": sha(HERE / "rank_b.json"),
               "N41_sage_audit.json": sha(HERE / "sage_audit.json"),
               "N41_rotation_audit.json": sha(HERE / "rotation_audit.json")}
    write_new(HERE / "transfer_protocol.json", {
        "status": "FROZEN_BEFORE_W15_TRANSFER_ARITHMETIC",
        "source_sha256": sources,
        "scope": "source tuple counts and explicit fixed 16-equation interpolation-table memory only",
        "coordinate_chart": "optimistic 130 Boolean x-coordinate variables, omitting one of 131 field bits; no N131 chart reduction is asserted",
    })
    parsed = [tuple(map(int, line.split())) for line in COUNTS.read_text().splitlines()]
    assert len(parsed) == 32767 and [seed for seed, _ in parsed] == list(range(1, 32768))
    counts = [count for _, count in parsed]
    assert sum(counts) == 540579832
    assert json.loads(REFERENCE.read_text())["status"] == "PASS_W15_OFFSET_SUPPORT_AND_N41_PUBLIC_RELATION"
    n41_a = json.loads((HERE / "rank_result.json").read_text())
    n41_b = json.loads((HERE / "rank_b.json").read_text())
    assert n41_a["bins_with_extra_rank_defect"] == n41_b["bins_with_extra_rank_defect"] == 0
    tuple_counts = [count*count for count in counts]
    features = []
    for degree in range(1, 6):
        dimension = sum(comb(130, j) for j in range(degree+1))
        bytes_per_equation = (dimension+7)//8
        bytes_all_seed_bins_16 = bytes_per_equation*16*32767
        features.append({"degree": degree, "feature_count": dimension,
                         "bytes_per_dense_equation": bytes_per_equation,
                         "bytes_for_16_dense_equations_all_nonzero_seeds": bytes_all_seed_bins_16,
                         "ratio_to_4gib": str(bytes_all_seed_bins_16 / (4*1024**3))})
    record = {
        "status": "EXACT_W15_SOURCE_TUPLE_AND_FIXED_TABLE_ARITHMETIC",
        "protocol_sha256": sha(HERE / "transfer_protocol.json"),
        "seed_bins": len(counts), "signed_pair_states": sum(counts),
        "signed_pair_states_per_seed_min": min(counts),
        "signed_pair_states_per_seed_max": max(counts),
        "same_seed_four_atom_tuples_per_seed_min_before_cross_column_exclusion": min(tuple_counts),
        "same_seed_four_atom_tuples_per_seed_max_before_cross_column_exclusion": max(tuple_counts),
        "feature_table_model": "16 dense Boolean equations per nonzero seed; coefficient bits only; ignores indices, construction, target work, and four-point membership",
        "optimistic_130_bit_feature_dimensions": features,
        "n41_extra_quadratic_rank_defect_bins_in_each_block": 0,
    }
    write_new(HERE / "transfer.json", record)
    print({k: v for k, v in record.items() if k != "optimistic_130_bit_feature_dimensions"})


if __name__ == "__main__":
    main()
