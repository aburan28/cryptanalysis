"""Compile the matched-source and eight-slot uniqueness gate without the arithmetic core."""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
BASE = GOAL / "n131_fixed_seed_eight_pair_circuit_20261010"
POSITIVE = GOAL / "n131_w18_positive_bdd_20261010"
WIDTH = GOAL / "n131_w16_w18_sixpair_width_gate_20261010"
ROOT = HERE.parents[2]
sys.path[:0] = [str(BASE), str(POSITIVE), str(ROOT / "ecc2k130/codegen")]
import cnf  # noqa: E402
import fixed_pair_circuit as pair  # noqa: E402
import matching  # noqa: E402
from positive_bdd import check_positive_gate, emit_positive_bdd  # noqa: E402


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def selectors(circuit):
    return [[circuit.newVar() for _ in pair.SOURCE_BITS] for _ in pair.ROTATIONS]


def main():
    paths = {"script": HERE / "compile_gate.py", "matching": HERE / "matching.py",
             "pair": BASE / "fixed_pair_circuit.py",
             "positive_bdd": POSITIVE / "positive_bdd.py",
             "cnf": ROOT / "ecc2k130/codegen/cnf.py",
             "support": WIDTH / "support_w18.tsv",
             "constructed": BASE / "derive_result.json"}
    protocol = json.loads((HERE / "compile_protocol.json").read_text())
    assert protocol["source_sha256"] == {name: digest(path) for name, path in paths.items()}
    check_positive_gate()
    columns = {int(a): int(b) for a, b in
               (line.split() for line in paths["support"].read_text().splitlines())}
    edge_map = matching.edges(pair, columns)
    chosen = matching.greedy_disjoint(edge_map)
    chosen_set = set(chosen)
    root, nodes = pair.build_bdd(chosen)
    assert all(pair.bdd_accepts(root, nodes, code) == (code in chosen_set)
               for code in range(1 << len(pair.SOURCE_BITS)))
    fixture = json.loads(paths["constructed"].read_text())
    codes = [pair.selector_code(item["masks"][0]) for item in fixture["selected"]]
    assert len(codes) == len(set(codes)) == len(pair.ROTATIONS)
    assert all(pair.bdd_accepts(root, nodes, code) for code in codes)
    assert len(set(edge_map[codes[0]] + edge_map[codes[1]])) == 4
    baseline = cnf.Cnf()
    baseline_selectors = selectors(baseline)
    original_root, original_nodes = pair.build_bdd(edge_map)
    for slot in baseline_selectors:
        emit_positive_bdd(baseline, original_root, original_nodes, slot)
    matched = cnf.Cnf()
    gate = matching.emit_matching_gate(matched, pair, columns,
                                       selectors(matched), emit_positive_bdd)
    assert gate["admissible_pair_codes"] == len(chosen)
    assert gate["code_disequalities"] == 28
    result = {"status": "PASS_MATCHED_SOURCE_XCNF_GATE_BUILD",
              "candidate_id": None, "curve_id": "EC1N131Ckb1heb5f1998f20b",
              "ordinary_source_gate_stats": baseline.stats(),
              "matched_distinct_source_gate_stats": matched.stats(),
              "matched_gate": gate, "fixture_codes": codes,
              "source_sha256": protocol["source_sha256"],
              "protocol_sha256": digest(HERE / "compile_protocol.json")}
    (HERE / "compile_result.json").write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print(json.dumps({"status": result["status"],
                      "ordinary_source_gate_stats": result["ordinary_source_gate_stats"],
                      "matched_distinct_source_gate_stats": result["matched_distinct_source_gate_stats"]}))


if __name__ == "__main__":
    main()
