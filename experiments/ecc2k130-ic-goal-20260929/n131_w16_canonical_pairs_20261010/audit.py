#!/usr/bin/env sage -python
"""Independent pair-swap orbit, group, and bounded-search receipt audit."""

import hashlib
import importlib.util
import itertools
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
JOINT = ROOT / "n131_w16_joint_prefix_20261010"
OLD = ROOT / "n131_w16_fivepair_sat_gate_20261010"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


old = load("canonical_audit_old", OLD / "fivepair_run.py")


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    control = json.loads((HERE / "control.json").read_text())
    query = json.loads((HERE / "query.json").read_text())
    old_control = json.loads((JOINT / "control.json").read_text())
    witness = json.loads((OLD / "fivepair_input.json").read_text())
    lifted = json.loads((OLD / "fivepair_control_group_lift.json").read_text())
    assert protocol["source_sha256"] == {
        "runner": sha(HERE / "run.py"), "canonical": sha(HERE / "canonical.py"),
        "joint_runner": sha(JOINT / "run.py"),
        "joint_circuit": sha(JOINT / "circuit.py"),
        "joint_protocol": sha(JOINT / "protocol.json"),
        "joint_control": sha(JOINT / "control.json"),
        "prefixes": sha(JOINT / "prefixes.json"),
        "original_witness": sha(OLD / "fivepair_input.json"),
        "solver": sha(Path("/opt/homebrew/bin/cryptominisat5")),
        "runtime": sha(HERE / "sage_runtime_info.json")}
    assert lifted["status"] == "GROUP_LIFT_FOUND" and len(lifted["solutions"]) >= 1
    solution = lifted["solutions"][0]
    masks = witness["remaining_masks"]
    assert solution["masks"] == masks
    assert all(masks[i] != masks[i+1] for i in range(0, 10, 2))
    columns, field, curve, _, _ = old.experiment.run.source()
    target = tuple(witness["residual_target_q"])
    orbit = set()
    canonical_rows = []
    for swaps in itertools.product((0, 1), repeat=5):
        variant_masks = list(masks)
        leaves = [tuple(point) for point in solution["raw_leaves"]]
        for pair, swap in enumerate(swaps):
            if swap:
                i = 2*pair
                variant_masks[i], variant_masks[i+1] = variant_masks[i+1], variant_masks[i]
                leaves[i], leaves[i+1] = leaves[i+1], leaves[i]
        assert all(variant_masks[i] in columns for i in range(10))
        assert all(curve.add(leaves[i], leaves[i+1]) ==
                   curve.add(tuple(solution["raw_leaves"][i]),
                             tuple(solution["raw_leaves"][i+1]))
                   for i in range(0, 10, 2))
        total = None
        for leaf in leaves:
            total = curve.add(total, leaf)
        assert curve.mul(4, total) == target
        orbit.add(tuple(variant_masks))
        if all(variant_masks[i] < variant_masks[i+1] for i in range(0, 10, 2)):
            canonical_rows.append(variant_masks)
    assert len(orbit) == 32 and canonical_rows == [control["canonical_control_masks"]]
    assert control["status"] == "PASS_CANONICAL_JOINT_FULL_XCNF_AND_GROUP_CONTROL"
    assert control["full_assignment_check"] == {
        "cnf_clauses": control["formula"]["cnf_clauses"],
        "xor_rows": control["formula"]["native_xor_rows"]}
    assert control["group_lift_status"] == "GROUP_LIFT_FOUND"
    assert control["formula"]["variables"] == old_control["formula"]["variables"] + 75
    assert control["formula"]["cnf_clauses"] == old_control["formula"]["cnf_clauses"] + 300
    assert control["formula"]["native_xor_rows"] == old_control["formula"]["native_xor_rows"]
    assert query["formula"] == control["formula"]
    assert query["source_sha256"] == control["source_sha256"] == protocol["source_sha256"]
    assert query["output_sha256"] == {
        "stdout": sha(HERE / "solver.stdout.txt"),
        "stderr": sha(HERE / "solver.stderr.txt")}
    assert query["phase_seconds"]["total"] <= protocol["total_cap_seconds"]
    assert query["sampled_peak_combined_rss_bytes"] < protocol["rss_cap_bytes"]
    stdout = (HERE / "solver.stdout.txt").read_text(errors="replace")
    restarts = sum(line.startswith("c rst ") for line in stdout.splitlines())
    if query["status"] == "CENSORED_TIME":
        assert query["stop_reason"] == "SAFE_WALL_STOP"
        assert query["solver_status_lines"] == [] and query["model_lines"] == 0
        assert restarts > 0
    elif query["status"] == "GROUP_LIFT_FOUND":
        assert query["model_check"] == {
            "cnf_clauses": query["formula"]["cnf_clauses"],
            "xor_rows": query["formula"]["native_xor_rows"]}
        recovered = json.loads((HERE / "query_group_lift.json").read_text())
        assert recovered["status"] == "GROUP_LIFT_FOUND"
        prefixes = json.loads((JOINT / "prefixes.json").read_text())["prefixes"]
        prefix = prefixes[query["selected_choice"] // 4]
        assert any(curve.add(tuple(prefix["projected_sum"]),
                             tuple(row["projected_sum"])) == tuple(protocol["target_q"])
                   for row in recovered["solutions"])
    else:
        raise AssertionError("unexpected solver terminal status")
    result = {"status": "PASS_CANONICAL_ORBIT_GROUP_XCNF_AND_QUERY_AUDIT",
              "pair_swap_orbit_size": len(orbit),
              "canonical_representatives": len(canonical_rows),
              "query_status": query["status"],
              "solver_restart_lines": restarts,
              "query_total_wall_seconds": query["phase_seconds"]["total"],
              "sampled_solver_cpu_seconds": query["sampled_solver_cpu_seconds"],
              "source_sha256": {"audit": sha(HERE / "audit.py"),
                                "protocol": sha(HERE / "protocol.json"),
                                "control": sha(HERE / "control.json"),
                                "query": sha(HERE / "query.json")}}
    with (HERE / "audit.json").open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": result["status"],
                      "query_status": query["status"],
                      "restarts": restarts}))


if __name__ == "__main__":
    main()
