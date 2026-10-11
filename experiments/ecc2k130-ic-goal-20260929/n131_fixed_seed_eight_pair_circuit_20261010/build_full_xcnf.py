"""Serialize the exact eight-pair N131 reciprocal system to native-XOR XCNF."""

import argparse
import hashlib
import json
import resource
import sys
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "ecc2k130/codegen"))
import cnf  # noqa: E402
import fixed_pair_circuit as pair  # noqa: E402
from full_preflight import build_program  # noqa: E402


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("planted", "ordinary"), required=True)
    args = parser.parse_args()
    protocol = json.loads((HERE / "full_formula_protocol.json").read_text())
    source = HERE.parent / "n131_w16_w18_sixpair_width_gate_20261010" / "support_w18.tsv"
    paths = {"script": Path(__file__), "circuit": HERE / "fixed_pair_circuit.py",
             "full_preflight_source": HERE / "full_preflight.py",
             "full_preflight_result": HERE / "full_preflight_result.json",
             "pair_audit": HERE / "pair_model_audit.json",
             "support": HERE / "support_result.json", "derive": HERE / "derive_result.json",
             "planted_chain": HERE / "planted_chain_result.json",
             "ordinary_target": HERE / "target_preimages.json",
             "mask_columns": source, "cnf": ROOT / "ecc2k130/codegen/cnf.py",
             "ir": ROOT / "ecc2k130/codegen/ir.py",
             "build": ROOT / "ecc2k130/codegen/build.py"}
    for name, path in paths.items():
        assert protocol["source_sha256"][name] == digest(path), name
    assert protocol["resource_cap_bytes"] == 4294967296
    planted = json.loads(paths["planted_chain"].read_text())
    derive = json.loads(paths["derive"].read_text())
    ordinary = json.loads(paths["ordinary_target"].read_text())
    target_z = (planted["raw_target_z"] if args.mode == "planted" else
                ordinary["preimages"][0]["reciprocal_x_z"])

    start = time.monotonic_ns()
    mask_columns = {int(mask): int(column) for mask, column in
                    (line.split() for line in source.read_text().splitlines())}
    valid = pair.valid_codes(mask_columns)
    root, nodes = pair.build_bdd(valid)
    assert len(valid) == 33191 and len(nodes) == 13093
    bdd_ready = time.monotonic_ns()
    prog, roots = build_program()
    assert len(roots) == 15*pair.N
    assert prog.opCount(roots) == json.loads(paths["full_preflight_result"].read_text())["ir_live_ops"]
    ir_ready = time.monotonic_ns()

    c = cnf.Cnf()
    selectors = [[c.newVar() for _ in range(17)] for _ in range(8)]
    outputs = [[c.newVar() for _ in range(pair.N)] for _ in range(8)]
    intermediates = [[c.newVar() for _ in range(pair.N)] for _ in range(6)]
    lits = {("one", 0): c.true}
    for slot in range(8):
        lits.update({("a%d" % slot, bit): selectors[slot][bit] for bit in range(17)})
        lits.update({("z%d" % slot, bit): outputs[slot][bit] for bit in range(pair.N)})
    for slot in range(6):
        lits.update({("t%d" % slot, bit): intermediates[slot][bit] for bit in range(pair.N)})
    lits.update({("target", bit): c.true if target_z >> bit & 1 else c.false
                 for bit in range(pair.N)})
    for root_lit in prog.emitCnf(roots, lits, c):
        c.assertZero(root_lit)
    for slot in range(8):
        pair.emit_bdd(c, root, nodes, selectors[slot])
        c.addClause(outputs[slot])
    for value in intermediates:
        c.addClause(value)
    if args.mode == "planted":
        for slot, item in enumerate(derive["selected"]):
            code = pair.selector_code(item["masks"][0])
            z = item["unrotated_pair_output_z"]
            for bit, literal in enumerate(selectors[slot]):
                c.addClause([literal if code >> bit & 1 else -literal])
            for bit, literal in enumerate(outputs[slot]):
                c.addClause([literal if z >> bit & 1 else -literal])
        for slot, z in enumerate(planted["intermediate_z"]):
            for bit, literal in enumerate(intermediates[slot]):
                c.addClause([literal if z >> bit & 1 else -literal])
    encoded = time.monotonic_ns()
    path = HERE / ("full_%s.xcnf" % args.mode)
    c.writeDimacs(path)
    written = time.monotonic_ns()
    result = {"status": "PASS_FULL_EIGHT_PAIR_XCNF_BUILD",
              "mode": args.mode, "candidate_id": None,
              "curve_id": "EC1N131Ckb1heb5f1998f20b",
              "raw_target_z": target_z, "target_count": 1,
              "public_workload_id": ordinary["workload_id"] if args.mode == "ordinary" else None,
              "fixed_seed_mask": pair.SEED, "pair_slots": 8,
              "valid_source_pairs_per_slot": len(valid), "bdd_nodes": len(nodes),
              "root_count": len(roots), "ir_live_ops": prog.opCount(roots),
              "xcnf": {**c.stats(), "bytes": path.stat().st_size, "sha256": digest(path)},
              "phase_ns": {"reusable_bdd": bdd_ready-start,
                           "reusable_ir": ir_ready-bdd_ready,
                           "target_formula_encode": encoded-ir_ready,
                           "target_formula_write": written-encoded},
              "peak_process_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              "source_sha256": {name: digest(path) for name, path in paths.items()},
              "protocol_sha256": digest(HERE / "full_formula_protocol.json")}
    with (HERE / ("full_%s_build.json" % args.mode)).open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"], "mode": args.mode,
                      "xcnf": result["xcnf"],
                      "peak_rss_bytes": result["peak_process_rss_bytes"]}))


if __name__ == "__main__":
    main()
