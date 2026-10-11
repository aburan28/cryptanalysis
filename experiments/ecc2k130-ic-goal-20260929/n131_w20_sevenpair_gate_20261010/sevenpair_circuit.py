"""Exact seven-pair W20 N131 Boolean circuit using four-product S3 links."""

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
import fixed_pair_circuit as base_pair  # noqa: E402
import ir  # noqa: E402
from fourmul import reciprocal_s3_fourmul_ir  # noqa: E402


N = 131
WIDTH = 20
ROTATIONS = [0, 18, 36, 54, 72, 90, 108]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def seed_and_bits():
    count = json.loads((HERE / "count_result_v2.json").read_text())
    seed = count["selected_seed_mask"]
    bits = [bit for bit in range(WIDTH) if bit != seed.bit_length()-1]
    return seed, bits


def coordinate(mask):
    return sum((1 << (bit+1) for bit in range(WIDTH) if mask >> bit & 1), 0)


def selector_code(mask, bits):
    if mask >> (WIDTH-1) & 1:
        raise ValueError("source mask is not canonical for selected seed")
    return sum(((mask >> bit) & 1) << index for index, bit in enumerate(bits))


def product_basis(seed, bits):
    seed_field = coordinate(seed)
    return [(1 << (2*(bit+1))) ^ (seed_field << (bit+1)) for bit in bits]


def pair_ir(prog, slot, one, seed, bits, cutoff=3):
    selectors = [prog.addInput("a%d" % slot, bit) for bit in range(len(bits))]
    z = [prog.addInput("z%d" % slot, bit) for bit in range(N)]
    basis = product_basis(seed, bits)
    p = [prog.xorList(selectors[index] for index, value in enumerate(basis)
                      if value >> bit & 1) for bit in range(N)]
    z2 = build.pbSqrIr(prog, z, N, base_pair.TAPS)
    az = base_pair.xor_vectors(prog, z2, z)
    product = build.pbMulIr(prog, az, p, N, base_pair.TAPS, cutoff)
    seed_u2 = base_pair.gf_square(base_pair.gf_half_trace(coordinate(seed)))
    roots = [prog.xorList((product[bit], z2[bit],
                           one if seed_u2 >> bit & 1 else None))
             for bit in range(N)]
    return roots, z


def build_program(seed, bits):
    prog = ir.Prog()
    one = prog.addInput("one", 0)
    roots = []
    rotated = []
    for slot, rotation in enumerate(ROTATIONS):
        pair_roots, z = pair_ir(prog, slot, one, seed, bits)
        roots.extend(pair_roots)
        rotated.append(base_pair.rotate_ir(prog, z, rotation))
    intermediates = [[prog.addInput("t%d" % index, bit)
                      for bit in range(N)] for index in range(5)]
    target = [prog.addInput("target", bit) for bit in range(N)]
    running = rotated[0]
    for index in range(1, 7):
        output = intermediates[index-1] if index < 6 else target
        roots.extend(reciprocal_s3_fourmul_ir(prog, running, rotated[index],
                                              output, one, cutoff=3))
        running = output
    return prog, roots


def assign_bits(values, name, value):
    values.update({(name, bit): (value >> bit) & 1 for bit in range(N)})


def main():
    protocol_path = HERE / "circuit_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    paths = {"script": Path(__file__), "count": HERE / "count_result_v2.json",
             "bdd": HERE / "bdd_result.json",
             "sage_audit": HERE / "sage_audit_result.json",
             "ordinary_target": BASE / "target_preimages.json",
             "base_pair": BASE / "fixed_pair_circuit.py",
             "fourmul": FOURMUL / "fourmul.py",
             "build": ROOT / "ecc2k130/codegen/build.py",
             "ir": ROOT / "ecc2k130/codegen/ir.py"}
    for name, path in paths.items():
        assert protocol["source_sha256"][name] == digest(path), name
    seed, bits = seed_and_bits()
    bdd = json.loads(paths["bdd"].read_text())
    assert seed == bdd["fixed_seed_mask"] and bits == bdd["selector_bits"]
    planted = json.loads(paths["sage_audit"].read_text())
    ordinary = json.loads(paths["ordinary_target"].read_text())
    prog, roots = build_program(seed, bits)
    assert len(roots) == 13*N
    values = {("one", 0): 1}
    for item in planted["selected"]:
        slot = item["slot"]
        code = selector_code(item["masks"][0], bits)
        values.update({("a%d" % slot, bit): (code >> bit) & 1
                       for bit in range(len(bits))})
        assign_bits(values, "z%d" % slot, item["unrotated_pair_output_z"])
    for index, value in enumerate(planted["intermediate_z"]):
        assign_bits(values, "t%d" % index, value)
    assign_bits(values, "target", planted["constructed_raw_target_z"])
    planted_roots = prog.evaluate(values, roots)
    assert not any(planted_roots)
    assign_bits(values, "target", ordinary["preimages"][0]["reciprocal_x_z"])
    ordinary_failed_roots = sum(prog.evaluate(values, roots))
    assert ordinary_failed_roots > 0
    result = {"status": "PASS_W20_SEVEN_PAIR_TARGET_CONDITIONED_IR",
              "curve_id": "EC1N131Ckb1heb5f1998f20b",
              "workload_id": ordinary["workload_id"],
              "candidate_id": None, "source_dimension": WIDTH,
              "fixed_seed_mask": seed, "selector_dimension_per_slot": len(bits),
              "pair_slots": 7, "s3_links": 6,
              "root_count": len(roots),
              "ir_live_ops": prog.opCount(roots),
              "pair_live_ops": prog.opCount(roots[:7*N]),
              "link_live_ops": prog.opCount(roots[7*N:]),
              "planted_failed_roots": sum(planted_roots),
              "ordinary_target_with_planted_leaves_failed_roots": ordinary_failed_roots,
              "source_sha256": {name: digest(path) for name, path in paths.items()},
              "protocol_sha256": digest(protocol_path)}
    with (HERE / "circuit_result.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"],
                      "ir_live_ops": result["ir_live_ops"],
                      "pair_live_ops": result["pair_live_ops"],
                      "link_live_ops": result["link_live_ops"]}))


if __name__ == "__main__":
    main()
