#!/usr/bin/env sage -python
"""Independent prefix geometry, constructed control, and query audit."""

import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OLD = ROOT / "n131_w16_fivepair_sat_gate_20261010"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


old = load("joint_audit_old_run", OLD / "fivepair_run.py")


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    prefix_record = json.loads((HERE / "prefixes.json").read_text())
    prefixes = prefix_record["prefixes"]
    protocol = json.loads((HERE / "protocol.json").read_text())
    control = json.loads((HERE / "control.json").read_text())
    query = json.loads((HERE / "query.json").read_text())
    prior = json.loads((OLD / "fivepair_input.json").read_text())
    assert protocol["source_sha256"] == {
        "runner": sha(HERE / "run.py"), "circuit": sha(HERE / "circuit.py"),
        "preparation": sha(HERE / "prepare.py"), "prefixes": sha(HERE / "prefixes.json"),
        "runtime": sha(HERE / "sage_runtime_info.json"),
        "solver": sha(Path("/opt/homebrew/bin/cryptominisat5")),
        "old_runner": sha(OLD / "fivepair_run.py"),
        "old_lift": sha(OLD / "fivepair_lift.py"),
        "old_control": sha(OLD / "fivepair_control_result.json"),
        "bdd": sha(ROOT / "n131_w16_bdd_membership_20261010" / "bdd.py"),
        "bdd_core": sha(ROOT / "n131_w16_bdd_membership_20261010" / "core.py")}
    assert prefix_record["target_q"] == protocol["target_q"] == prior["original_target_q"]
    assert len(prefixes) == 32
    columns, field, curve, _, _ = old.experiment.run.source()
    _, _, _, basis_w, basis_u = old.lift.original.source()
    target = tuple(protocol["target_q"])
    seen = set()
    for row in prefixes:
        a, b = row["masks"]
        assert a in columns and b in columns and columns[a] != columns[b]
        assert row["columns"] == [columns[a], columns[b]]
        leaves = [old.lift.original.atom(field, curve, basis_w, basis_u, a),
                  old.lift.original.atom(field, curve, basis_w, basis_u, b)]
        leaves = [curve.neg(point) if sign else point
                  for point, sign in zip(leaves, row["signs"])]
        assert row["raw_leaves"] == [list(point) for point in leaves]
        raw = curve.add(*leaves)
        assert row["raw_sum"] == list(raw)
        projected = curve.mul(4, raw)
        assert row["projected_sum"] == list(projected)
        assert tuple(projected) not in seen
        seen.add(tuple(projected))
        residual = curve.add(target, curve.neg(projected))
        assert row["residual_q"] == list(residual)
        preimages = old.experiment.run.prior.prior.old.target_preimages(curve, residual)
        assert row["preimages"] == [list(point) for point in preimages]
        assert row["target_reciprocals"] == [field.inv(point[0]) for point in preimages]
    assert prefixes[0]["raw_sum"] == prior["first_pair_raw"]
    assert prefixes[0]["residual_q"] == prior["residual_target_q"]
    assert control["status"] == "PASS_JOINT_32_PREFIX_FULL_XCNF_AND_GROUP_CONTROL"
    assert control["full_assignment_check"] == {
        "cnf_clauses": control["formula"]["cnf_clauses"],
        "xor_rows": control["formula"]["native_xor_rows"]}
    assert control["group_lift_status"] == "GROUP_LIFT_FOUND"
    assert control["source_sha256"] == query["source_sha256"] == protocol["source_sha256"]
    assert control["formula"] == query["formula"]
    assert query["target_q"] == protocol["target_q"]
    assert query["output_sha256"] == {
        "stdout": sha(HERE / "solver.stdout.txt"),
        "stderr": sha(HERE / "solver.stderr.txt")}
    assert query["phase_seconds"]["total"] <= protocol["total_cap_seconds"]
    assert query["sampled_peak_combined_rss_bytes"] < protocol["rss_cap_bytes"]
    stdout = (HERE / "solver.stdout.txt").read_text(errors="replace")
    restart_lines = sum(line.startswith("c rst ") for line in stdout.splitlines())
    if query["status"] == "CENSORED_TIME":
        assert query["stop_reason"] == "SAFE_WALL_STOP"
        assert query["solver_status_lines"] == [] and query["model_lines"] == 0
        assert restart_lines > 0
    elif query["status"] == "GROUP_LIFT_FOUND":
        assert query["model_check"] == {
            "cnf_clauses": query["formula"]["cnf_clauses"],
            "xor_rows": query["formula"]["native_xor_rows"]}
        lifted = json.loads((HERE / "query_group_lift.json").read_text())
        assert lifted["status"] == "GROUP_LIFT_FOUND"
        prefix = prefixes[query["selected_choice"] // 4]
        assert any(curve.add(tuple(prefix["projected_sum"]),
                             tuple(sol["projected_sum"])) == target
                   for sol in lifted["solutions"])
    else:
        raise AssertionError("unexpected query status")
    result = {"status": "PASS_JOINT_PREFIX_GEOMETRY_XCNF_AND_QUERY_AUDIT",
              "prefix_count": len(prefixes), "target_branch_count": 4*len(prefixes),
              "known_control_choice": control["known_control_choice"],
              "query_status": query["status"], "solver_restart_lines": restart_lines,
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
                      "restart_lines": restart_lines}))


if __name__ == "__main__":
    main()
