"""Build one W18 resultant XCNF admitting all four public preimages."""

import argparse
import hashlib
import json
import resource
import sys
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
FOUR = HERE.parent / "n131_w18_four_preimage_20261010"
BASE = HERE.parent / "n131_fixed_seed_eight_pair_circuit_20261010"
FOURMUL = HERE.parent / "n131_reciprocal_s3_fourmul_20261010"
POSITIVE = HERE.parent / "n131_w18_positive_bdd_20261010"
RESULTANT = HERE.parent / "n131_w18_two_link_resultant_20261010"
FLAT = HERE.parent / "n131_w18_parity_flatten_20261010"
ROOT = HERE.parents[2]
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(FOURMUL))
sys.path.insert(0, str(POSITIVE))
sys.path.insert(0, str(RESULTANT))
sys.path.insert(0, str(FLAT))
sys.path.insert(0, str(ROOT / "ecc2k130/codegen"))
import cnf  # noqa: E402
import build  # noqa: E402
import fixed_pair_circuit as pair  # noqa: E402
from resultant_circuit import build_program  # noqa: E402
from positive_bdd import check_positive_gate, emit_positive_bdd  # noqa: E402
from flat_emit import emit_constraints  # noqa: E402

_original_pb_mul = build.pbMulIr


def cutoff_one_mul(prog, a, b, n, taps, cutoff):
    return _original_pb_mul(prog, a, b, n, taps, 1)


build.pbMulIr = cutoff_one_mul


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("constructed", "ordinary", "unpinned_constructed"), required=True)
    args = parser.parse_args()
    protocol_path = HERE / "formula_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    paths = {"script": Path(__file__), "flat_emitter": FLAT / "flat_emit.py",
             "positive_bdd": POSITIVE / "positive_bdd.py",
             "resultant_circuit": RESULTANT / "resultant_circuit.py",
             "resultant_result": RESULTANT / "circuit_result.json",
             "prior_ordinary_build": FLAT / "flat_ordinary_build.json",
             "fourmul": FOURMUL / "fourmul.py",
             "fourmul_result": FOURMUL / "result.json",
             "link_equivalence": FOURMUL / "link_equivalence_result.json",
             "baseline_circuit": BASE / "fixed_pair_circuit.py",
             "source_bound_formula": POSITIVE / "positive_ordinary.xcnf",
             "source_bound_build": POSITIVE / "positive_ordinary_build.json",
             "derive": BASE / "derive_result.json",
             "planted_chain": BASE / "planted_chain_result.json",
             "planted_preimages": FOUR / "planted_preimages_result.json",
             "ordinary_target": BASE / "target_preimages.json",
             "mask_columns": BASE.parent / "n131_w16_w18_sixpair_width_gate_20261010/support_w18.tsv",
             "cnf": ROOT / "ecc2k130/codegen/cnf.py",
             "build": ROOT / "ecc2k130/codegen/build.py",
             "ir": ROOT / "ecc2k130/codegen/ir.py"}
    for name, path in paths.items():
        assert protocol["source_sha256"][name] == digest(path), name
    assert protocol["resource_cap_bytes"] == 4294967296
    assert protocol["multiplication_leaf_cutoff"] == 1
    check_positive_gate()
    planted = json.loads(paths["planted_chain"].read_text())
    derive = json.loads(paths["derive"].read_text())
    ordinary = json.loads(paths["ordinary_target"].read_text())
    planted_preimages = json.loads(paths["planted_preimages"].read_text())
    assert planted_preimages["status"] == "PASS_CONSTRUCTED_FOUR_PREIMAGES"
    preimages = (planted_preimages if args.mode in ("constructed", "unpinned_constructed")
                 else ordinary)
    target_values = [item["reciprocal_x_z"] for item in preimages["preimages"]]
    assert len(set(target_values)) == 4
    assert target_values[1] == target_values[0] ^ 1
    assert target_values[3] == target_values[2] ^ 1
    delta = target_values[0] ^ target_values[2]
    assert [target_values[0] ^ (index & 1) ^ (delta if index & 2 else 0)
            for index in range(4)] == target_values
    if args.mode in ("constructed", "unpinned_constructed"):
        assert target_values[0] == planted["raw_target_z"]

    start = time.monotonic_ns()
    mask_columns = {int(mask): int(column) for mask, column in
                    (line.split() for line in paths["mask_columns"].read_text().splitlines())}
    valid = pair.valid_codes(mask_columns)
    root, nodes = pair.build_bdd(valid)
    assert len(valid) == 33191 and len(nodes) == 13093
    bdd_ready = time.monotonic_ns()
    prog, roots, deltas, recoveries = build_program()
    assert len(roots) == 12*pair.N and len(deltas) == 3
    assert prog.opCount(roots) == 469003
    ir_ready = time.monotonic_ns()

    c = cnf.Cnf()
    selectors = [[c.newVar() for _ in range(17)] for _ in range(8)]
    outputs = [[c.newVar() for _ in range(pair.N)] for _ in range(8)]
    intermediates = [[c.newVar() for _ in range(pair.N)] for _ in range(3)]
    choice_low, choice_high = c.newVar(), c.newVar()
    literals = {("one", 0): c.true}
    for slot in range(8):
        literals.update({("a%d" % slot, bit): selectors[slot][bit] for bit in range(17)})
        literals.update({("z%d" % slot, bit): outputs[slot][bit] for bit in range(pair.N)})
    for slot, index in enumerate((1, 3, 5)):
        literals.update({("t%d" % index, bit): intermediates[slot][bit]
                         for bit in range(pair.N)})
    for bit in range(pair.N):
        value = c.true if target_values[0] >> bit & 1 else c.false
        if bit == 0:
            value = c.xorLit(value, choice_low)
        if delta >> bit & 1:
            value = c.xorLit(value, choice_high)
        literals[("target", bit)] = value
    emitter_stats = emit_constraints(prog, roots, deltas, literals, c)
    for slot in range(8):
        emit_positive_bdd(c, root, nodes, selectors[slot])
        c.addClause(outputs[slot])
    for vector in intermediates:
        c.addClause(vector)
    if args.mode == "constructed":
        c.addClause([-choice_low])
        c.addClause([-choice_high])
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
    path = HERE / ("four_%s.xcnf" % args.mode)
    c.writeDimacs(path)
    written = time.monotonic_ns()
    result = {"status": "PASS_FOUR_PREIMAGE_RESULTANT_XCNF_BUILD", "mode": args.mode,
              "curve_id": "EC1N131Ckb1heb5f1998f20b",
              "workload_id": ordinary["workload_id"] if args.mode == "ordinary" else None,
              "candidate_id": None, "raw_target_z": target_values[0],
              "target_z_values": target_values,
              "target_choice_variables": [choice_low, choice_high],
              "target_affine_delta": delta,
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
    with (HERE / ("four_%s_build.json" % args.mode)).open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"], "mode": args.mode,
                      "xcnf": result["xcnf"]}))


if __name__ == "__main__":
    main()
