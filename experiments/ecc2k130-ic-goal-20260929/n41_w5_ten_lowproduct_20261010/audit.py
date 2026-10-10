#!/usr/bin/env python3
"""Compare sparse-W first-pair links on the frozen N41 public relation."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
GATE = PARENT / "n41_w5_ten_source_gate_20261010"
JOIN = PARENT / "n41_w5_ten_native_join_20261010"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = load("n41_w5_ten_gate", GATE / "run.py")
method = load("n41_w5_ten_lowproduct", HERE / "circuit.py")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(frame=False):
    context = gate.setup()
    field = context["field"]
    geometry = context["geometry"]
    rotations = geometry["rotations"]
    bases_w = [[gate.old.frob(field, w, rotation)
                for w in geometry["source_basis_w"]]
               for rotation in rotations]
    bases_u = geometry["bases_u"]
    for basis_w, basis_u in zip(bases_w, bases_u):
        for w, u in zip(basis_w, basis_u):
            assert field.mul(u, u) ^ u == w

    hit = json.loads((JOIN / "run/hits.jsonl").read_text().splitlines()[0])
    sage = json.loads((JOIN / "sage_hit_audit.json").read_text())
    assert sage["status"] == "PASS_INDEPENDENT_SAGE_PUBLIC_GROUP_REPLAY"
    public = json.loads((GATE / "public/result.json").read_text())
    qprime = tuple(public["transported_target_qprime"])
    targets = gate.old.base.target_preimages(field, context["curve"], qprime)
    target_us = [gate.old.transformed(field, point) for point in targets]
    circuit = gate.old.base.KaratsubaCircuit(41, [0, 3])
    meta = method.build(circuit, bases_w, bases_u, context["columns"], target_us,
                        rotations=rotations if frame else None,
                        field=field if frame else None)
    formula = HERE / ("public_relation_frame.xcnf" if frame else "public_relation.xcnf")
    circuit.write(formula)
    leaves, middle, total = gate.chain(context, hit["masks"], hit["signs"])
    assert gate.regular(context, [*leaves, *middle, total])
    assert total == targets[hit["target_preimage_index"]]
    initial = {}
    for row, mask in zip(meta["masks"], hit["masks"]):
        initial.update({wire: mask >> i & 1 for i, wire in enumerate(row)})
    for i, wire in enumerate(meta["flags"]):
        initial[wire] = int(i == hit["target_preimage_index"])
    for row, point in zip(meta["middle"], middle):
        value = gate.old.transformed(field, point)
        initial.update({wire: value >> i & 1 for i, wire in enumerate(row)})
    assert len(initial) == meta["primary_variables"]
    assignment = gate.old.witness_tools.complete_assignment(circuit, initial)
    check = gate.old.base.check_xcnf(formula, assignment)
    decoded = gate.decode(assignment, meta, context, qprime, targets)
    assert decoded["valid"] and decoded["masks"] == hit["masks"]
    assert decoded["signs"] == hit["signs"]
    stats = {"variables": circuit.next_var - 1,
             "clauses": len(circuit.clauses), "xor_rows": len(circuit.xors),
             "and_gates": circuit.and_count, "bytes": formula.stat().st_size,
             "sha256": sha(formula)}
    baseline = public["formula"]
    receipt = {"status": "PASS_PUBLIC_RELATION_XCNF_ASSIGNMENT",
               "candidate_id": None, "curve_id": geometry["curve_id"],
               "public_target_q": public["public_target_q"],
               "target_preimage_index": hit["target_preimage_index"],
               "actual_factor_base_points_B": geometry["actual_subgroup_factor_base_points_B"],
               "effective_folded_columns_K": geometry["folded_columns_K"],
               "method": {"low_product_leaf_links": 5, "generic_links": 4,
                          "pair_local_frobenius_frames": frame,
                          "rotations": rotations},
               "baseline_formula": baseline, "formula": stats,
               "xcnf_check": check,
               "source_sha256": {"script": sha(__file__),
                                 "circuit": sha(HERE / "circuit.py"),
                                 "public_relation": sha(JOIN / "run/hits.jsonl"),
                                 "sage_replay": sha(JOIN / "sage_hit_audit.json"),
                                 "gate_run": sha(GATE / "run.py"),
                                 "geometry": sha(GATE / "geometry_result.json")}}
    with (HERE / ("frame_audit.json" if frame else "audit.json")).open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"], "baseline": baseline,
                      "formula": stats}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--frame", action="store_true")
    args = parser.parse_args()
    main(args.frame)
