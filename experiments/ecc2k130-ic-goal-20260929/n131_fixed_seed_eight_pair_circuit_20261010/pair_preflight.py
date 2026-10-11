"""Build and verify one exact fixed-seed pair-output XCNF gate."""

import hashlib
import json
import sys
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "ecc2k130/codegen"))
import cnf  # noqa: E402
import fixed_pair_circuit as pair  # noqa: E402


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "pair_protocol.json").read_text())
    source = HERE.parent / "n131_w16_w18_sixpair_width_gate_20261010" / "support_w18.tsv"
    paths = {"script": Path(__file__), "circuit": HERE / "fixed_pair_circuit.py",
             "support": HERE / "support_result.json", "derive": HERE / "derive_result.json",
             "mask_columns": source, "cnf": ROOT / "ecc2k130/codegen/cnf.py",
             "ir": ROOT / "ecc2k130/codegen/ir.py",
             "build": ROOT / "ecc2k130/codegen/build.py"}
    for name, path in paths.items():
        assert protocol["source_sha256"][name] == digest(path), name
    start = time.monotonic_ns()
    columns = {int(mask): int(column) for mask, column in
               (line.split() for line in source.read_text().splitlines())}
    valid = pair.valid_codes(columns)
    assert len(valid) == 33191
    root, nodes = pair.build_bdd(valid)
    assert len(nodes) == 13093
    assert all(pair.bdd_accepts(root, nodes, code) == (code in valid)
               for code in range(1 << 17))
    bdd_end = time.monotonic_ns()

    witness = json.loads(paths["derive"].read_text())["selected"][0]
    left, right = witness["masks"]
    assert left ^ pair.SEED == right
    code = pair.selector_code(left)
    z = witness["unrotated_pair_output_z"]
    assert code in valid
    assert pair.product_from_code(code) == witness["product_p"]
    prog = pair.new_program()
    one = prog.addInput("one", 0)
    roots, _ = pair.pair_ir(prog, 0, one, cutoff=protocol["karatsuba_leaf_cutoff"])
    inputs = {("one", 0): 1}
    inputs.update({("a0", bit): code >> bit & 1 for bit in range(17)})
    inputs.update({("z0", bit): z >> bit & 1 for bit in range(pair.N)})
    assert not any(prog.evaluate(inputs, roots))
    flipped = dict(inputs)
    flipped[("z0", 0)] ^= 1
    assert any(prog.evaluate(flipped, roots))
    assert pair.gf_mul(pair.gf_square(z) ^ z, witness["product_p"]) == (
        pair.gf_square(z) ^ pair.gf_square(pair.gf_half_trace(pair.coordinate(pair.SEED))))
    ir_end = time.monotonic_ns()

    c = cnf.Cnf()
    selectors = [c.newVar() for _ in range(17)]
    z_lits = [c.newVar() for _ in range(pair.N)]
    lits = {("one", 0): c.true}
    lits.update({("a0", bit): selectors[bit] for bit in range(17)})
    lits.update({("z0", bit): z_lits[bit] for bit in range(pair.N)})
    for root_lit in prog.emitCnf(roots, lits, c):
        c.assertZero(root_lit)
    pair.emit_bdd(c, root, nodes, selectors)
    unpinned_stats = c.stats()
    c.writeDimacs(HERE / "pair_unpinned.xcnf")
    for bit, literal in enumerate(selectors):
        c.addClause([literal if code >> bit & 1 else -literal])
    for bit, literal in enumerate(z_lits):
        c.addClause([literal if z >> bit & 1 else -literal])
    pinned_stats = c.stats()
    c.writeDimacs(HERE / "pair_pinned.xcnf")
    encoded_end = time.monotonic_ns()
    result = {"status": "PASS_FIXED_SEED_PAIR_IR_AND_XCNF_PREFLIGHT",
              "candidate_id": None, "target_count": 0,
              "source_dimension": 18, "seed_mask": pair.SEED,
              "valid_unordered_pairs": len(valid), "bdd_nodes": len(nodes),
              "bdd_exhaustive_codes_checked": 1 << 17,
              "positive_mask_pair": [left, right],
              "positive_product_p": witness["product_p"],
              "positive_pair_output_z": z,
              "ir_live_ops": prog.opCount(roots),
              "ir_total_nodes": len(prog.ops),
              "unpinned_xcnf": {**unpinned_stats, "sha256": digest(HERE / "pair_unpinned.xcnf"),
                                "bytes": (HERE / "pair_unpinned.xcnf").stat().st_size},
              "pinned_xcnf": {**pinned_stats, "sha256": digest(HERE / "pair_pinned.xcnf"),
                              "bytes": (HERE / "pair_pinned.xcnf").stat().st_size},
              "phase_ns": {"bdd": bdd_end-start, "ir_and_controls": ir_end-bdd_end,
                           "cnf_and_write": encoded_end-ir_end},
              "source_sha256": {name: digest(path) for name, path in paths.items()},
              "protocol_sha256": digest(HERE / "pair_protocol.json")}
    with (HERE / "pair_preflight_result.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"],
                      "ir_live_ops": result["ir_live_ops"],
                      "unpinned_xcnf": unpinned_stats,
                      "pinned_xcnf": pinned_stats}))


if __name__ == "__main__":
    main()
