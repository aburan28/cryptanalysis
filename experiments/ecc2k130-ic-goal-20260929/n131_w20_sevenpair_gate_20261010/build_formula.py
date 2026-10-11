"""Serialize the exact W20 seven-pair source and reciprocal S3 chain to XCNF."""

import argparse
import hashlib
import json
import resource
import sys
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "n131_fixed_seed_eight_pair_circuit_20261010"
ROOT = HERE.parents[2]
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(ROOT / "ecc2k130/codegen"))
import cnf  # noqa: E402
import fixed_pair_circuit as base_pair  # noqa: E402
import bdd_gate  # noqa: E402
import sevenpair_circuit as seven  # noqa: E402


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("constructed", "ordinary"), required=True)
    args = parser.parse_args()
    protocol_path = HERE / "formula_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    paths = {"script": Path(__file__), "circuit": HERE / "sevenpair_circuit.py",
             "circuit_result": HERE / "circuit_result.json",
             "bdd_source": HERE / "bdd_gate.py", "bdd_result": HERE / "bdd_result.json",
             "count": HERE / "count_result_v2.json",
             "sage_audit": HERE / "sage_audit_result.json",
             "table": HERE / "support_w20.tsv",
             "ordinary_target": BASE / "target_preimages.json",
             "base_circuit": BASE / "fixed_pair_circuit.py",
             "cnf": ROOT / "ecc2k130/codegen/cnf.py",
             "build": ROOT / "ecc2k130/codegen/build.py",
             "ir": ROOT / "ecc2k130/codegen/ir.py"}
    for name, path in paths.items():
        assert protocol["source_sha256"][name] == digest(path), name
    assert protocol["rss_cap_bytes"] == 4294967296
    seed, bits = seven.seed_and_bits()
    planted = json.loads(paths["sage_audit"].read_text())
    ordinary = json.loads(paths["ordinary_target"].read_text())
    target_z = (planted["constructed_raw_target_z"] if args.mode == "constructed" else
                ordinary["preimages"][0]["reciprocal_x_z"])

    start = time.monotonic_ns()
    columns = {int(mask): int(column) for mask, column, shift in
               (line.split() for line in paths["table"].read_text().splitlines())}
    valid = set()
    for mask, column in columns.items():
        other = mask ^ seed
        if mask < other and other in columns and column != columns[other]:
            valid.add(seven.selector_code(mask, bits))
    bdd_expected = json.loads(paths["bdd_result"].read_text())
    assert len(valid) == bdd_expected["valid_codes"]
    root, nodes = bdd_gate.build_bdd(valid, bits)
    assert len(nodes) == bdd_expected["bdd_nodes"]
    bdd_ready = time.monotonic_ns()
    prog, roots = seven.build_program(seed, bits)
    assert len(roots) == 13*seven.N
    assert prog.opCount(roots) == json.loads(paths["circuit_result"].read_text())["ir_live_ops"]
    ir_ready = time.monotonic_ns()

    c = cnf.Cnf()
    selectors = [[c.newVar() for _ in bits] for _ in range(7)]
    outputs = [[c.newVar() for _ in range(seven.N)] for _ in range(7)]
    intermediates = [[c.newVar() for _ in range(seven.N)] for _ in range(5)]
    literals = {("one", 0): c.true}
    for slot in range(7):
        literals.update({("a%d" % slot, bit): selectors[slot][bit]
                         for bit in range(len(bits))})
        literals.update({("z%d" % slot, bit): outputs[slot][bit]
                         for bit in range(seven.N)})
    for slot in range(5):
        literals.update({("t%d" % slot, bit): intermediates[slot][bit]
                         for bit in range(seven.N)})
    literals.update({("target", bit): c.true if target_z >> bit & 1 else c.false
                     for bit in range(seven.N)})
    for root_lit in prog.emitCnf(roots, literals, c):
        c.assertZero(root_lit)
    for slot in range(7):
        base_pair.emit_bdd(c, root, nodes, selectors[slot])
        c.addClause(outputs[slot])
    for vector in intermediates:
        c.addClause(vector)
    if args.mode == "constructed":
        for slot, item in enumerate(planted["selected"]):
            code = seven.selector_code(item["masks"][0], bits)
            z = item["unrotated_pair_output_z"]
            for bit, lit in enumerate(selectors[slot]):
                c.addClause([lit if code >> bit & 1 else -lit])
            for bit, lit in enumerate(outputs[slot]):
                c.addClause([lit if z >> bit & 1 else -lit])
        for slot, z in enumerate(planted["intermediate_z"]):
            for bit, lit in enumerate(intermediates[slot]):
                c.addClause([lit if z >> bit & 1 else -lit])
    encoded = time.monotonic_ns()
    path = HERE / ("sevenpair_%s.xcnf" % args.mode)
    c.writeDimacs(path)
    written = time.monotonic_ns()
    result = {"status": "PASS_W20_SEVEN_PAIR_XCNF_BUILD",
              "mode": args.mode, "curve_id": "EC1N131Ckb1heb5f1998f20b",
              "workload_id": ordinary["workload_id"] if args.mode == "ordinary" else None,
              "candidate_id": None, "raw_target_z": target_z,
              "fixed_seed_mask": seed, "pair_slots": 7,
              "valid_pair_codes": len(valid), "bdd_nodes": len(nodes),
              "root_count": len(roots), "ir_live_ops": prog.opCount(roots),
              "xcnf": {**c.stats(), "bytes": path.stat().st_size,
                       "sha256": digest(path)},
              "phase_ns": {"reusable_bdd": bdd_ready-start,
                           "reusable_ir": ir_ready-bdd_ready,
                           "target_formula_encode": encoded-ir_ready,
                           "target_formula_write": written-encoded},
              "peak_process_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              "source_sha256": {name: digest(path) for name, path in paths.items()},
              "protocol_sha256": digest(protocol_path)}
    with (HERE / ("sevenpair_%s_build.json" % args.mode)).open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"], "mode": args.mode,
                      "xcnf": result["xcnf"]}))


if __name__ == "__main__":
    main()
