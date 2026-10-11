"""Four-field-multiplication form of the reciprocal S3 link."""

import hashlib
import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "n131_fixed_seed_eight_pair_circuit_20261010"
ROOT = HERE.parents[2]
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(ROOT / "ecc2k130/codegen"))
import build  # noqa: E402
import fixed_pair_circuit as pair  # noqa: E402
from full_preflight import build_program as baseline_program  # noqa: E402


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reciprocal_s3_fourmul_ir(prog, u, v, w, one, cutoff=3):
    """Use s2 = uv + w(u+v), then t = (uv)w in the exact S3 identity."""
    uv = build.pbMulIr(prog, u, v, pair.N, pair.TAPS, cutoff)
    uv_sum = pair.xor_vectors(prog, u, v)
    w_sum = build.pbMulIr(prog, w, uv_sum, pair.N, pair.TAPS, cutoff)
    triple = build.pbMulIr(prog, uv, w, pair.N, pair.TAPS, cutoff)
    first = pair.xor_vectors(prog, uv_sum, w)
    second = pair.xor_vectors(prog, uv, w_sum, first)
    second[0] = prog.xor(second[0], one)
    term = build.pbMulIr(prog, triple, second, pair.N, pair.TAPS, cutoff)
    square = build.pbSqrIr(prog, pair.xor_vectors(prog, triple, first),
                           pair.N, pair.TAPS)
    return pair.xor_vectors(prog, square, term)


def build_program():
    prog = pair.new_program()
    one = prog.addInput("one", 0)
    roots = []
    rotated = []
    for slot, rotation in enumerate(pair.ROTATIONS):
        pair_roots, z = pair.pair_ir(prog, slot, one, cutoff=3)
        roots.extend(pair_roots)
        rotated.append(pair.rotate_ir(prog, z, rotation))
    intermediates = [[prog.addInput("t%d" % index, bit)
                      for bit in range(pair.N)] for index in range(6)]
    target = [prog.addInput("target", bit) for bit in range(pair.N)]
    running = rotated[0]
    for index in range(1, 8):
        output = intermediates[index-1] if index < 7 else target
        roots.extend(reciprocal_s3_fourmul_ir(prog, running, rotated[index],
                                              output, one, cutoff=3))
        running = output
    return prog, roots


def assign_bits(values, name, value):
    values.update({(name, bit): (value >> bit) & 1 for bit in range(pair.N)})


def main():
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    paths = {"script": Path(__file__), "pair_circuit": BASE / "fixed_pair_circuit.py",
             "baseline_preflight": BASE / "full_preflight.py",
             "baseline_result": BASE / "full_preflight_result.json",
             "derive": BASE / "derive_result.json",
             "planted_chain": BASE / "planted_chain_result.json",
             "ordinary_target": BASE / "target_preimages.json",
             "build": ROOT / "ecc2k130/codegen/build.py",
             "ir": ROOT / "ecc2k130/codegen/ir.py"}
    for name, path in paths.items():
        assert protocol["source_sha256"][name] == digest(path), name
    baseline, baseline_roots = baseline_program()
    improved, roots = build_program()
    assert len(roots) == len(baseline_roots) == 15*pair.N
    baseline_count = baseline.opCount(baseline_roots)
    improved_count = improved.opCount(roots)
    assert baseline_count == json.loads(paths["baseline_result"].read_text())["ir_live_ops"]
    assert improved_count < baseline_count

    derive = json.loads(paths["derive"].read_text())
    planted = json.loads(paths["planted_chain"].read_text())
    ordinary = json.loads(paths["ordinary_target"].read_text())
    values = {("one", 0): 1}
    for item in derive["selected"]:
        slot = item["slot"]
        code = pair.selector_code(item["masks"][0])
        values.update({("a%d" % slot, bit): (code >> bit) & 1 for bit in range(17)})
        assign_bits(values, "z%d" % slot, item["unrotated_pair_output_z"])
    for index, value in enumerate(planted["intermediate_z"]):
        assign_bits(values, "t%d" % index, value)
    assign_bits(values, "target", planted["raw_target_z"])
    old_planted = baseline.evaluate(values, baseline_roots)
    new_planted = improved.evaluate(values, roots)
    assert old_planted == new_planted and not any(new_planted)
    assign_bits(values, "target", ordinary["preimages"][0]["reciprocal_x_z"])
    old_ordinary = baseline.evaluate(values, baseline_roots)
    new_ordinary = improved.evaluate(values, roots)
    assert old_ordinary == new_ordinary and any(new_ordinary)
    result = {"status": "PASS_FOUR_MULTIPLICATION_RECIPROCAL_S3_IR",
              "curve_id": "EC1N131Ckb1heb5f1998f20b",
              "workload_id": ordinary["workload_id"],
              "baseline_field_multiplications_per_link": 5,
              "new_field_multiplications_per_link": 4,
              "pair_slots": 8, "s3_links": 7, "root_count": len(roots),
              "baseline_live_ops": baseline_count,
              "new_live_ops": improved_count,
              "baseline_pair_live_ops": baseline.opCount(baseline_roots[:8*pair.N]),
              "new_pair_live_ops": improved.opCount(roots[:8*pair.N]),
              "baseline_link_live_ops": baseline.opCount(baseline_roots[8*pair.N:]),
              "new_link_live_ops": improved.opCount(roots[8*pair.N:]),
              "planted_failed_roots": sum(new_planted),
              "ordinary_target_with_planted_leaves_failed_roots": sum(new_ordinary),
              "source_sha256": {name: digest(path) for name, path in paths.items()},
              "protocol_sha256": digest(protocol_path)}
    with (HERE / "result.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"],
                      "baseline_live_ops": baseline_count,
                      "new_live_ops": improved_count,
                      "baseline_link_live_ops": result["baseline_link_live_ops"],
                      "new_link_live_ops": result["new_link_live_ops"]}))


if __name__ == "__main__":
    main()
