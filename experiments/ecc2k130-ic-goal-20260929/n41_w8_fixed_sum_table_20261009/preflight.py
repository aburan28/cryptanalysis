#!/usr/bin/env python3
"""Audit finite pair domains and the sequential cardinality encoding."""

import hashlib
import itertools
import json
from pathlib import Path

import run
from karatsuba_circuit import KaratsubaCircuit

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def card_truth_table():
    circuit = KaratsubaCircuit(41, [0, 3])
    row = [circuit.variable() for _ in range(4)]
    aux_count = run.method.one_hot(circuit, row)
    aux = list(range(row[-1] + 1, circuit.next_var))
    if aux_count != 3 or len(aux) != 3:
        raise ValueError("sequential cardinality auxiliary count changed")
    clauses = [[int(item) for item in line.split()[:-1]]
               for line in circuit.clauses]
    checked = 0
    for bits in itertools.product((False, True), repeat=4):
        exists = False
        for extra in itertools.product((False, True), repeat=3):
            values = {i: v for i, v in enumerate(bits + extra, 1)}
            if all(any(values[abs(lit)] == (lit > 0) for lit in clause)
                   for clause in clauses):
                exists = True
        if exists != (sum(bits) == 1):
            raise ValueError("sequential one-hot truth table failed")
        checked += 1
    return checked


def main():
    output = HERE / "preflight.json"
    if output.exists():
        raise FileExistsError(output)
    geometry = json.loads((HERE / "geometry.json").read_text())
    field = run.base.Field(41, [0, 3])
    curve = run.base.Curve(field, 0)
    q, raw, target_us = run.target_data(field, curve, geometry, "control")
    domain_sizes = []
    for block in geometry["blocks"][:6]:
        domain = run.method.descriptors(block)
        keys = {(entry["a"], entry["z"]) for entry in domain}
        if (len(domain) != 80 or
                any((state["a"], state["z"]) not in keys
                    for state in block["states"])):
            raise ValueError("table does not cover the exact signed pair states")
        domain_sizes.append(len(domain))
    card_patterns = card_truth_table()
    circuit = KaratsubaCircuit(41, [0, 3])
    wires = run.method.build(circuit, geometry, target_us)
    pins = run.control_pins(circuit, wires, geometry, raw)
    result = {"status": "PASS_EXACT_TABLE_PREFLIGHT",
              "proposal_id": run.PROPOSAL_ID, "candidate_id": None,
              "target_q": q, "pair_descriptors_per_block": domain_sizes,
              "signed_states_per_block": [160]*6,
              "cardinality_input_patterns_checked": card_patterns,
              "variables": circuit.next_var - 1,
              "cnf_clauses": len(circuit.clauses),
              "xor_rows": len(circuit.xors),
              "and_gates": circuit.and_count,
              "primary_variables": wires["primary_variables"],
              "onehot_auxiliary_variables": wires["onehot_auxiliary_variables"],
              "duplicate_column_clauses": wires["duplicate_column_clauses"],
              "saved_witness_target_flag": pins["target_flag"],
              "source_sha256": {name: sha(HERE / name) for name in
                                ("preflight.py", "circuit.py", "run.py", "geometry.json")}}
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in
                      ("status", "pair_descriptors_per_block",
                       "cardinality_input_patterns_checked", "variables",
                       "cnf_clauses", "xor_rows", "and_gates")}, sort_keys=True))


if __name__ == "__main__":
    main()
