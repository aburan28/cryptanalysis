"""Build the eight-pair reciprocal IR and evaluate a complete curve witness."""

import hashlib
import json
import resource
import time
from pathlib import Path

import fixed_pair_circuit as pair


HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def set_bits(values, name, value):
    values.update({(name, bit): value >> bit & 1 for bit in range(pair.N)})


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
        roots.extend(pair.reciprocal_s3_ir(prog, running, rotated[index],
                                           output, one, cutoff=3))
        running = output
    return prog, roots


def main():
    protocol = json.loads((HERE / "full_preflight_protocol.json").read_text())
    paths = {"script": Path(__file__), "circuit": HERE / "fixed_pair_circuit.py",
             "derive": HERE / "derive_result.json",
             "planted_chain": HERE / "planted_chain_result.json",
             "ordinary_target": HERE / "target_preimages.json",
             "pair_audit": HERE / "pair_model_audit.json"}
    for name, path in paths.items():
        assert protocol["source_sha256"][name] == digest(path), name
    derive = json.loads(paths["derive"].read_text())
    planted = json.loads(paths["planted_chain"].read_text())
    ordinary = json.loads(paths["ordinary_target"].read_text())
    assert len(derive["selected"]) == 8
    assert len(planted["intermediate_z"]) == 6
    assert len(ordinary["preimages"]) == 4
    assert all(pair.gf_frobenius(item["unrotated_pair_output_z"], item["rotation"])
               == planted["pair_rotated_z"][item["slot"]]
               for item in derive["selected"])

    start = time.monotonic_ns()
    prog, roots = build_program()
    built = time.monotonic_ns()
    assert len(roots) == 15*pair.N
    values = {("one", 0): 1}
    for item in derive["selected"]:
        slot = item["slot"]
        code = pair.selector_code(item["masks"][0])
        values.update({("a%d" % slot, bit): code >> bit & 1 for bit in range(17)})
        set_bits(values, "z%d" % slot, item["unrotated_pair_output_z"])
    for index, z in enumerate(planted["intermediate_z"]):
        set_bits(values, "t%d" % index, z)
    set_bits(values, "target", planted["raw_target_z"])
    planted_roots = prog.evaluate(values, roots)
    assert len(planted_roots) == 15*pair.N and not any(planted_roots)
    set_bits(values, "target", ordinary["preimages"][0]["reciprocal_x_z"])
    ordinary_control_failures = sum(prog.evaluate(values, roots))
    assert ordinary_control_failures > 0
    checked = time.monotonic_ns()
    result = {"status": "PASS_EIGHT_PAIR_N131_TARGET_CONDITIONED_IR_PREFLIGHT",
              "candidate_id": None, "curve_id": "EC1N131Ckb1heb5f1998f20b",
              "source_dimension": 18, "fixed_seed_mask": pair.SEED,
              "pair_slots": 8, "raw_curve_summands": 16,
              "pair_roots": 8*pair.N, "reciprocal_s3_roots": 7*pair.N,
              "ir_total_nodes": len(prog.ops), "ir_live_ops": prog.opCount(roots),
              "planted_failed_roots": sum(planted_roots),
              "ordinary_target_with_planted_leaves_failed_roots": ordinary_control_failures,
              "phase_ns": {"build_reusable_ir": built-start,
                           "evaluate_planted_and_ordinary_controls": checked-built},
              "peak_process_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              "source_sha256": {name: digest(path) for name, path in paths.items()},
              "protocol_sha256": digest(HERE / "full_preflight_protocol.json")}
    with (HERE / "full_preflight_result.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"], "ir_live_ops": result["ir_live_ops"],
                      "build_ir_s": result["phase_ns"]["build_reusable_ir"]/1e9,
                      "peak_rss_bytes": result["peak_process_rss_bytes"]}))


if __name__ == "__main__":
    main()
