#!/usr/bin/env python3
"""Independently replay Q1460 models and validate source-bound run receipts."""
from __future__ import annotations
import gzip
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT / "q1419_partial_pin"))
from verify_archive import check_serialized_xcnf  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    protocol = json.loads((HERE / "protocol.json").read_text())
    prepared = json.loads((HERE / "prepare_receipt.json").read_text())
    freeze = json.loads((HERE / "freeze.json").read_text())
    build = json.loads((HERE / "build_receipt.json").read_text())
    equivalence = json.loads((HERE / "equivalence_check.json").read_text())
    assert equivalence["status"] == prepared["witness_replay_status"] == "PASS"
    assert equivalence["transform_source_sha256"] == sha(HERE / "prepare.py")
    assert prepared["source_sha256"] == sha(HERE / "prepare.py")
    assert prepared["protocol_sha256"] == freeze["protocol_sha256"] == sha(HERE / "protocol.json")
    assert freeze["prepare_receipt_sha256"] == sha(HERE / "prepare_receipt.json")
    assert freeze["build_source_sha256"] == sha(HERE / "build.py")
    assert build["freeze_sha256"] == sha(HERE / "freeze.json")
    rows = []
    for cell in protocol["cells"]:
        degree = cell.split("_")[0]
        data = prepared["cells"][cell]
        assert data["auxiliary_variables"] == data["shared_prefixes"]
        assert data["derived_witness_replay"]["max_cnf_width"] <= 4
        assert data["original_witness_replay"]["xor_rows"] == data["derived_witness_replay"]["xor_rows"]
        derived_archive = HERE / f"{cell}.xcnf.gz"
        original_archive = PARENT / "q1419_partial_pin/runs" / cell / "system.xcnf.gz"
        assert sha(derived_archive) == data["derived_archive_sha256"]
        assert sha(original_archive) == data["source_archive_sha256"]
        derived = gzip.decompress(derived_archive.read_bytes())
        original = gzip.decompress(original_archive.read_bytes())
        assert hashlib.sha256(derived).hexdigest() == data["derived_raw_sha256"]
        assert hashlib.sha256(original).hexdigest() == data["source_raw_sha256"]
        binary_record = build["per_degree"][degree]
        assert binary_record["return_code"] == 0
        assert sha(Path(binary_record["binary_path"])) == binary_record["binary_sha256"]
        for variant in protocol["upstream_solver"]["variants"]:
            run_dir = HERE / "runs" / cell / variant
            if not (run_dir / "receipt.json").exists():
                continue
            receipt = json.loads((run_dir / "receipt.json").read_text())
            stdout = (run_dir / "solver.stdout.txt").read_bytes()
            stderr = (run_dir / "solver.stderr.txt").read_bytes()
            assert receipt["proposal_id"] == "Q1460"
            assert receipt["candidate_id"] is None and receipt["run_id"] is None
            assert receipt["isogeny"] == "none"
            assert receipt["cell"] == cell and receipt["variant"] == variant
            assert receipt["runner_sha256"] == sha(HERE / "run.py")
            assert receipt["freeze_sha256"] == sha(HERE / "freeze.json")
            assert receipt["prepare_receipt_sha256"] == sha(HERE / "prepare_receipt.json")
            assert receipt["build_receipt_sha256"] == sha(HERE / "build_receipt.json")
            assert receipt["derived_archive_sha256"] == sha(derived_archive)
            assert receipt["source_archive_sha256"] == sha(original_archive)
            assert receipt["stdout_sha256"] == hashlib.sha256(stdout).hexdigest()
            assert receipt["stderr_sha256"] == hashlib.sha256(stderr).hexdigest()
            assert receipt["binary_sha256"] == binary_record["binary_sha256"]
            error_text = stderr.decode("utf-8", "replace")
            assert receipt["after_xor_init"] == ("Q1458_AFTER_XOR_INIT" in error_text)
            assert receipt["search_started"] == ("Q1458_SEARCH_START" in error_text)
            if receipt["status"] == "SAT_REPLAYED_BOTH":
                text = stdout.decode("ascii")
                variables = data["derived_variables"]
                models = [line for line in text.splitlines()
                          if len(line) == variables and set(line) <= {"0", "1"}]
                assert len(models) == 1
                model = {i+1: ch == "1" for i, ch in enumerate(models[0])}
                original_model = {k: v for k, v in model.items()
                                  if k <= data["original_variables"]}
                derived_replay = check_serialized_xcnf(derived, model)
                original_replay = check_serialized_xcnf(original, original_model)
                assert all(derived_replay[key] == receipt["model_replay"]["derived"][key]
                           for key in derived_replay)
                assert all(original_replay[key] == receipt["model_replay"]["original"][key]
                           for key in original_replay)
                assert derived_replay["variables"] == data["derived_variables"]
                assert original_replay["variables"] == data["original_variables"]
                assert derived_replay["xor_rows"] == original_replay["xor_rows"]
            elif receipt["status"] == "BOUNDED_UNKNOWN":
                assert receipt["timed_out"] and receipt["search_started"]
                assert receipt["model_replay"] is None
            else:
                assert receipt["status"] in ("CENSORED_BEFORE_SEARCH", "PRODUCER_FAILURE",
                                              "UNSAT_REPORTED_AGAINST_WITNESS",
                                              "MODEL_REPLAY_FAILED", "PRODUCER_FAILURE_NO_STATUS")
            rows.append({"cell": cell, "variant": variant, "status": receipt["status"],
                         "search_started": receipt["search_started"],
                         "wall_seconds_exploratory": receipt["wall_seconds_exploratory"],
                         "user_cpu_seconds": receipt["user_cpu_seconds"],
                         "maxrss_bytes_darwin": receipt["maxrss_child_bytes_darwin"],
                         "receipt_sha256": sha(run_dir / "receipt.json")})
    output = {"proposal_id": "Q1460", "candidate_id": None, "status": "PASS",
              "freeze_sha256": sha(HERE / "freeze.json"), "runs": rows,
              "ordinary_relation_yield": None, "complete_solve_work_log2": None}
    (HERE / "verification.json").write_text(json.dumps(output, indent=2,
                                                         sort_keys=True) + "\n")
    print("PASS Q1460", len(rows), "runs")


if __name__ == "__main__":
    main()
