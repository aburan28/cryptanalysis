#!/usr/bin/env python3
"""Independently replay Q1471 XOR-Gauss inputs, models, and receipts."""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import signal
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1460 = PARENT / "q20261011_wdsat_shared_prefix"
Q1463 = PARENT / "q20261011_wdsat_ordinary"
Q1467 = PARENT / "q20261011_wdsat_order"
Q1469 = PARENT / "q20261011_wdsat_prefix_search"
from priorities import MODES, priorities
sys.path.insert(0, str(PARENT / "q1419_partial_pin"))
from verify_archive import check_serialized_xcnf  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    protocol = json.loads((HERE / "protocol.json").read_text())
    freeze = json.loads((HERE / "freeze.json").read_text())
    build = json.loads((Q1469 / "build_receipt.json").read_text())
    parent_freeze = json.loads((Q1469 / "freeze.json").read_text())
    order_manifest = json.loads((Q1467 / "order_manifest.json").read_text())
    assert protocol["proposal_id"] == freeze["proposal_id"] == "Q1471"
    assert build["proposal_id"] == "Q1469"
    assert protocol["candidate_id"] is protocol["run_id"] is freeze["candidate_id"] is build["candidate_id"] is None
    assert protocol["isogeny"] == "none"
    assert freeze["protocol_sha256"] == sha(HERE / "protocol.json")
    assert freeze["freeze_source_sha256"] == sha(HERE / "freeze.py")
    assert freeze["q1469_build_receipt_sha256"] == sha(Q1469 / "build_receipt.json")
    assert freeze["runner_source_sha256"] == sha(HERE / "run.py")
    assert freeze["priority_source_sha256"] == sha(HERE / "priorities.py")
    assert parent_freeze["q1467_order_manifest_sha256"] == sha(Q1467 / "order_manifest.json")
    assert freeze["q1469_priority_source_sha256"] == sha(Q1469 / "priorities.py")
    assert freeze["q1469_freeze_sha256"] == sha(Q1469 / "freeze.json")
    assert freeze["q1469_analysis_sha256"] == sha(Q1469 / "analysis.json")
    assert freeze["q1469_verification_sha256"] == sha(Q1469 / "verification.json")
    assert build["freeze_sha256"] == sha(Q1469 / "freeze.json")
    assert build["upstream_commit"] == protocol["solver"]["upstream_commit"]
    rows = []
    for degree in (53, 83):
        name = f"n{degree}"
        binary = build["per_degree"][name]
        assert binary["return_code"] == 0
        assert binary["branch_patch"]["branch_cap"] == protocol["limits"]["left_branch_attempts_per_run"]
        assert binary["branch_patch"]["instrumented_sites"] == 4
        assert sha(Path(binary["binary_path"])) == binary["binary_sha256"]
        source_path = Path(binary["binary_path"]).parent / "src/wdsat.c"
        assert sha(source_path) == binary["order_patch"]["wdsat_c_sha256"]
        source_text = source_path.read_text()
        for mode in MODES:
            match = re.search(r"static const int_t q1469_" + mode +
                              r"\[\] = \{([^}]*)\};", source_text)
            assert match is not None
            parsed = [int(token.strip()) for token in match.group(1).split(",")]
            assert parsed == priorities(degree)[mode] == freeze["priority_arrays"][name][mode]
        assert source_text.count("q1469_apply_order(nb_min_vars);") == 1
        assert binary["order_patch"]["priority_counts"] == {mode: len(priorities(degree)[mode]) for mode in MODES}
        for kind in ("full_lock", "ordinary"):
            cell = f"{name}_{kind}"
            record = freeze["cells"][cell]
            if kind == "ordinary":
                archive = Q1463 / f"{name}_ordinary.xcnf.gz"
                source = PARENT / "runs" / f"{name}_q{1410 if degree == 53 else 1408}_ordinary.xcnf.gz"
            else:
                archive = Q1460 / f"{name}_full_lock.xcnf.gz"
                source = PARENT / "q1419_partial_pin/runs" / f"{name}_full_lock/system.xcnf.gz"
            assert sha(archive) == record["derived_archive_sha256"]
            assert sha(source) == record["source_archive_sha256"]
            derived = gzip.decompress(archive.read_bytes())
            original = gzip.decompress(source.read_bytes())
            assert hashlib.sha256(derived).hexdigest() == record["derived_raw_sha256"]
            for mode in (protocol["selected_mode_by_degree"][str(degree)],):
                validate_run(degree, kind, mode, name, cell, freeze, build, protocol,
                             order_manifest, binary, archive, source, derived, original, rows)
    output = {"proposal_id": "Q1471", "candidate_id": None, "status": "PASS",
              "runs": rows, "freeze_sha256": sha(HERE / "freeze.json"),
              "complete_solve_work_log2": None}
    (HERE / "verification.json").write_text(json.dumps(output, indent=2,
                                                        sort_keys=True) + "\n")
    print("PASS Q1471", len(rows), "runs")


