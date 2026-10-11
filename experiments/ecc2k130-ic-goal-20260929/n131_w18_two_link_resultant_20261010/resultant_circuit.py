"""Three nondegenerate two-link S3 resultants in the W18 eight-pair chain."""

import hashlib
import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "n131_fixed_seed_eight_pair_circuit_20261010"
FOURMUL = HERE.parent / "n131_reciprocal_s3_fourmul_20261010"
ROOT = HERE.parents[2]
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(FOURMUL))
sys.path.insert(0, str(ROOT / "ecc2k130/codegen"))
import build  # noqa: E402
import fixed_pair_circuit as pair  # noqa: E402
import ir  # noqa: E402
from fourmul import reciprocal_s3_fourmul_ir  # noqa: E402


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def square(prog, bits):
    return build.pbSqrIr(prog, bits, pair.N, pair.TAPS)


def multiply(prog, a, b, cutoff=3):
    return build.pbMulIr(prog, a, b, pair.N, pair.TAPS, cutoff)


def two_link_resultant_ir(prog, a, b, c, d, cutoff=3):
    """Return resultant roots and D,E for the unique middle when D is nonzero."""
    ha = pair.xor_vectors(prog, square(prog, a), a)
    hb = pair.xor_vectors(prog, square(prog, b), b)
    hc = pair.xor_vectors(prog, square(prog, c), c)
    hd = pair.xor_vectors(prog, square(prog, d), d)
    h = multiply(prog, ha, hb, cutoff)
    k = multiply(prog, hc, hd, cutoff)
    c0 = square(prog, pair.xor_vectors(prog, a, b))
    z0 = square(prog, pair.xor_vectors(prog, c, d))
    s = pair.xor_vectors(prog, multiply(prog, k, c0, cutoff),
                         multiply(prog, h, z0, cutoff))
    delta = pair.xor_vectors(prog, h, k)
    e = pair.xor_vectors(prog, c0, z0, s)
    roots = pair.xor_vectors(prog, square(prog, e),
                             multiply(prog, delta, s, cutoff))
    return roots, delta, e


def build_program():
    prog = ir.Prog()
    one = prog.addInput("one", 0)
    roots = []
    rotated = []
    for slot, rotation in enumerate(pair.ROTATIONS):
        pair_roots, z = pair.pair_ir(prog, slot, one, cutoff=3)
        roots.extend(pair_roots)
        rotated.append(pair.rotate_ir(prog, z, rotation))
    middle = [[prog.addInput("t%d" % index, bit) for bit in range(pair.N)]
              for index in (1, 3, 5)]
    target = [prog.addInput("target", bit) for bit in range(pair.N)]
    deltas = []
    recoveries = []
    for index, (a, b, c, d) in enumerate(((rotated[0], rotated[1], rotated[2], middle[0]),
                                           (middle[0], rotated[3], rotated[4], middle[1]),
                                           (middle[1], rotated[5], rotated[6], middle[2]))):
        block_roots, delta, e = two_link_resultant_ir(prog, a, b, c, d)
        roots.extend(block_roots)
        deltas.append(delta)
        recoveries.append(e)
    roots.extend(reciprocal_s3_fourmul_ir(prog, middle[2], rotated[7],
                                          target, one, cutoff=3))
    assert len(roots) == 12*pair.N
    return prog, roots, deltas, recoveries


def assign_bits(values, name, value):
    values.update({(name, bit): (value >> bit) & 1 for bit in range(pair.N)})


def constructed_values():
    derive = json.loads((BASE / "derive_result.json").read_text())
    chain = json.loads((BASE / "planted_chain_result.json").read_text())
    values = {("one", 0): 1}
    for item in derive["selected"]:
        slot = item["slot"]
        code = pair.selector_code(item["masks"][0])
        values.update({("a%d" % slot, bit): (code >> bit) & 1
                       for bit in range(17)})
        assign_bits(values, "z%d" % slot, item["unrotated_pair_output_z"])
    for index in (1, 3, 5):
        assign_bits(values, "t%d" % index, chain["intermediate_z"][index])
    assign_bits(values, "target", chain["raw_target_z"])
    return values, chain


def main():
    protocol_path = HERE / "circuit_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    paths = {"script": Path(__file__), "pair": BASE / "fixed_pair_circuit.py",
             "fourmul": FOURMUL / "fourmul.py",
             "fourmul_result": FOURMUL / "result.json",
             "derive": BASE / "derive_result.json",
             "chain": BASE / "planted_chain_result.json",
             "target": BASE / "target_preimages.json",
             "build": ROOT / "ecc2k130/codegen/build.py",
             "ir": ROOT / "ecc2k130/codegen/ir.py",
             "prior_resultant": HERE.parent / "s3_two_link_resultant_circuit.py"}
    for name, path in paths.items():
        assert protocol["source_sha256"][name] == digest(path), name
    prog, roots, deltas, recoveries = build_program()
    values, chain = constructed_values()
    planted_roots = prog.evaluate(values, roots)
    assert not any(planted_roots)
    delta_values = [sum(bit << index for index, bit in
                        enumerate(prog.evaluate(values, vector)))
                    for vector in deltas]
    e_values = [sum(bit << index for index, bit in
                    enumerate(prog.evaluate(values, vector)))
                for vector in recoveries]
    assert all(delta_values)
    eliminated = [chain["intermediate_z"][index] for index in (0, 2, 4)]
    assert all(pair.gf_mul(delta, middle) == e for delta, middle, e in
               zip(delta_values, eliminated, e_values))
    target = json.loads(paths["target"].read_text())
    assign_bits(values, "target", target["preimages"][0]["reciprocal_x_z"])
    ordinary_with_constructed_leaves = sum(prog.evaluate(values, roots))
    assert ordinary_with_constructed_leaves > 0
    old = json.loads(paths["fourmul_result"].read_text())
    result = {"status": "PASS_THREE_NONDEGENERATE_TWO_LINK_RESULTANTS",
              "curve_id": "EC1N131Ckb1heb5f1998f20b",
              "workload_id": target["workload_id"], "candidate_id": None,
              "pair_slots": 8, "resultant_blocks": 3, "remaining_s3_links": 1,
              "root_count": len(roots), "ir_live_ops": prog.opCount(roots),
              "prior_fourmul_ir_live_ops": old["new_live_ops"],
              "nondegeneracy_delta_values": delta_values,
              "eliminated_middle_coordinates": eliminated,
              "recovered_middle_products": e_values,
              "ordinary_target_with_constructed_leaves_failed_roots": ordinary_with_constructed_leaves,
              "source_sha256": {name: digest(path) for name, path in paths.items()},
              "protocol_sha256": digest(protocol_path)}
    with (HERE / "circuit_result.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"],
                      "ir_live_ops": result["ir_live_ops"],
                      "prior_ir_live_ops": old["new_live_ops"]}))


if __name__ == "__main__":
    main()
