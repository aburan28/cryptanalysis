#!/usr/bin/env python3
"""Independent integer and source-binding check of adjacent support counts."""
import collections
import hashlib
import json
from decimal import Decimal, getcontext
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ORDER = 680564733841876926932320129493409985129
getcontext().prec = 45


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    audit_protocol = json.loads((HERE / "audit_protocol.json").read_text())
    assert audit_protocol["status"] == "FROZEN_BEFORE_AUDIT"
    paths = {"verify": HERE / "verify.py", "count": HERE / "count.py",
             "protocol": HERE / "protocol.json", "result": HERE / "result.json",
             "w14_support": ROOT / "n131_w14_ten_source_gate_20261009/support_w14.tsv",
             "w15_support": ROOT / "n131_w15_coupled_sixpair_20261010/support_w15.tsv",
             "w14_baseline": ROOT / "n41_upper_xor_projection_20261010/seed_sum_count.json",
             "w15_baseline": ROOT / "n131_w15_coupled_sixpair_20261010/seed_sum_count.json"}
    assert audit_protocol["source_sha256"] == {name: sha(path) for name, path in paths.items()}
    protocol = json.loads(paths["protocol"].read_text())
    result = json.loads(paths["result"].read_text())
    assert result["status"] == "PASS_EXACT_ADJACENT_SEED_SUPPORT"
    assert result["protocol_sha256"] == sha(paths["protocol"])
    assert result["wall_ns"] <= protocol["wall_cap_seconds"] * 10**9
    assert result["peak_rss_bytes"] <= protocol["rss_cap_bytes"]
    assert result["source_sha256"] == {key: sha(paths[key]) for key in protocol["source_sha256"]}
    baselines = {14: json.loads(paths["w14_baseline"].read_text())["n131"],
                 15: json.loads(paths["w15_baseline"].read_text())}
    for d in (14, 15):
        row = result[f"w{d}"]
        support = [tuple(map(int, line.split())) for line in
                   paths[f"w{d}_support"].read_text().splitlines()]
        labels = collections.Counter(column for _, column in support)
        assert len(support) == row["source_masks"]
        assert len(labels) == row["folded_columns_K"]
        assert row["seed_space_rank"] == d + d//2 + d%2
        same_column = sum(count**2 for count in labels.values())
        pairs = len(support)**2 - same_column
        assert same_column == row["same_column_excluded_ordered_pairs"]
        assert pairs == row["accepted_ordered_mask_pairs"]
        assert row["source_sha256"] == sha(paths[f"w{d}_support"])
        hist = row["seed_bucket_pair_count_histogram"]
        assert sum(hist) == 1 << row["seed_space_rank"]
        assert row["nonempty_seed_buckets"] == sum(hist[1:])
        assert row["maximum_mask_pairs_per_seed"] == len(hist)-1
        assert sum(i*count for i, count in enumerate(hist)) == pairs
        signed = 4*pairs
        block = 16*sum(i*i*count for i, count in enumerate(hist))
        assert signed == row["signed_pair_states_per_rotation"]
        assert block == row["same_seed_two_pair_states"]
        tuples = signed*signed*block*block
        assert str(tuples) == row["six_pair_tuple_count"]
        assert row["group_order"] == str(ORDER)
        assert row["group_wide_mean_before_cross_pair_columns"] == str(
            Decimal(tuples)/Decimal(ORDER))
        reference = int(baselines[d]["six_pair_tuple_count"])
        assert row["same_rotation_group_wide_mean"] == str(
            Decimal(reference)/Decimal(ORDER))
        assert row["adjacent_to_same_rotation_tuple_ratio"] == str(
            Decimal(tuples)/Decimal(reference))
        suffix = signed*block*block
        minimum = (ORDER+2*suffix-1)//(2*suffix)
        assert row["minimum_one_free_pair_prefixes_for_half_union_ceiling"] == minimum
        assert 2*minimum*suffix >= ORDER
        assert 2*(minimum-1)*suffix < ORDER
        assert row["necessary_average_microseconds_per_prefix_in_600s"] == str(
            Decimal(600_000_000)/Decimal(minimum))
    print(json.dumps({"status": "PASS_ADJACENT_SUPPORT_INTEGER_AUDIT",
                      "widths": [14, 15], "source_hashes_verified": True,
                      "histogram_identities_verified": True,
                      "prefix_minimality_verified": True}))


if __name__ == "__main__":
    main()
