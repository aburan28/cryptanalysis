#!/usr/bin/env python3
"""Bind geometry, indexed row, three SAT controls, and bounded searches."""

import hashlib
import json
import platform
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((HERE / name).read_text())


def main():
    screen, join, replay, protocol = [read(x) for x in
                                      ("screen.json", "join_result.json",
                                       "verification.json", "protocol.json")]
    assert screen["source_sha256"] == sha(HERE / "screen.py")
    assert screen["actual_usable_points_B"] == 512
    assert screen["signed_frobenius_columns_K"] == 26
    assert join["status"] == "VERIFIED_EIGHT_POINT_ROW"
    assert replay["status"] == "PASS"
    assert replay["join_receipt_sha256"] == sha(HERE / "join_result.json")
    assert replay["distinct_folded_columns"] == 8
    source_map = {"screen": HERE / "screen.json", "join": HERE / "join.cpp",
                  "included_arithmetic": HERE / "../../koblitz-s5-invariant-20260924/three_pair_s7_native.cpp",
                  "input": HERE / "input.txt", "prepare": HERE / "prepare.py"}
    assert {key: sha(path) for key, path in source_map.items()} == protocol["source_sha256"]
    assert join["target"] == screen["public_target"]

    variants = []
    for name, driver, circuit in [
        ("reciprocal", "sat.py", "reciprocal_circuit.py"),
        ("sparse", "sparse_sat.py", "reciprocal_sparse_circuit.py"),
        ("trace_sparse", "trace_sparse_sat.py", "reciprocal_trace_sparse_circuit.py")]:
        p = read(("sat_protocol.json" if name == "reciprocal" else name + "_sat_protocol.json"))
        c = read(name + "_control.json")
        r = read(name + "_result.json")
        source = {"sat": HERE / driver, "circuit": HERE / circuit,
                  "base": BASE / "run_n41_disjoint_s5_sat.py",
                  "assignment": BASE / "check_n41_lowpower_w8_s6_witness.py",
                  "geometry": BASE / "n41_two_free_pair_occupancy_20261009/geometry_snapshot.json",
                  "screen": HERE / "screen.json", "join": HERE / "join_result.json",
                  "solver": Path("/opt/homebrew/bin/cryptominisat5"),
                  "runtime": HERE / "sage_runtime_info.json",
                  "formula": HERE / ("reciprocal_public.xcnf" if name == "reciprocal" else name + "_public.xcnf"),
                  "control": HERE / (name + "_control.json")}
        assert {key: sha(path) for key, path in source.items()} == p["source_sha256"]
        assert c["status"] == "PASS_FULL_FORMULA_AND_GROUP_CONTROL"
        assert c["xcnf_check"] == {"cnf_clauses": c["formula"]["clauses"],
                                    "xor_rows": c["formula"]["xor_rows"]}
        assert r["formula_sha256"] == sha(source["formula"])
        assert r["status"] == "CENSORED_TIME"
        assert r["stop_reason"] == "SOLVER_WALL_CAP"
        assert r["status_lines"] == [] and r["model_lines"] == 0
        assert r["solver_wall_seconds"] <= 120
        stdout = HERE / (name + "_solver.stdout.txt")
        stderr = HERE / (name + "_solver.stderr.txt")
        assert r["stdout_sha256"] == sha(stdout)
        assert r["stderr_sha256"] == sha(stderr)
        lines = stdout.read_text(errors="replace").splitlines()
        restarts = [line for line in lines if line.startswith("c rst ")]
        assert restarts and not stderr.read_text()
        variants.append({"name": name, "formula": c["formula"],
                         "solver_wall_seconds": r["solver_wall_seconds"],
                         "sampled_peak_rss_bytes": r["sampled_peak_rss_bytes"],
                         "active_search_restart_lines": len(restarts),
                         "last_search_progress_line": restarts[-1],
                         "status": r["status"]})
    out = {"status": "PASS", "candidate_id": None,
           "public_target": screen["public_target"],
           "geometry": {"B": 512, "K": 26, "raw_reciprocal_audits": 32,
                        "S3_group_checks": 256},
           "indexed_relation": {"status": join["status"],
                                "distinct_columns": replay["distinct_folded_columns"],
                                "setup_ns": join["reusable_setup_ns"],
                                "target_lookup_ns": join["stage_online_wall_ns"],
                                "peak_rss_bytes": join["peak_rss_bytes"]},
           "variants": variants,
           "source_sha256": sha(Path(__file__)),
           "binary_sha256": sha(HERE / "join"),
           "compiler": subprocess.check_output(["clang++", "--version"], text=True).splitlines()[0],
           "host": {"machine": platform.machine(), "system": platform.system(),
                    "release": platform.release()}}
    (HERE / "audit.json").write_text(json.dumps(out, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": out["status"], "variants": [
        {"name": v["name"], "and_gates": v["formula"]["and_gates"],
         "status": v["status"], "search_restarts": v["active_search_restart_lines"]}
        for v in variants]}, indent=2))


if __name__ == "__main__":
    main()
