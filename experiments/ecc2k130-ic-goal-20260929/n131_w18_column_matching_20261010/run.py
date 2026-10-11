"""Freeze-check and certify the W18 column matching on audited support."""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
BASE = GOAL / "n131_fixed_seed_eight_pair_circuit_20261010"
WIDTH = GOAL / "n131_w16_w18_sixpair_width_gate_20261010"
sys.path.insert(0, str(BASE))
from fixed_pair_circuit import SEED, ROTATIONS, valid_codes  # noqa: E402
import fixed_pair_circuit as pair  # noqa: E402
import matching  # noqa: E402


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    paths = {"run": HERE / "run.py", "matching": HERE / "matching.py",
             "pair": BASE / "fixed_pair_circuit.py",
             "support": WIDTH / "support_w18.tsv",
             "support_receipt": BASE / "support_result.json",
             "constructed": BASE / "derive_result.json"}
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["source_sha256"] == {name: digest(path) for name, path in paths.items()}
    assert SEED == 212 and len(ROTATIONS) == 8
    columns = {int(a): int(b) for a, b in
               (line.split() for line in paths["support"].read_text().splitlines())}
    support = json.loads(paths["support_receipt"].read_text())
    order = int(support["subgroup_order"])
    edge_map = matching.edges(pair, columns)
    chosen = matching.greedy_disjoint(edge_map)
    selected = set(chosen)
    used = [column for code in chosen for column in edge_map[code]]
    assert len(set(used)) == len(used) and len(edge_map) == 33191
    assert set(chosen).issubset(valid_codes(columns))
    fixture = json.loads(paths["constructed"].read_text())
    fixture_codes = [pair.selector_code(item["masks"][0]) for item in fixture["selected"]]
    assert len(fixture_codes) == 8 and len(set(fixture_codes)) == 8
    assert all(code in selected for code in fixture_codes)
    ordered_exact, sizes = matching.count_ordered_matchings(edge_map)
    lower = 1
    for i in range(8):
        lower *= len(chosen)-i
    lower_mean = matching.expectation(lower, order)
    exact_mean = matching.expectation(ordered_exact, order)
    upper_mean = matching.expectation(len(edge_map)**8, order)
    result = {"status": "PASS_EXACT_W18_EIGHT_PAIR_COLUMN_MATCHING",
              "curve_id": "EC1N131Ckb1heb5f1998f20b", "candidate_id": None,
              "seed_mask": SEED, "rotations": ROTATIONS,
              "valid_pair_codes": len(edge_map), "greedy_disjoint_codes": len(chosen),
              "greedy_removed_codes": len(edge_map)-len(chosen),
              "component_size_counts": sizes,
              "ordered_distinct_column_code_tuples_exact": str(ordered_exact),
              "ordered_disjoint_subset_code_tuples_lower": str(lower),
              "sign_assignments_per_code_tuple": 4**8,
              "subgroup_order": str(order),
              "uniform_target_mean_exact": str(exact_mean),
              "uniform_target_mean_lower": str(lower_mean),
              "uniform_target_mean_upper": str(upper_mean),
              "constructed_fixture_codes": fixture_codes,
              "constructed_fixture_retained": True,
              "source_sha256": protocol["source_sha256"],
              "protocol_sha256": digest(HERE / "protocol.json")}
    (HERE / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print(json.dumps({k: result[k] for k in ("status", "valid_pair_codes",
                                             "greedy_disjoint_codes",
                                             "component_size_counts",
                                             "uniform_target_mean_exact")}))


if __name__ == "__main__":
    main()
