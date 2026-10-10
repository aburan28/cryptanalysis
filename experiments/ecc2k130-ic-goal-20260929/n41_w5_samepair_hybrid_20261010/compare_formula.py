#!/usr/bin/env sage -python
"""Matched exact versus relaxed fifth-pair formula construction control."""

import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("n41_samepair_hybrid_runner_for_comparison",
                                              HERE / "run.py")
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    with path.open("x") as out:
        json.dump(value, out, indent=2, sort_keys=True)
        out.write("\n")


def main():
    record = run.verify()
    preflight = json.loads((HERE / "preflight.json").read_text())
    assert preflight["status"] == "PASS_FULL_HYBRID_FORMULA_PUBLIC_RELATION"
    ctx = run.context()
    hit, targets, middle, _ = run.witness(ctx)
    target_us = [run.old.old.transformed(ctx["field"], point) for point in targets]
    circuit = run.old.old.base.KaratsubaCircuit(41, [0, 3])
    geometry = ctx["geometry"]
    bases_w = [[run.hybrid.method.frob(ctx["field"], w, rotation)
                for w in geometry["source_basis_w"]]
               for rotation in run.ROTATIONS]
    meta = run.hybrid.method.build(
        circuit, bases_w, geometry["bases_u"], ctx["columns"], target_us,
        rotations=run.ROTATIONS, field=ctx["field"])
    formula = HERE / "exact_samepair.xcnf"
    circuit.write(formula)
    initial = {}
    for row, mask in zip(meta["masks"], hit["masks"]):
        initial.update({wire: mask >> i & 1 for i, wire in enumerate(row)})
    for i, wire in enumerate(meta["flags"]):
        initial[wire] = int(i == hit["target_preimage_index"])
    for row, point in zip(meta["middle"], middle):
        value = run.old.old.transformed(ctx["field"], point)
        initial.update({wire: value >> i & 1 for i, wire in enumerate(row)})
    assignment = run.old.old.witness_tools.complete_assignment(circuit, initial)
    check = run.old.old.base.check_xcnf(formula, assignment)
    relation = run.old.decode(assignment, meta, ctx,
                              run.old.qprime_of(ctx, ctx["q"]), targets)
    assert relation["valid"] and relation["masks"] == hit["masks"]
    exact = {"variables": circuit.next_var - 1,
             "clauses": len(circuit.clauses), "xor_rows": len(circuit.xors),
             "and_gates": circuit.and_count, "bytes": formula.stat().st_size,
             "sha256": sha(formula)}
    relaxed = preflight["formula"]
    receipt = {"status": "PASS_MATCHED_EXACT_AND_RELAXED_FORMULA_CONTROLS",
               "candidate_id": None, "curve_id": record["curve_id"],
               "public_target_q": record["public_target_q"],
               "actual_factor_base_points_B": 170, "folded_columns_K": 14,
               "exact": exact, "relaxed": relaxed,
               "relaxed_over_exact": {name: relaxed[name] / exact[name]
                                      for name in ("variables", "clauses",
                                                   "xor_rows", "and_gates")},
               "exact_full_assignment_check": check,
               "source_sha256": {"script": sha(Path(__file__)),
                                 "hybrid_protocol": sha(HERE / "hybrid_protocol.json"),
                                 "hybrid_preflight": sha(HERE / "preflight.json"),
                                 "exact_formula": sha(formula)}}
    save(HERE / "formula_comparison.json", receipt)
    print(json.dumps({"status": receipt["status"],
                      "exact": exact, "relaxed": relaxed}))


if __name__ == "__main__":
    main()
