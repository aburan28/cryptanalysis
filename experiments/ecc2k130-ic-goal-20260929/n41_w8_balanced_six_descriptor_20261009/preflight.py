#!/usr/bin/env python3
"""Check exact six-pair descriptors and known public witness before freezing."""

import json
from pathlib import Path

import run

HERE = Path(__file__).resolve().parent


def main():
    output = HERE / "preflight.json"
    if output.exists():
        raise FileExistsError("preserve first preflight")
    geometry = json.loads(run.GEOMETRY.read_text())
    field = run.base.Field(41, [0, 3])
    curve = run.base.Curve(field, 0)
    q, raw_targets, target_us = run.target_data(field, curve, geometry, "public")
    circuit = run.KaratsubaCircuit(41, [0, 3])
    wires = run.method.build(circuit, geometry, target_us)
    before = {"variables": circuit.next_var-1,
              "cnf_clauses": len(circuit.clauses),
              "native_xor_rows": len(circuit.xors),
              "and_gates": circuit.and_count}
    pins = run.control_pins(circuit, wires, geometry, raw_targets)
    witness = json.loads(run.WITNESS.read_text())["witness"]
    states = [geometry["blocks"][block]["states"][index]
              for block, index in enumerate(witness)]
    columns = [column for state in states for column in state["columns"]]
    if (len(witness) != 6 or len(set(columns)) != 12 or
            len(wires["descriptors"]) != 6 or
            any(len(domain) != 80 for domain in wires["descriptors"]) or
            len(wires["middle_wires"]) != 4 or
            len(raw_targets) != 4):
        raise ValueError("frozen six-block control geometry changed")
    record = {"status": "PASS_BALANCED_SIX_PREFLIGHT",
              "proposal_id": run.PROPOSAL_ID, "candidate_id": None,
              "curve_id": geometry["curve_id"], "target_q": list(q),
              "saved_witness_indices": witness,
              "saved_witness_columns": columns,
              "target_flag": pins["target_flag"],
              "descriptor_indices": pins["descriptor_indices"],
              "unpinned_formula_counts": before,
              "pinned_formula_counts": {
                  "variables": circuit.next_var-1,
                  "cnf_clauses": len(circuit.clauses),
                  "native_xor_rows": len(circuit.xors),
                  "and_gates": circuit.and_count},
              "source_sha256": {name: run.sha(path) for name, path in
                                (("circuit.py", HERE / "circuit.py"),
                                 ("run.py", HERE / "run.py"),
                                 ("geometry.json", run.GEOMETRY),
                                 ("saved_public_relation.json", run.WITNESS))}}
    output.write_text(json.dumps(record, indent=2, sort_keys=True)+"\n")
    print(json.dumps({"status": record["status"],
                      "unpinned_formula_counts": before,
                      "target_flag": pins["target_flag"]}, sort_keys=True))


if __name__ == "__main__":
    main()