def validate_run(degree, kind, mode, name, cell, freeze, build, protocol,
                 order_manifest, binary, archive, source, derived, original, rows):
            record = freeze["cells"][cell]
            run_dir = HERE / "runs" / cell / mode
            if not (run_dir / "receipt.json").exists():
                return
            receipt = json.loads((run_dir / "receipt.json").read_text())
            stdout = (run_dir / "solver.stdout.txt").read_bytes()
            stderr = (run_dir / "solver.stderr.txt").read_bytes()
            error_text = stderr.decode("utf-8", "replace")
            assert receipt["proposal_id"] == "Q1471"
            assert receipt["solver_mode"] == "xor_gauss"
            assert receipt["command_template"] == [binary["binary_path"], "-x", "-i", "INPUT"]
            assert receipt["candidate_id"] is receipt["run_id"] is None
            assert receipt["isogeny"] == "none"
            assert (receipt["degree"], receipt["kind"], receipt["variant"]) == (degree, kind, mode)
            priority = priorities(degree)[mode]
            assert len(priority) == len(set(priority))
            assert all(1 <= value <= freeze["cells"][cell]["derived_variables"] for value in priority)
            marker = f"Q1469_ORDER {mode} {len(priority)}"
            assert error_text.splitlines().count(marker) == 1
            assert receipt["branch_order_marker"] == marker
            assert receipt["branch_order_priority_count"] == len(priority)
            assert receipt["ordinary_query"] == (kind == "ordinary")
            for field in ("curve_id", "workload_id", "public_target", "factor_base_actual_B",
                          "factor_base_folded_columns_K", "factor_base_enumerated_set_sha256"):
                assert receipt[field] == record[field]
            assert receipt["protocol_sha256"] == sha(HERE / "protocol.json")
            assert receipt["freeze_sha256"] == sha(HERE / "freeze.json")
            assert receipt["build_receipt_sha256"] == sha(Q1469 / "build_receipt.json")
            assert receipt["runner_sha256"] == sha(HERE / "run.py")
            assert receipt["archive_sha256"] == sha(archive)
            assert receipt["source_archive_sha256"] == sha(source)
            assert receipt["binary_sha256"] == binary["binary_sha256"]
            assert receipt["stdout_sha256"] == hashlib.sha256(stdout).hexdigest()
            assert receipt["stderr_sha256"] == hashlib.sha256(stderr).hexdigest()
            assert receipt["search_started"] == ("Q1458_SEARCH_START" in error_text)
            assert receipt["after_xor_init"] == ("Q1458_AFTER_XOR_INIT" in error_text)
            checkpoints = [int(value) for value in re.findall(r"^Q1464_BRANCH (\d+)$",
                                                             error_text, re.MULTILINE)]
            assert checkpoints == receipt["branch_checkpoints"]
            assert all(value == 1 << index for index, value in enumerate(checkpoints))
            assert receipt["branch_lower_bound"] == (checkpoints[-1] if checkpoints else 0)
            limits = protocol["limits"]
            assert receipt["left_branch_attempt_limit"] == limits["left_branch_attempts_per_run"]
            assert receipt["wall_limit_seconds"] == limits["wall_seconds_per_run"]
            assert receipt["cpu_soft_limit_seconds"] == limits["cpu_seconds_soft"]
            assert receipt["cpu_hard_limit_seconds"] == limits["cpu_seconds_hard"]
            assert receipt["natural_relation_yield_estimate"] is None
            assert receipt["complete_solve_work_log2"] is None
            if receipt["status"] == "SAT_REPLAYED_XCNF":
                models = [line for line in stdout.decode("ascii").splitlines()
                          if len(line) == record["derived_variables"] and set(line) <= {"0", "1"}]
                assert len(models) == receipt["model_count"] == 1
                model = {i + 1: ch == "1" for i, ch in enumerate(models[0])}
                original_vars = int(original.splitlines()[0].split()[2])
                replays = {"derived": check_serialized_xcnf(derived, model),
                           "original": check_serialized_xcnf(original, {i: model[i]
                                                                       for i in range(1, original_vars + 1)})}
                for key, replay in replays.items():
                    assert all(receipt["model_replay"][key][field] == value
                               for field, value in replay.items())
                assert receipt["return_code"] == 0 and not receipt["timed_out"]
            elif receipt["status"] == "BRANCH_CAP_REACHED":
                cap = limits["left_branch_attempts_per_run"]
                assert receipt["return_code"] == 42 and not receipt["timed_out"]
                assert receipt["branch_exact_at_cap"] == cap
                assert f"Q1464_BRANCH_CAP {cap}" in error_text
                assert receipt["search_started"]
            elif receipt["status"] in ("CPU_CAP_SEARCH_STARTED", "CPU_CAP_BEFORE_SEARCH"):
                assert receipt["return_code"] in (-signal.SIGXCPU, -signal.SIGKILL)
                assert receipt["user_cpu_seconds"] + receipt["system_cpu_seconds"] >= limits["cpu_seconds_soft"] - 2
            elif receipt["status"] in ("WALL_CAP_SEARCH_STARTED", "CENSORED_BEFORE_SEARCH"):
                assert receipt["timed_out"]
            else:
                assert receipt["status"] in ("PRODUCER_FAILURE", "UNSAT_REPORTED_UNVERIFIED",
                                              "MODEL_REPLAY_FAILED", "PRODUCER_FAILURE_NO_MODEL")
            rows.append({"degree": degree, "kind": kind, "mode": mode,
                         "status": receipt["status"],
                         "branch_lower_bound": receipt["branch_lower_bound"],
                         "user_cpu_seconds": receipt["user_cpu_seconds"],
                         "wall_seconds_exploratory": receipt["wall_seconds_exploratory"],
                         "receipt_sha256": sha(run_dir / "receipt.json")})
if __name__ == "__main__":
    main()
