"""Exact uniform-target support ceilings for W16 pair-prefix cuts."""

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
WIDTH = HERE.parent / "n131_w16_w18_sixpair_width_gate_20261010"
ORDER = 680564733841876926932320129493409985129


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, row):
    with Path(path).open("x") as stream:
        json.dump(row, stream, indent=2, sort_keys=True)
        stream.write("\n")


def source():
    result = json.loads((WIDTH / "result.json").read_text())
    assert result["status"] == "PASS_N131_W15_W18_WIDTH_GATE"
    assert result["curve_id"] == "EC1N131Ckb1heb5f1998f20b"
    width = next(row for row in result["widths"] if row["degree"] == 16)
    n = width["signed_pair_states_N"]
    m = width["same_seed_two_pair_states_M"]
    h = width["maximum_nonzero_seed_states"]
    assert width["six_pair_tuple_ceiling"] == str(n*n*m*m)
    assert width["minimum_one_free_pair_prefixes_for_half_union_ceiling"] == 32
    assert width["support_sha256"] == sha(WIDTH / "support_w16.tsv")
    return width, n, m, h


def freeze():
    width, n, m, h = source()
    row = {"status": "FROZEN_BEFORE_W16_PREFIX_CUT_ARITHMETIC",
           "candidate_id": None, "curve_id": "EC1N131Ckb1heb5f1998f20b",
           "target_law": "uniform point in the prime-order subgroup",
           "target_count": 0, "subgroup_order": str(ORDER),
           "wall_budget_seconds": 600,
           "source_policy": "six W16 signed pair slots; two free pairs and two same-seed two-pair blocks",
           "source_sha256": {"compute": sha(HERE / "compute.py"),
                             "width_result": sha(WIDTH / "result.json"),
                             "width_count": sha(WIDTH / "count.py"),
                             "support": sha(WIDTH / "support_w16.tsv")}}
    save(HERE / "protocol.json", row)
    print(json.dumps({"status": row["status"], "N": n, "M": m, "max_seed": h}))


def run():
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_W16_PREFIX_CUT_ARITHMETIC"
    assert protocol["source_sha256"] == {
        "compute": sha(HERE / "compute.py"),
        "width_result": sha(WIDTH / "result.json"),
        "width_count": sha(WIDTH / "count.py"),
        "support": sha(WIDTH / "support_w16.tsv")}
    width, n, m, h = source()
    # For a pair fixed in a same-seed block, at most h choices remain for
    # its matching partner.  Cross-block column filtering can only shrink
    # these counts.  All prefixes here are chosen without the target.
    cases = {
        "one_free_pair": n*m*m,
        "one_constrained_pair": n*n*m*h,
        "two_free_pairs": m*m,
        "one_free_one_constrained_pair": n*m*h,
        "two_pairs_same_constrained_block": n*n*m,
        "one_pair_each_constrained_block": n*n*h*h,
    }
    rows = []
    for name, remaining in cases.items():
        minimum = (ORDER + 2*remaining - 1) // (2*remaining)
        rows.append({"cut": name,
                     "remaining_labeled_tuple_ceiling": str(remaining),
                     "one_prefix_uniform_target_support_ceiling": {
                         "numerator": str(min(remaining, ORDER)),
                         "denominator": str(ORDER)},
                     "minimum_target_independent_prefixes_for_half_union_ceiling": str(minimum),
                     "necessary_average_prefixes_per_second_for_600s": {
                         "numerator": str(minimum), "denominator": "600"}})
    assert rows[0]["minimum_target_independent_prefixes_for_half_union_ceiling"] == "32"
    result = {"status": "PASS_EXACT_W16_PAIR_PREFIX_CUT_CEILINGS",
              "candidate_id": None, "curve_id": protocol["curve_id"],
              "target_count": 0, "target_law": protocol["target_law"],
              "subgroup_order": str(ORDER),
              "source_counts": {"signed_pair_states_N": n,
                                "same_seed_two_pair_states_M": m,
                                "maximum_nonzero_seed_states": h,
                                "six_pair_labeled_tuple_ceiling": str(n*n*m*m)},
              "rows": rows,
              "scope": "uniform-target union bound for a fixed list of complete pair prefixes selected independently of the target; labeled tuple counts ignore cross-slot column collisions and group-sum collisions",
              "source_sha256": protocol["source_sha256"],
              "protocol_sha256": sha(HERE / "protocol.json")}
    save(HERE / "result.json", result)
    print(json.dumps({"status": result["status"],
                      "two_same_block_half_prefixes": rows[4]["minimum_target_independent_prefixes_for_half_union_ceiling"],
                      "two_free_half_prefixes": rows[2]["minimum_target_independent_prefixes_for_half_union_ceiling"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "run"))
    {"freeze": freeze, "run": run}[parser.parse_args().mode]()
