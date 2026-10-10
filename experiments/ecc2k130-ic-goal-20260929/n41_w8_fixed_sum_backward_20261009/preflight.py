#!/usr/bin/env python3
"""Audit exact target residuals and the saved N41 relation before timing."""

import hashlib
import itertools
import json
from pathlib import Path

import run
from karatsuba_circuit import KaratsubaCircuit

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def cardinality_patterns():
    circuit = KaratsubaCircuit(41, [0, 3])
    row = [circuit.variable() for _ in range(4)]
    if run.method.one_hot(circuit, row) != 3:
        raise ValueError("sequential one-hot auxiliary count changed")
    clauses = [[int(word) for word in line.split()[:-1]]
               for line in circuit.clauses]
    for bits in itertools.product((False, True), repeat=4):
        sat = False
        for extra in itertools.product((False, True), repeat=3):
            values = dict(enumerate(bits + extra, 1))
            sat |= all(any(values[abs(lit)] == (lit > 0)
                           for lit in clause) for clause in clauses)
        if sat != (sum(bits) == 1):
            raise ValueError("sequential one-hot truth table failed")
    return 16


def main():
    output = HERE / "preflight.json"
    if output.exists():
        raise FileExistsError(output)
    geometry = json.loads((HERE / "geometry.json").read_text())
    field = run.base.Field(41, [0, 3])
    curve = run.base.Curve(field, 0)
    q, raw, _ = run.target_data(field, curve, geometry, "control")
    reach = run.backward.build(field, curve, geometry, q, raw)
    if len(reach) != 640 or len({entry["w_phi"] for entry in reach}) != 640:
        raise ValueError("target residual coordinate domain changed")
    circuit = KaratsubaCircuit(41, [0, 3])
    wires = run.method.build(circuit, geometry, reach)
    pins = run.control_pins(circuit, wires, geometry, raw)
    result = {"status": "PASS_TARGET_BACKWARD_PREFLIGHT",
              "proposal_id": run.PROPOSAL_ID, "candidate_id": None,
              "target_q": q, "raw_preimages": len(raw),
              "signed_last_pair_states": len(geometry["blocks"][5]["states"]),
              "exact_residual_entries": len(reach),
              "unique_residual_phi_coordinates": len({e["w_phi"] for e in reach}),
              "uniform_field_membership_upper_bound_numerator": len(reach),
              "uniform_field_membership_upper_bound_denominator": 2**41,
              "onehot_patterns_checked": cardinality_patterns(),
              "saved_witness_reachability_index": pins["reachability_index"],
              "variables": circuit.next_var - 1,
              "cnf_clauses": len(circuit.clauses),
              "xor_rows": len(circuit.xors),
              "and_gates": circuit.and_count,
              "primary_variables": wires["primary_variables"],
              "onehot_auxiliary_variables": wires["onehot_auxiliary_variables"],
              "duplicate_column_clauses": wires["duplicate_column_clauses"],
              "source_sha256": {name: sha(HERE / name) for name in
                                ("preflight.py", "reachability.py", "circuit.py",
                                 "run.py", "geometry.json")}}
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in
                      ("status", "exact_residual_entries",
                       "saved_witness_reachability_index",
                       "variables", "cnf_clauses", "xor_rows", "and_gates")},
                     sort_keys=True))


if __name__ == "__main__":
    main()
