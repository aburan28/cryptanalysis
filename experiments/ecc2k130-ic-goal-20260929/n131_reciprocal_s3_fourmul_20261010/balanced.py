"""Balance the seven four-product S3 links over the same eight pair slots."""

import hashlib
import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "n131_fixed_seed_eight_pair_circuit_20261010"
sys.path.insert(0, str(BASE))
import fixed_pair_circuit as pair  # noqa: E402
from fourmul import build_program as chain_program  # noqa: E402
from fourmul import reciprocal_s3_fourmul_ir  # noqa: E402


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


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
    for slot, (left, right) in enumerate(((0, 1), (2, 3), (4, 5), (6, 7))):
        roots.extend(reciprocal_s3_fourmul_ir(prog, rotated[left],
                                              rotated[right], intermediates[slot],
                                              one, cutoff=3))
    roots.extend(reciprocal_s3_fourmul_ir(prog, intermediates[0],
                                          intermediates[1], intermediates[4],
                                          one, cutoff=3))
    roots.extend(reciprocal_s3_fourmul_ir(prog, intermediates[2],
                                          intermediates[3], intermediates[5],
                                          one, cutoff=3))
    roots.extend(reciprocal_s3_fourmul_ir(prog, intermediates[4],
                                          intermediates[5], target, one,
                                          cutoff=3))
    return prog, roots


def assign_bits(values, name, value):
    values.update({(name, bit): (value >> bit) & 1 for bit in range(pair.N)})


def main():
    protocol_path = HERE / "balanced_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    paths = {"script": Path(__file__), "fourmul": HERE / "fourmul.py",
             "fourmul_result": HERE / "result.json",
             "balanced_planted": HERE / "balanced_planted_result.json",
             "derive": BASE / "derive_result.json",
             "planted_chain": BASE / "planted_chain_result.json",
             "ordinary_target": BASE / "target_preimages.json",
             "pair_circuit": BASE / "fixed_pair_circuit.py"}
    for name, path in paths.items():
        assert protocol["source_sha256"][name] == digest(path), name
    chain, chain_roots = chain_program()
    prog, roots = build_program()
    assert len(roots) == len(chain_roots) == 15*pair.N
    balanced_control = json.loads(paths["balanced_planted"].read_text())
    planted = json.loads(paths["planted_chain"].read_text())
    derive = json.loads(paths["derive"].read_text())
    ordinary = json.loads(paths["ordinary_target"].read_text())
    assert balanced_control["raw_target_z"] == planted["raw_target_z"]
    values = {("one", 0): 1}
    for item in derive["selected"]:
        slot = item["slot"]
        code = pair.selector_code(item["masks"][0])
        values.update({("a%d" % slot, bit): (code >> bit) & 1 for bit in range(17)})
        assign_bits(values, "z%d" % slot, item["unrotated_pair_output_z"])
    for index, value in enumerate(balanced_control["balanced_intermediate_z"]):
        assign_bits(values, "t%d" % index, value)
    assign_bits(values, "target", planted["raw_target_z"])
    planted_roots = prog.evaluate(values, roots)
    assert not any(planted_roots)
    assign_bits(values, "target", ordinary["preimages"][0]["reciprocal_x_z"])
    ordinary_failed_roots = sum(prog.evaluate(values, roots))
    assert ordinary_failed_roots > 0
    result = {"status": "PASS_BALANCED_FOURMUL_EIGHT_PAIR_IR",
              "curve_id": "EC1N131Ckb1heb5f1998f20b",
              "workload_id": ordinary["workload_id"],
              "root_count": len(roots), "tree_depth": 3,
              "chain_depth": 7,
              "chain_live_ops": chain.opCount(chain_roots),
              "balanced_live_ops": prog.opCount(roots),
              "planted_failed_roots": sum(planted_roots),
              "ordinary_target_with_planted_leaves_failed_roots": ordinary_failed_roots,
              "source_sha256": {name: digest(path) for name, path in paths.items()},
              "protocol_sha256": digest(protocol_path)}
    with (HERE / "balanced_result.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"],
                      "chain_live_ops": result["chain_live_ops"],
                      "balanced_live_ops": result["balanced_live_ops"]}))


if __name__ == "__main__":
    main()
