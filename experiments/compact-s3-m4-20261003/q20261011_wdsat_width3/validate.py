#!/usr/bin/env python3
"""Independently replay Q1465 width-three formulas and work-limit receipts."""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1464 = PARENT / "q20261011_wdsat_workprobe"
sys.path.insert(0, str(PARENT / "q1419_partial_pin"))
from verify_archive import check_serialized_xcnf  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    protocol = json.loads((HERE / "protocol.json").read_text())
    freeze = json.loads((HERE / "freeze.json").read_text())
    prepared = json.loads((HERE / "prepare_receipt.json").read_text())
    equivalence = json.loads((HERE / "equivalence_check.json").read_text())
    build = json.loads((HERE / "build_receipt.json").read_text())
    q1464_freeze = json.loads((Q1464 / "freeze.json").read_text())
    profiles = json.loads((PARENT / "q1419_partial_pin/protocol.json").read_text())["profiles"]
    assert protocol["proposal_id"] == freeze["proposal_id"] == prepared["proposal_id"] == build["proposal_id"] == "Q1465"
    assert protocol["candidate_id"] is protocol["run_id"] is freeze["candidate_id"] is prepared["candidate_id"] is build["candidate_id"] is None
    assert protocol["isogeny"] == "none"
    assert equivalence["status"] == "PASS"
    assert equivalence["source_sha256"] == sha(HERE / "check_equivalence.py")
    assert equivalence["transform_source_sha256"] == sha(HERE / "prepare.py")
    assert prepared["source_sha256"] == sha(HERE / "prepare.py")
    assert freeze["protocol_sha256"] == prepared["protocol_sha256"] == sha(HERE / "protocol.json")
    assert freeze["freeze_source_sha256"] == sha(HERE / "freeze.py")
    assert freeze["prepare_source_sha256"] == sha(HERE / "prepare.py")
    assert freeze["prepare_receipt_sha256"] == sha(HERE / "prepare_receipt.json")
    assert freeze["equivalence_check_sha256"] == sha(HERE / "equivalence_check.json")
    assert freeze["build_source_sha256"] == sha(HERE / "build.py")
    assert freeze["q1464_freeze_sha256"] == sha(Q1464 / "freeze.json")
    assert build["freeze_sha256"] == sha(HERE / "freeze.json")
    assert build["upstream_commit"] == protocol["solver"]["upstream_commit"]
    rows = []
    for degree in (53, 83):
        name = f"n{degree}"
        binary = build["per_degree"][name]
        assert binary["return_code"] == 0
        assert binary["branch_patch"]["branch_cap"] == protocol["limits"]["left_branch_attempts_per_run"]
        assert binary["branch_patch"]["instrumented_sites"] == 4
        assert sha(Path(binary["binary_path"])) == binary["binary_sha256"]
        assert sha(Path(binary["binary_path"]).parent / "src/wdsat.c") == binary["branch_patch"]["wdsat_c_sha256"]
        for kind in ("full_lock", "ordinary"):
            cell = f"{name}_{kind}"
            record = freeze["cells"][cell]
            item = prepared["cells"][cell]
            assert record["curve_id"] == q1464_freeze["cells"][name]["curve_id"]
            assert record["factor_base_actual_B"] == q1464_freeze["cells"][name]["factor_base_actual_B"]
            assert record["factor_base_enumerated_set_sha256"] == q1464_freeze["cells"][name]["factor_base_enumerated_set_sha256"]
            assert item["stats"]["derived_cnf_widths"] and max(map(int, item["stats"]["derived_cnf_widths"])) <= 3
            archive = HERE / f"{cell}.xcnf.gz"
            if kind == "ordinary":
                source = PARENT / "runs" / f"{name}_q{1410 if degree == 53 else 1408}_ordinary.xcnf.gz"
                target = record["public_target"]
                workload = record["workload_id"]
            else:
                source = PARENT / "q1419_partial_pin/runs" / f"{cell}/system.xcnf.gz"
                target = profiles[str(degree)]["public_target"]
                workload = profiles[str(degree)]["workload_id"]
            assert sha(archive) == record["derived_archive_sha256"] == item["derived_archive_sha256"]
            assert sha(source) == record["source_archive_sha256"] == item["source_archive_sha256"]
            derived = gzip.decompress(archive.read_bytes())
            original = gzip.decompress(source.read_bytes())
            assert hashlib.sha256(derived).hexdigest() == record["derived_raw_sha256"]
            for variant in protocol["solver"]["variants"]:
                run_dir = HERE / "runs" / cell / variant
                if not (run_dir / "receipt.json").exists():
                    continue
                receipt = json.loads((run_dir / "receipt.json").read_text())
                stdout = (run_dir / "solver.stdout.txt").read_bytes()
                stderr = (run_dir / "solver.stderr.txt").read_bytes()
                error_text = stderr.decode("utf-8", "replace")
                assert receipt["proposal_id"] == "Q1465"
                assert receipt["candidate_id"] is receipt["run_id"] is None
                assert receipt["isogeny"] == "none"
                assert (receipt["degree"], receipt["kind"], receipt["variant"]) == (degree, kind, variant)
                assert receipt["ordinary_query"] == (kind == "ordinary")
                assert receipt["curve_id"] == record["curve_id"]
                assert receipt["workload_id"] == workload and receipt["public_target"] == target
                assert receipt["factor_base_actual_B"] == record["factor_base_actual_B"]
                assert receipt["factor_base_folded_columns_K"] == record["factor_base_folded_columns_K"]
                assert receipt["factor_base_enumerated_set_sha256"] == record["factor_base_enumerated_set_sha256"]
                assert receipt["protocol_sha256"] == sha(HERE / "protocol.json")
                assert receipt["freeze_sha256"] == sha(HERE / "freeze.json")
                assert receipt["build_receipt_sha256"] == sha(HERE / "build_receipt.json")
                assert receipt["runner_sha256"] == sha(HERE / "run.py")
                assert receipt["archive_sha256"] == sha(archive)
                assert receipt["source_archive_sha256"] == sha(source)
                assert receipt["binary_sha256"] == binary["binary_sha256"]
                assert receipt["stdout_sha256"] == hashlib.sha256(stdout).hexdigest()
                assert receipt["stderr_sha256"] == hashlib.sha256(stderr).hexdigest()
                assert receipt["search_started"] == ("Q1458_SEARCH_START" in error_text)
                assert receipt["after_xor_init"] == ("Q1458_AFTER_XOR_INIT" in error_text)
                checkpoints = [int(x) for x in re.findall(r"^Q1464_BRANCH (\d+)$", error_text, re.MULTILINE)]
                assert checkpoints == receipt["branch_checkpoints"]
                assert all(x == 1 << index for index, x in enumerate(checkpoints))
                assert receipt["branch_lower_bound"] == (checkpoints[-1] if checkpoints else 0)
                assert receipt["left_branch_attempt_limit"] == protocol["limits"]["left_branch_attempts_per_run"]
                assert receipt["wall_limit_seconds"] == protocol["limits"]["wall_seconds_per_run"]
                assert receipt["natural_relation_yield_estimate"] is None
                assert receipt["complete_solve_work_log2"] is None
                if receipt["status"] == "SAT_REPLAYED_XCNF":
                    models = [line for line in stdout.decode("ascii").splitlines()
                              if len(line) == record["derived_variables"] and set(line) <= {"0", "1"}]
                    assert len(models) == receipt["model_count"] == 1
                    model = {i + 1: ch == "1" for i, ch in enumerate(models[0])}
                    replays = {"derived": check_serialized_xcnf(derived, model),
                               "original": check_serialized_xcnf(original, {i: model[i]
                                                                           for i in range(1, record["original_variables"] + 1)})}
                    for key, replay in replays.items():
                        assert all(receipt["model_replay"][key][field] == value
                                   for field, value in replay.items())
                    assert receipt["return_code"] == 0 and not receipt["timed_out"]
                elif receipt["status"] == "BRANCH_CAP_REACHED":
                    cap = protocol["limits"]["left_branch_attempts_per_run"]
                    assert receipt["return_code"] == 42 and not receipt["timed_out"]
                    assert receipt["branch_exact_at_cap"] == cap
                    assert f"Q1464_BRANCH_CAP {cap}" in error_text
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
    output = {"proposal_id": "Q1465", "candidate_id": None, "status": "PASS",
              "runs": rows, "freeze_sha256": sha(HERE / "freeze.json"),
              "complete_solve_work_log2": None}
    (HERE / "verification.json").write_text(json.dumps(output, indent=2,
                                                        sort_keys=True) + "\n")
    print("PASS Q1465", len(rows), "runs")


if __name__ == "__main__":
    main()
