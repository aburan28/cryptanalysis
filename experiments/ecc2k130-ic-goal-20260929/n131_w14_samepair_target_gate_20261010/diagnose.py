#!/usr/bin/env python3
"""Locate the first failing full-formula clause on the frozen group control."""
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("samepair_diagnostic_driver", HERE / "run.py")
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)

protocol = json.loads((HERE / "protocol.json").read_text())
control = json.loads((HERE / "control.json").read_text())
_, _, columns, field, curve, source_w, source_u = run.source()
leaves = [tuple(row) for row in control["raw_leaves"]]
middle, total = run.chain(curve, leaves)
assert list(total) == control["raw_sum"]
target = run.target_preimages(curve, tuple(control["target_q"]))
target_us = [run.transformed(field, point) for point in target]
circuit = run.old.old.base.KaratsubaCircuit(131, run.LOW_TERMS)
meta = run.method.build(circuit, field, source_w, source_u,
                        protocol["rotations"], columns, columns, target_us)
initial = {}
for row, mask in zip(meta["masks"], control["masks"]):
    initial.update({wire: mask >> i & 1 for i, wire in enumerate(row)})
for i, wire in enumerate(meta["flags"]):
    initial[wire] = int(i == control["target_preimage_index"])
for row, value in zip(meta["middle"], control["middle_u"]):
    initial.update({wire: value >> i & 1 for i, wire in enumerate(row)})
assignment = run.old.old.witness_tools.complete_assignment(circuit, initial)
failed = []
for i, clause in enumerate(circuit.clauses):
    literals = [int(word) for word in clause.split()[:-1]]
    if not any(assignment[abs(v)] == (v > 0) for v in literals):
        failed.append({"index": i, "clause": clause})
        if len(failed) == 10:
            break


def a(value):
    return field.mul(value, value) ^ value


def s3(left, right, z):
    left, right, z = [run.transformed(field, point)
                      for point in (left, right, z)]
    return field.mul(field.mul(a(left), a(right)), a(z)) == \
        field.mul(left ^ right ^ z, left ^ right ^ z)


links = []
for i in range(5):
    links.append({"pair": i, "numeric_s3": s3(leaves[2*i], leaves[2*i+1], middle[i]),
                  "sum_matches": curve.add(leaves[2*i], leaves[2*i+1]) == middle[i],
                  "masks": control["masks"][2*i:2*i+2],
                  "canonical": control["folded_columns"][2*i:2*i+2]})
print(json.dumps({"failed_clauses": failed, "numeric_leaf_links": links,
                  "clauses": len(circuit.clauses),
                  "duplicate_column_clauses": meta["duplicate_column_clauses"]},
                 indent=2, sort_keys=True))
