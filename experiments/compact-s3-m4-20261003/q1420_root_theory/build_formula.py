#!/usr/bin/env python3
"""Build balanced m4 CNF with pair S3 constraints delegated to a root oracle."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = PARENT.parents[1]
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(PARENT / "q1419_partial_pin"))

from chain_s3 import Formula, field, multiplication_table, square_destinations  # noqa: E402
from chain_s3_factored import s3_link_factored  # noqa: E402
from chain_s3_multitarget import choose_target_x  # noqa: E402
from run_cell import pin_bits, read_profile  # noqa: E402
from run_probe import sha  # noqa: E402

CONTROL_PROTOCOL = PARENT / "q1419_partial_pin/protocol.json"
ORDINARY_PARENT = {
    53: PARENT / "runs/n53_q1410_ordinary.json",
    83: PARENT / "runs/n83_q1408_ordinary.json",
}


def build(n: int, kind: str, cell: str):
    protocol = json.loads(CONTROL_PROTOCOL.read_text())
    profile, control_parent, fixture = read_profile(protocol, n)
    parent_path = (Path(profile["parent_receipt"]["path"])
                   if kind == "control" else ORDINARY_PARENT[n])
    if not parent_path.is_absolute():
        parent_path = ROOT / parent_path
    parent = (control_parent if kind == "control" else
              json.loads(parent_path.read_text()))
    assert parent["curve_id"] == profile["curve_id"]
    assert parent["factor_base_actual_B"] == profile[
        "factor_base_actual_B"]
    assert parent["factor_base_folded_columns"] == profile["folded_columns_K"]
    assert parent["factor_base_enumerated_set_sha256"] == profile[
        "factor_base_enumerated_set_sha256"]
    raw_targets = parent["raw_preimage_x_coordinates"]
    assert raw_targets and len(set(raw_targets)) == len(raw_targets)
    onb = field.Onb(n)
    formula = Formula()
    leaves = [[formula.new() for _ in range(n)] for _ in range(4)]
    mids = [[formula.new() for _ in range(n)] for _ in range(2)]
    for leaf in leaves:
        formula.at_most(leaf, profile["normal_basis_weight_bound"])
        formula.clauses.append(leaf[:])
    target, selector = choose_target_x(formula, n, raw_targets)
    # The sole symbolic S3 link connects the pair roots to the target. The
    # first two links are enforced by the external CaDiCaL propagator.
    s3_link_factored(formula, mids[0], mids[1], target,
                     multiplication_table(onb), square_destinations(onb))
    if kind == "control":
        assert cell in ("full_lock", "free_mids")
        data = fixture["fixture"]
        for bits, value in zip(leaves, data["raw_leaf_x"]):
            pin_bits(formula, bits, value)
        selected_x = onb.toCoords(int(data["raw_sum"][0]))
        choice = raw_targets.index(selected_x)
        pin_bits(formula, selector, choice)
        if cell == "full_lock":
            for bits, point in zip(mids, data["raw_pair_sum_points"]):
                pin_bits(formula, bits, onb.toCoords(int(point[0])))
    else:
        assert cell == "ordinary"
    meta = {
        "proposal_id": "Q1420", "candidate_id": None,
        "curve_id": profile["curve_id"], "isogeny": "none",
        "degree_n": n, "kind": kind, "cell": cell,
        "factor_base_actual_B": profile["factor_base_actual_B"],
        "folded_columns_K": profile["folded_columns_K"],
        "factor_base_enumerated_set_sha256": profile[
            "factor_base_enumerated_set_sha256"],
        "public_target": parent["public_target"],
        "target_preimage_x_count": len(raw_targets),
        "normal_basis_weight_bound": profile["normal_basis_weight_bound"],
        "leaf_variables": leaves, "pair_mid_variables": mids,
        "target_selector_variables": selector,
        "parent_receipt_sha256": sha(parent_path),
        "q1419_control_protocol_sha256": sha(CONTROL_PROTOCOL),
        "field_bridge_export_sha256": sha(HERE / f"n{n}_field.txt"),
        "original_formula_variables": formula.variables,
        "original_formula_cnf_clauses": len(formula.clauses),
        "original_formula_xor_rows": len(formula.xors),
        "input_law": ("known-satisfiable archived witness control"
                      if kind == "control" else
                      "one archived ordinary public target; no witness pins"),
        "natural_relation_yield_estimate": None,
        "complete_solve_work_log2": None,
    }
    return formula, meta


def emit_xor_gate(output, a, b):
    yield (-a, -b, -output)
    yield (a, b, -output)
    yield (a, -b, output)
    yield (-a, b, output)


def emit_xor_equation(a, b, rhs):
    if rhs:
        yield (a, b)
        yield (-a, -b)
    else:
        yield (a, -b)
        yield (-a, b)


def convert_to_cnf(formula):
    variables = formula.variables
    clauses = list(formula.clauses)
    for row, rhs in formula.xors:
        assert len(row) >= 2 and all(bit > 0 for bit in row)
        acc = row[0]
        for bit in row[1:-1]:
            variables += 1
            clauses.extend(emit_xor_gate(variables, acc, bit))
            acc = variables
        clauses.extend(emit_xor_equation(acc, row[-1], rhs))
    return variables, clauses


def write_artifacts(formula, meta, output: Path):
    variables, clauses = convert_to_cnf(formula)
    meta["cnf_variables"] = variables
    meta["cnf_clauses"] = len(clauses)
    assert not output.exists()
    output.mkdir(parents=True)
    cnf = output / "system.cnf"
    digest = hashlib.sha256()
    with cnf.open("wb") as stream:
        def write(line):
            encoded = line.encode("ascii")
            stream.write(encoded)
            digest.update(encoded)
        write(f"p cnf {variables} {len(clauses)}\n")
        for clause in clauses:
            write(" ".join(map(str, clause)) + " 0\n")
    meta["cnf_sha256"] = digest.hexdigest()
    meta["cnf_bytes"] = cnf.stat().st_size
    map_path = output / "variables.txt"
    with map_path.open("w") as stream:
        stream.write(f"Q1420MAP1 {meta['degree_n']} "
                     f"{meta['normal_basis_weight_bound']}\n")
        for bits in meta["leaf_variables"]:
            stream.write(" ".join(map(str, bits)) + "\n")
        for bits in meta["pair_mid_variables"]:
            stream.write(" ".join(map(str, bits)) + "\n")
        stream.write(str(len(meta["target_selector_variables"])) + " " +
                     " ".join(map(str, meta["target_selector_variables"])) +
                     "\n")
    meta["variable_map_sha256"] = sha(map_path)
    (output / "meta.json").write_text(json.dumps(meta, indent=2,
                                                  sort_keys=True) + "\n")
    return variables, len(clauses)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--degree", type=int, choices=(53, 83), required=True)
    parser.add_argument("--kind", choices=("control", "ordinary"), required=True)
    parser.add_argument("--cell", choices=("full_lock", "free_mids", "ordinary"),
                        required=True)
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    formula, meta = build(args.degree, args.kind, args.cell)
    if args.preflight:
        variables, clauses = convert_to_cnf(formula)
        print(json.dumps({"status": "PREFLIGHT", "degree": args.degree,
                          "kind": args.kind, "cell": args.cell,
                          "original_variables": formula.variables,
                          "original_xor_rows": len(formula.xors),
                          "cnf_variables": variables,
                          "cnf_clauses": len(clauses)}))
        return
    output = HERE / "build" / f"n{args.degree}_{args.cell}"
    variables, clauses = write_artifacts(formula, meta, output)
    print(json.dumps({"output": str(output), "cnf_variables": variables,
                      "cnf_clauses": clauses,
                      "cnf_sha256": meta["cnf_sha256"]}))


if __name__ == "__main__":
    main()
