#!/usr/bin/env python3
"""Independently replay Q1464 work limits, model bytes, and input identities."""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1460 = PARENT / "q20261011_wdsat_shared_prefix"
Q1463 = PARENT / "q20261011_wdsat_ordinary"
sys.path.insert(0, str(PARENT / "q1419_partial_pin"))
from verify_archive import check_serialized_xcnf  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    protocol = json.loads((HERE / "protocol.json").read_text())
    freeze = json.loads((HERE / "freeze.json").read_text())
    build = json.loads((HERE / "build_receipt.json").read_text())
    parent = json.loads((Q1460 / "build_receipt.json").read_text())
    profiles = json.loads((PARENT / "q1419_partial_pin/protocol.json").read_text())["profiles"]
    assert protocol["proposal_id"] == freeze["proposal_id"] == build["proposal_id"] == "Q1464"
    assert protocol["candidate_id"] is protocol["run_id"] is freeze["candidate_id"] is build["candidate_id"] is None
    assert protocol["isogeny"] == "none"
    assert freeze["protocol_sha256"] == sha(HERE / "protocol.json")
    assert freeze["freeze_source_sha256"] == sha(HERE / "freeze.py")
    assert freeze["build_source_sha256"] == sha(HERE / "build.py")
    assert freeze["parent_build_receipt_sha256"] == sha(Q1460 / "build_receipt.json")
    assert freeze["control_profiles_protocol_sha256"] == sha(PARENT / "q1419_partial_pin/protocol.json")
    assert build["freeze_sha256"] == sha(HERE / "freeze.json")
    assert build["upstream_commit"] == freeze["upstream_commit"] == protocol["solver"]["upstream_commit"]
    incident = json.loads((HERE / "pre_fix_incident.json").read_text())
    assert incident["source_sha256"] == sha(HERE / "run_pre_fix.py")
    interrupted = HERE / "runs/pre_fix/n83_full_lock/plain"
    assert not (interrupted / "receipt.json").exists()
    assert incident["archived_solver_stdout_sha256"] == sha(interrupted / "solver.stdout.txt")
    assert incident["archived_solver_stderr_sha256"] == sha(interrupted / "solver.stderr.txt")
    for variant in ("plain", "xor_gauss"):
        old = HERE / "runs/pre_fix/n53_full_lock" / variant
        old_receipt = json.loads((old / "receipt.json").read_text())
        assert old_receipt["runner_sha256"] == incident["source_sha256"]
        assert old_receipt["stdout_sha256"] == sha(old / "solver.stdout.txt")
        assert old_receipt["stderr_sha256"] == sha(old / "solver.stderr.txt")
    rows = []
    for degree in (53, 83):
        name = f"n{degree}"
        data = freeze["cells"][name]
        binary = build["per_degree"][name]
        assert binary["return_code"] == 0
        assert binary["config"] == parent["per_degree"][name]["config"]
        assert binary["branch_patch"]["branch_cap"] == protocol["limits"]["left_branch_attempts_per_run"]
        assert binary["branch_patch"]["instrumented_sites"] == 4
        assert sha(Path(binary["binary_path"])) == binary["binary_sha256"]
        assert sha(Path(binary["binary_path"]).parent / "src/wdsat.c") == binary[
            "branch_patch"]["wdsat_c_sha256"]
        assert data["curve_id"] == profiles[str(degree)]["curve_id"]
        assert data["factor_base_actual_B"] == profiles[str(degree)]["factor_base_actual_B"]
        assert data["factor_base_enumerated_set_sha256"] == profiles[str(degree)]["factor_base_enumerated_set_sha256"]
        for kind in ("full_lock", "ordinary"):
            if kind == "ordinary":
                archive = Q1463 / f"{name}_ordinary.xcnf.gz"
                source = PARENT / "runs" / f"{name}_q{1410 if degree == 53 else 1408}_ordinary.xcnf.gz"
                archive_key, source_key = "ordinary_archive_sha256", "ordinary_source_archive_sha256"
                workload_id = data["ordinary_workload_id"]
                target = data["public_target"]
                variables = data["ordinary_variables"]
            else:
                archive = Q1460 / f"{name}_full_lock.xcnf.gz"
                source = PARENT / "q1419_partial_pin/runs" / f"{name}_full_lock/system.xcnf.gz"
                archive_key, source_key = "control_archive_sha256", "control_source_archive_sha256"
                workload_id = profiles[str(degree)]["workload_id"]
                target = profiles[str(degree)]["public_target"]
                variables = data["control_variables"]
            assert sha(archive) == data[archive_key]
            assert sha(source) == data[source_key]
            transformed = gzip.decompress(archive.read_bytes())
            original = gzip.decompress(source.read_bytes())
            for variant in protocol["solver"]["variants"]:
                run_dir = HERE / "runs" / f"{name}_{kind}" / variant
                if not (run_dir / "receipt.json").exists():
                    continue
                receipt = json.loads((run_dir / "receipt.json").read_text())
                stdout = (run_dir / "solver.stdout.txt").read_bytes()
                stderr = (run_dir / "solver.stderr.txt").read_bytes()
                stderr_text = stderr.decode("utf-8", "replace")
                assert receipt["proposal_id"] == "Q1464"
                assert receipt["candidate_id"] is receipt["run_id"] is None
                assert receipt["isogeny"] == "none"
                assert receipt["degree"] == degree and receipt["kind"] == kind
                assert receipt["variant"] == variant
                assert receipt["ordinary_query"] == (kind == "ordinary")
                assert receipt["curve_id"] == data["curve_id"]
                assert receipt["workload_id"] == workload_id
                assert receipt["public_target"] == target
                assert receipt["factor_base_actual_B"] == data["factor_base_actual_B"]
                assert receipt["factor_base_folded_columns_K"] == data["factor_base_folded_columns_K"]
                assert receipt["factor_base_enumerated_set_sha256"] == data["factor_base_enumerated_set_sha256"]
                assert receipt["protocol_sha256"] == sha(HERE / "protocol.json")
                assert receipt["freeze_sha256"] == sha(HERE / "freeze.json")
                assert receipt["build_receipt_sha256"] == sha(HERE / "build_receipt.json")
                assert receipt["runner_sha256"] == sha(HERE / "run.py")
                assert receipt["archive_sha256"] == sha(archive)
                assert receipt["source_archive_sha256"] == sha(source)
                assert receipt["binary_sha256"] == binary["binary_sha256"]
                assert receipt["stdout_sha256"] == hashlib.sha256(stdout).hexdigest()
                assert receipt["stderr_sha256"] == hashlib.sha256(stderr).hexdigest()
                assert receipt["search_started"] == ("Q1458_SEARCH_START" in stderr_text)
                assert receipt["after_xor_init"] == ("Q1458_AFTER_XOR_INIT" in stderr_text)
                checkpoints = [int(value) for value in re.findall(r"^Q1464_BRANCH (\d+)$",
                                                                 stderr_text, re.MULTILINE)]
                assert checkpoints == receipt["branch_checkpoints"]
                assert all(value == 1 << index for index, value in enumerate(checkpoints))
                assert receipt["branch_lower_bound"] == (checkpoints[-1] if checkpoints else 0)
                assert receipt["wall_limit_seconds"] == protocol["limits"]["wall_seconds_per_run"]
                assert receipt["left_branch_attempt_limit"] == protocol["limits"]["left_branch_attempts_per_run"]
                assert receipt["complete_solve_work_log2"] is None
                assert receipt["natural_relation_yield_estimate"] is None
                if receipt["status"] == "SAT_REPLAYED_XCNF":
                    models = [line for line in stdout.decode("ascii").splitlines()
                              if len(line) == variables and set(line) <= {"0", "1"}]
                    assert len(models) == receipt["model_count"] == 1
                    model = {i + 1: ch == "1" for i, ch in enumerate(models[0])}
                    original_vars = int(original.splitlines()[0].split()[2])
                    replay_derived = check_serialized_xcnf(transformed, model)
                    replay_original = check_serialized_xcnf(original, {i: model[i]
                                                                      for i in range(1, original_vars + 1)})
                    for key, replay in (("derived", replay_derived), ("original", replay_original)):
                        assert all(receipt["model_replay"][key][field] == value
                                   for field, value in replay.items())
                    assert receipt["return_code"] == 0 and not receipt["timed_out"]
                elif receipt["status"] == "BRANCH_CAP_REACHED":
                    cap = protocol["limits"]["left_branch_attempts_per_run"]
                    assert receipt["return_code"] == 42 and not receipt["timed_out"]
                    assert receipt["branch_exact_at_cap"] == cap
                    assert f"Q1464_BRANCH_CAP {cap}" in stderr_text
                    assert receipt["search_started"]
                elif receipt["status"] == "WALL_CAP_SEARCH_STARTED":
                    assert receipt["timed_out"] and receipt["search_started"]
                else:
                    assert receipt["status"] in ("CENSORED_BEFORE_SEARCH", "PRODUCER_FAILURE",
                                                  "UNSAT_REPORTED_UNVERIFIED", "MODEL_REPLAY_FAILED",
                                                  "PRODUCER_FAILURE_NO_MODEL")
                rows.append({"degree": degree, "kind": kind, "variant": variant,
                             "status": receipt["status"],
                             "branch_lower_bound": receipt["branch_lower_bound"],
                             "user_cpu_seconds": receipt["user_cpu_seconds"],
                             "wall_seconds_exploratory": receipt["wall_seconds_exploratory"],
                             "receipt_sha256": sha(run_dir / "receipt.json")})
    output = {"proposal_id": "Q1464", "candidate_id": None,
              "status": "PASS", "runs": rows,
              "pre_fix_incident_sha256": sha(HERE / "pre_fix_incident.json"),
              "freeze_sha256": sha(HERE / "freeze.json"),
              "complete_solve_work_log2": None}
    (HERE / "verification.json").write_text(json.dumps(output, indent=2,
                                                        sort_keys=True) + "\n")
    print("PASS Q1464", len(rows), "runs")


if __name__ == "__main__":
    main()
