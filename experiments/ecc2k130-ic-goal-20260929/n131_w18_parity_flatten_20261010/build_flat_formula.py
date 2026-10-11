"""Build the same W18 resultant XCNF with parity-flattened IR emission."""

import argparse
import hashlib
import json
import resource
import sys
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "n131_fixed_seed_eight_pair_circuit_20261010"
FOURMUL = HERE.parent / "n131_reciprocal_s3_fourmul_20261010"
POSITIVE = HERE.parent / "n131_w18_positive_bdd_20261010"
RESULTANT = HERE.parent / "n131_w18_two_link_resultant_20261010"
ROOT = HERE.parents[2]
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(FOURMUL))
sys.path.insert(0, str(POSITIVE))
sys.path.insert(0, str(RESULTANT))
sys.path.insert(0, str(ROOT / "ecc2k130/codegen"))
import cnf  # noqa: E402
import fixed_pair_circuit as pair  # noqa: E402
from resultant_circuit import build_program  # noqa: E402
from positive_bdd import check_positive_gate, emit_positive_bdd  # noqa: E402
from flat_emit import emit_constraints  # noqa: E402


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("constructed", "ordinary"), required=True)
    args = parser.parse_args()
    protocol_path = HERE / "formula_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    paths = {"script": Path(__file__), "flat_emitter": HERE / "flat_emit.py",
             "positive_bdd": POSITIVE / "positive_bdd.py",
             "resultant_circuit": RESULTANT / "resultant_circuit.py",
             "resultant_result": RESULTANT / "circuit_result.json",
             "prior_ordinary_build": RESULTANT / "resultant_ordinary_build.json",
             "fourmul": FOURMUL / "fourmul.py",
             "fourmul_result": FOURMUL / "result.json",
             "link_equivalence": FOURMUL / "link_equivalence_result.json",
             "baseline_circuit": BASE / "fixed_pair_circuit.py",
             "source_bound_formula": POSITIVE / "positive_ordinary.xcnf",
             "source_bound_build": POSITIVE / "positive_ordinary_build.json",
             "derive": BASE / "derive_result.json",
             "planted_chain": BASE / "planted_chain_result.json",
             "ordinary_target": BASE / "target_preimages.json",
             "mask_columns": BASE.parent / "n131_w16_w18_sixpair_width_gate_20261010/support_w18.tsv",
             "cnf": ROOT / "ecc2k130/codegen/cnf.py",
             "build": ROOT / "ecc2k130/codegen/build.py",
             "ir": ROOT / "ecc2k130/codegen/ir.py"}
    for name, path in paths.items():
        assert protocol["source_sha256"][name] == digest(path), name
    assert protocol["resource_cap_bytes"] == 4294967296
    check_positive_gate()
    planted = json.loads(paths["planted_chain"].read_text())
    derive = json.loads(paths["derive"].read_text())
    ordinary = json.loads(paths["ordinary_target"].read_text())
    target_z = (planted["raw_target_z"] if args.mode == "constructed" else
                ordinary["preimages"][0]["reciprocal_x_z"])

    start = time.monotonic_ns()
    mask_columns = {int(mask): int(column) for mask, column in
                    (line.split() for line in paths["mask_columns"].read_text().splitlines())}
    valid = pair.valid_codes(mask_columns)
    root, nodes = pair.build_bdd(valid)
    assert len(valid) == 33191 and len(nodes) == 13093
    bdd_ready = time.monotonic_ns()
    prog, roots, deltas, recoveries = build_program()
    assert len(roots) == 12*pair.N and len(deltas) == 3
    assert prog.opCount(roots) == json.loads(paths["resultant_result"].read_text())["ir_live_ops"]
    ir_ready = time.monotonic_ns()

    c = cnf.Cnf()
    selectors = [[c.newVar() for _ in range(17)] for _ in range(8)]
    outputs = [[c.newVar() for _ in range(pair.N)] for _ in range(8)]
    intermediates = [[c.newVar() for _ in range(pair.N)] for _ in range(3)]
    literals = {("one", 0): c.true}
    for slot in range(8):
        literals.update({("a%d" % slot, bit): selectors[slot][bit] for bit in range(17)})
        literals.update({("z%d" % slot, bit): outputs[slot][bit] for bit in range(pair.N)})
    for slot, index in enumerate((1, 3, 5)):
        literals.update({("t%d" % index, bit): intermediates[slot][bit]
                         for bit in range(pair.N)})
    literals.update({("target", bit): c.true if target_z >> bit & 1 else c.false
                     for bit in range(pair.N)})
    emitter_stats = emit_constraints(prog, roots, deltas, literals, c)
    for slot in range(8):
        emit_positive_bdd(c, root, nodes, selectors[slot])
        c.addClause(outputs[slot])
    for vector in intermediates:
        c.addClause(vector)
    if args.mode == "constructed":
        for slot, item in enumerate(derive["selected"]):
            code = pair.selector_code(item["masks"][0])
            z = item["unrotated_pair_output_z"]
            for bit, lit in enumerate(selectors[slot]):
                c.addClause([lit if code >> bit & 1 else -lit])
            for bit, lit in enumerate(outputs[slot]):
                c.addClause([lit if z >> bit & 1 else -lit])
        for slot, index in enumerate((1, 3, 5)):
            z = planted["intermediate_z"][index]
            for bit, lit in enumerate(intermediates[slot]):
                c.addClause([lit if z >> bit & 1 else -lit])
    encoded = time.monotonic_ns()
    path = HERE / ("flat_%s.xcnf" % args.mode)
    c.writeDimacs(path)
    written = time.monotonic_ns()
    result = {"status": "PASS_FLATTENED_RESULTANT_XCNF_BUILD", "mode": args.mode,
              "curve_id": "EC1N131Ckb1heb5f1998f20b",
              "workload_id": ordinary["workload_id"] if args.mode == "ordinary" else None,
              "candidate_id": None, "raw_target_z": target_z,
              "root_count": len(roots), "ir_live_ops": prog.opCount(roots),
              "nondegenerate_blocks": len(deltas),
              "emitter_stats": emitter_stats,
              "valid_pair_codes": len(valid), "bdd_nodes": len(nodes),
              "xcnf": {**c.stats(), "bytes": path.stat().st_size,
                       "sha256": digest(path)},
              "phase_ns": {"reusable_bdd": bdd_ready-start,
                           "reusable_ir": ir_ready-bdd_ready,
                           "target_formula_encode": encoded-ir_ready,
                           "target_formula_write": written-encoded},
              "peak_process_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              "source_sha256": {name: digest(path) for name, path in paths.items()},
              "protocol_sha256": digest(protocol_path)}
    with (HERE / ("flat_%s_build.json" % args.mode)).open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"], "mode": args.mode,
                      "xcnf": result["xcnf"]}))


if __name__ == "__main__":
    main()
