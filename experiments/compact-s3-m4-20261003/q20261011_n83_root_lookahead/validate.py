#!/usr/bin/env python3
"""Validate Q1477 root probes, state restoration, and source-bound inputs."""
from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import re
import shutil
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1473 = PARENT / "q20261011_selector_polarity"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    protocol = json.loads((HERE / "protocol.json").read_text())
    frozen = json.loads((HERE / "freeze.json").read_text())
    build = json.loads((HERE / "build_receipt.json").read_text())
    drive = json.loads((HERE / "drive_receipt.json").read_text())
    assert protocol["proposal_id"] == frozen["proposal_id"] == build[
        "proposal_id"] == drive["proposal_id"] == "Q1477"
    assert protocol["candidate_id"] is protocol["run_id"] is None
    assert protocol["probe_literals"] == [-2140, 2140]
    for name, digest in frozen["files_sha256"].items():
        assert sha(HERE / name) == digest
    assert frozen["q1473_build_sha256"] == sha(Q1473 / "build_receipt.json")
    assert frozen["q1473_smoke_sha256"] == sha(Q1473 / "smoke_receipt.json")
    assert json.loads((Q1473 / "smoke_receipt.json").read_text())[
        "status"] == "PASS"
    assert build["freeze_sha256"] == drive["freeze_sha256"] == sha(
        HERE / "freeze.json")
    assert sha(Path(build["binary_path"])) == build["binary_sha256"]
    assert sha(Path(build["patched_source_path"])) == build[
        "patched_wdsat_c_sha256"]
    assert sha(Path(frozen["parent_source_dir"]) / "wdsat.c") == frozen[
        "parent_wdsat_c_sha256"] == build["parent_source_wdsat_c_sha256"]
    assert sha(Path(frozen["parent_source_dir"]) / "config.h") == frozen[
        "parent_config_sha256"] == build["config_sha256"]
    assert sha(HERE / "build.stdout.txt") == build["build_stdout_sha256"]
    assert sha(HERE / "build.stderr.txt") == build["build_stderr_sha256"]
    spec = importlib.util.spec_from_file_location("q1477_build_for_validation",
                                                  HERE / "build.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(dir="/Volumes/SSD990/llm/tmp") as tmp:
        scratch = Path(tmp)
        shutil.copy2(Path(frozen["parent_source_dir"]) / "wdsat.c", scratch / "wdsat.c")
        assert module.patch(scratch) == build["patched_wdsat_c_sha256"]
    rows = []
    for label in ("control", "selected", "holdout"):
        folder = HERE / "runs" / label
        if not folder.exists():
            break
        row = json.loads((folder / "receipt.json").read_text())
        input_record = frozen["inputs"][label]
        source = Path(input_record["path"])
        assert row["label"] == label and row["proposal_id"] == "Q1477"
        assert row["curve_id"] == protocol["curve_id"]
        assert row["workload_id"] == input_record["workload_id"]
        assert row["isogeny"] == "none"
        assert row["factor_base_actual_B"] == protocol["factor_base_actual_B"]
        assert row["factor_base_folded_columns_K"] == protocol[
            "factor_base_folded_columns_K"]
        assert sha(source) == row["input_sha256"] == input_record["sha256"]
        raw = source.read_bytes() if label == "control" else gzip.decompress(source.read_bytes())
        assert hashlib.sha256(raw).hexdigest() == row["raw_input_sha256"]
        assert row["binary_sha256"] == build["binary_sha256"]
        assert row["freeze_sha256"] == sha(HERE / "freeze.json")
        assert row["build_receipt_sha256"] == sha(HERE / "build_receipt.json")
        assert row["source_sha256"] == sha(HERE / "run.py")
        stdout_path, stderr_path = folder / "solver.stdout.txt", folder / "solver.stderr.txt"
        assert sha(stdout_path) == row["stdout_sha256"]
        assert sha(stderr_path) == row["stderr_sha256"]
        text = stderr_path.read_text(errors="replace")
        matches = re.findall(r"^Q1477_ROOT (-?\d+) ([01]) (\d+) (\d+) (\d+) (\d+)$",
                             text, re.M)
        parsed = [{"literal": int(v[0]), "consistent": bool(int(v[1])),
                   "cnf_calls": int(v[2]), "xor_calls": int(v[3]),
                   "cnf_new_assignments": int(v[4]),
                   "xor_new_assignments": int(v[5])} for v in matches]
        assert row["root_rows"] == parsed
        assert [v["literal"] for v in parsed] == protocol["probe_literals"]
        restored = re.findall(r"^Q1477_ROOT_RESTORED (\d+) (\d+)$", text, re.M)
        assert len(restored) == 1
        assert row["restored_cnf_xor_assignment_counts"] == list(map(int, restored[0]))
        assert row["search_started"] is False
        assert row["marker_ok"] and row["status"] == "ROOT_PROBES_RESTORED"
        assert row["return_code"] == 43 and not row["timed_out"]
        final = [list(map(int, match)) for match in re.findall(
            r"^Q1473_WORK_FINAL (\d+) (\d+)$", text, re.M)]
        assert row["q1473_final_work_rows"] == final and len(final) == 1
        assert final[0][0] >= sum(v["cnf_calls"] for v in parsed)
        assert final[0][1] >= sum(v["xor_calls"] for v in parsed)
        assert row["complete_n83_decomposition_work_log2"] is None
        assert row["complete_n131_solve_work_log2"] is None
        rows.append(row)
    assert rows and drive["labels"] == [r["label"] for r in rows]
    assert drive["statuses"] == [r["status"] for r in rows]
    assert abs(drive["total_exploratory_solver_wall_seconds"] - sum(
        r["solver_wall_seconds_exploratory"] for r in rows)) < 1e-8
    assert abs(drive["total_exploratory_user_cpu_seconds"] - sum(
        r["user_cpu_seconds_exploratory"] for r in rows)) < 1e-8
    print("PASS Q1477", [r["label"] for r in rows])


if __name__ == "__main__":
    main()
