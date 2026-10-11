"""Independent integer recount of W16 support and prefix-cut bounds."""

import collections
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
WIDTH = HERE.parent / "n131_w16_w18_sixpair_width_gate_20261010"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def walsh(values):
    size = len(values)
    step = 1
    while step < size:
        for base in range(0, size, 2*step):
            for offset in range(step):
                a, b = values[base+offset], values[base+offset+step]
                values[base+offset] = a+b
                values[base+offset+step] = a-b
        step *= 2
    return values


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    result = json.loads((HERE / "result.json").read_text())
    support = WIDTH / "support_w16.tsv"
    assert protocol["source_sha256"]["support"] == sha(support)
    rows = [tuple(map(int, line.split())) for line in support.read_text().splitlines()]
    assert len(rows) == 32796 and len({mask for mask, _ in rows}) == len(rows)
    indicator = [0] * (1 << 16)
    by_column = collections.defaultdict(list)
    for mask, column in rows:
        assert 0 < mask < len(indicator)
        indicator[mask] = 1
        by_column[column].append(mask)
    spectrum = walsh(indicator)
    correlation = walsh([value*value for value in spectrum])
    assert all(value % len(indicator) == 0 for value in correlation)
    signed = [2*(value // len(indicator)) for value in correlation]
    signed[0] = 0
    same_column_pairs = 0
    for masks in by_column.values():
        for index, a in enumerate(masks):
            for b in masks[index+1:]:
                signed[a ^ b] -= 4
                same_column_pairs += 1
    assert min(signed) >= 0
    n = sum(signed)
    m = sum(value*value for value in signed)
    h = max(signed[1:])
    assert (n, m, h) == (result["source_counts"]["signed_pair_states_N"],
                         result["source_counts"]["same_seed_two_pair_states_M"],
                         result["source_counts"]["maximum_nonzero_seed_states"])
    assert n//4 == len(rows)*(len(rows)-1)//2 - same_column_pairs
    order = int(result["subgroup_order"])
    capacities = {
        "one_free_pair": n*m*m,
        "one_constrained_pair": n*n*m*h,
        "two_free_pairs": m*m,
        "one_free_one_constrained_pair": n*m*h,
        "two_pairs_same_constrained_block": n*n*m,
        "one_pair_each_constrained_block": n*n*h*h,
    }
    assert len(capacities) == len(result["rows"])
    for row in result["rows"]:
        capacity = capacities[row["cut"]]
        assert capacity == int(row["remaining_labeled_tuple_ceiling"])
        assert row["one_prefix_uniform_target_support_ceiling"] == {
            "numerator": str(min(capacity, order)), "denominator": str(order)}
        t = int(row["minimum_target_independent_prefixes_for_half_union_ceiling"])
        assert 2*t*capacity >= order and 2*(t-1)*capacity < order
        assert row["necessary_average_prefixes_per_second_for_600s"] == {
            "numerator": str(t), "denominator": "600"}
    assert result["source_sha256"] == protocol["source_sha256"]
    assert result["protocol_sha256"] == sha(HERE / "protocol.json")
    audit = {"status": "PASS_INDEPENDENT_W16_SUPPORT_RECOUNT_AND_CUT_BOUNDS",
             "rational_masks": len(rows), "folded_columns": len(by_column),
             "same_column_unordered_pairs": same_column_pairs,
             "signed_pair_states_N": n,
             "same_seed_two_pair_states_M": m,
             "maximum_nonzero_seed_states": h,
             "cut_count": len(capacities),
             "source_sha256": {"verify": sha(HERE / "verify.py"),
                               "support": sha(support),
                               "protocol": sha(HERE / "protocol.json"),
                               "result": sha(HERE / "result.json")}}
    with (HERE / "audit.json").open("x") as stream:
        json.dump(audit, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": audit["status"], "N": n, "M": m,
                      "maximum_seed": h}))


if __name__ == "__main__":
    main()
