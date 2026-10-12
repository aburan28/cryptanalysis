#!/usr/bin/env python3
"""Validate Q1458 source, archived formulas, bounded runs, and SAT models."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    args = argparse.ArgumentParser()
    args.add_argument("--emit", action="store_true")
    emit = args.parse_args().emit
    protocol_bytes = (HERE / "protocol.json").read_bytes()
    protocol = json.loads(protocol_bytes)
    freeze_bytes = (HERE / "freeze.json").read_bytes()
    freeze = json.loads(freeze_bytes)
    build_bytes = (HERE / "build_receipt.json").read_bytes()
    build = json.loads(build_bytes)
    assert freeze["protocol_sha256"] == sha(protocol_bytes)
    assert build["freeze_sha256"] == sha(freeze_bytes)
    current_source = (HERE / "run.py").read_text()
    console_old = current_source.replace(
        '"wall_seconds": elapsed,\n                      "maxrss_bytes_darwin": after.ru_maxrss',
        '"wall_seconds": elapsed, "maxrss_kib": after.ru_maxrss')
    allowed_runner_hashes = {sha(current_source.encode()), sha(console_old.encode())}
    rows = []
    for cell in protocol["cells"]:
        degree = cell.split("_")[0]
        frozen = freeze["cells"][cell]
        archive = (PARENT / "q1419_partial_pin" / "runs" / cell /
                   "system.xcnf.gz").read_bytes()
        raw = gzip.decompress(archive)
        assert sha(archive) == frozen["formula_archive_sha256"]
        assert sha(raw) == frozen["formula_raw_sha256"]
        binary = Path(build["per_degree"][degree]["binary_path"])
        assert sha(binary.read_bytes()) == build["per_degree"][degree]["binary_sha256"]
        for variant in protocol["upstream_solver"]["variants"]:
            path = HERE / "runs" / cell / variant
            if not (path / "receipt.json").exists():
                continue
            receipt = json.loads((path / "receipt.json").read_text())
            stdout = (path / "solver.stdout.txt").read_bytes()
            stderr = (path / "solver.stderr.txt").read_bytes()
            assert receipt["proposal_id"] == "Q1458"
            assert receipt["candidate_id"] is None and receipt["run_id"] is None
            assert receipt["isogeny"] == "none"
            assert receipt["curve_id"] == frozen["curve_id"]
            assert receipt["stage_config_id"] == frozen["stage_config_id"]
            assert receipt["workload_id"] == frozen["workload_id"]
            assert receipt["input_archive_sha256"] == sha(archive)
            assert receipt["input_raw_sha256"] == sha(raw)
            assert receipt["stdout_sha256"] == sha(stdout)
            assert receipt["stderr_sha256"] == sha(stderr)
            assert receipt["binary_sha256"] == sha(binary.read_bytes())
            assert receipt["freeze_sha256"] == sha(freeze_bytes)
            assert receipt["build_receipt_sha256"] == sha(build_bytes)
            assert receipt["runner_sha256"] in allowed_runner_hashes
            assert receipt["resource_limit_address_space_mib"] is None
            assert receipt["resource_limit_wall_seconds"] == 60
            error_text = stderr.decode("utf-8", "replace")
            assert receipt["after_xor_init"] == ("Q1458_AFTER_XOR_INIT" in error_text)
            assert receipt["search_started"] == ("Q1458_SEARCH_START" in error_text)
            if receipt["status"] == "SAT_VERIFIED_XCNF":
                sys.path.insert(0, str(PARENT / "q1419_partial_pin"))
                from verify_archive import check_serialized_xcnf
                text = stdout.decode("ascii")
                models = [line for line in text.splitlines()
                          if len(line) == frozen["formula"]["variables"] and
                          set(line) <= {"0", "1"}]
                assert len(models) == 1
                model = {i + 1: value == "1" for i, value in enumerate(models[0])}
                independent = check_serialized_xcnf(raw, model)
                assert independent == receipt["model_check"]
            elif receipt["status"] == "BOUNDED_UNKNOWN":
                assert receipt["timed_out"] and receipt["search_started"]
                assert receipt["model_check"] is None
            elif receipt["status"] == "CENSORED_BEFORE_SEARCH":
                assert receipt["timed_out"] and not receipt["search_started"]
            else:
                assert receipt["status"].startswith("PRODUCER_FAILURE") or receipt["status"] in (
                    "MODEL_REPLAY_FAILED", "UNSAT_REPORTED")
            rows.append({"cell": cell, "variant": variant, "status": receipt["status"],
                         "search_started": receipt["search_started"],
                         "wall_seconds_exploratory": receipt["wall_seconds_exploratory"],
                         "user_cpu_seconds": receipt["user_cpu_seconds"],
                         "maxrss_bytes_darwin": receipt["maxrss_child_bytes_darwin"],
                         "receipt_sha256": sha((path / "receipt.json").read_bytes())})
    result = {"proposal_id": "Q1458", "status": "PASS", "candidate_id": None,
              "freeze_sha256": sha(freeze_bytes),
              "build_receipt_sha256": sha(build_bytes), "runs": rows,
              "ordinary_relation_yield": None, "complete_solve_work_log2": None}
    if emit:
        (HERE / "verification.json").write_text(json.dumps(result, sort_keys=True,
                                                             indent=2) + "\n")
    print(json.dumps({"validated_runs": len(rows),
                      "statuses": {row["cell"] + ":" + row["variant"]: row["status"]
                                   for row in rows}}))


if __name__ == "__main__":
    main()
