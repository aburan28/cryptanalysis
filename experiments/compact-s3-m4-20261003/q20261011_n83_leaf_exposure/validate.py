#!/usr/bin/env python3
"""Replay the Q1478 source patch, control model, and bounded N83 logs."""
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


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def full_control_model(frozen: dict, row: dict, stdout: Path) -> None:
    cell = frozen["inputs"]["control"]
    derived = gzip.decompress(Path(cell["derived_path"]).read_bytes())
    original = gzip.decompress(Path(cell["source_path"]).read_bytes())
    n_derived = int(derived.splitlines()[0].split()[2])
    n_original = int(original.splitlines()[0].split()[2])
    models = [line.strip() for line in stdout.read_text().splitlines()
              if len(line.strip()) == n_derived and set(line.strip()) <= {"0", "1"}]
    assert len(models) == 1
    assignment = {i + 1: bit == "1" for i, bit in enumerate(models[0])}
    evaluator = load("q1460_evaluate_for_q1478",
                     PARENT / "q20261011_wdsat_shared_prefix/prepare.py")
    assert evaluator.evaluate(derived, assignment)["xor_rows"] == 1245
    assert evaluator.evaluate(original, {i: assignment[i]
                                         for i in range(1, n_original + 1)})[
        "xor_rows"] == 1245
    assert row["status"] == "MODEL_REQUIRES_REPLAY" and row["return_code"] == 0


def main() -> None:
    protocol = json.loads((HERE / "protocol.json").read_text())
    frozen = json.loads((HERE / "freeze.json").read_text())
    build = json.loads((HERE / "build_receipt.json").read_text())
    drive = json.loads((HERE / "drive_receipt.json").read_text())
    assert protocol["proposal_id"] == frozen["proposal_id"] == build[
        "proposal_id"] == drive["proposal_id"] == "Q1478"
    for name, digest in frozen["files_sha256"].items():
        assert sha(HERE / name) == digest
    assert sha(PARENT / "q20261011_selector_polarity/build_receipt.json") == frozen[
        "q1473_build_sha256"]
    assert sha(Path(frozen["parent_source_dir"]) / "wdsat.c") == frozen[
        "parent_wdsat_c_sha256"]
    assert sha(Path(build["binary_path"])) == build["binary_sha256"]
    assert build["freeze_sha256"] == sha(HERE / "freeze.json")
    assert build["source_sha256"] == sha(HERE / "build.py")
    assert sha(HERE / "build.stdout.txt") == build["build_stdout_sha256"]
    assert sha(HERE / "build.stderr.txt") == build["build_stderr_sha256"]
    patcher = load("q1478_build_replay", HERE / "build.py")
    with tempfile.TemporaryDirectory(prefix="q1478_validate_") as temp:
        source = Path(temp)
        shutil.copy2(Path(frozen["parent_source_dir"]) / "wdsat.c",
                     source / "wdsat.c")
        assert patcher.patch(source) == build["patched_wdsat_c_sha256"]
    expected = [("control", "q1478_leafpair_first"),
                *( (name, order) for name in ("selected", "holdout")
                   for order in protocol["orders"] )]
    assert [(r["input"], r["order"]) for r in drive["rows"]] == expected
    assert drive["new_ordinary_attempts"] == 4
    rows = []
    for item in drive["rows"]:
        name, order = item["input"], item["order"]
        folder = HERE / "runs" / f"{name}_{order}"
        path = folder / "receipt.json"
        assert sha(path) == item["receipt_sha256"]
        row = json.loads(path.read_text())
        cell = frozen["inputs"][name]
        assert row["input"] == name and row["order"] == order
        assert row["workload_id"] == cell["workload_id"]
        assert row["binary_sha256"] == build["binary_sha256"]
        assert row["input_sha256"] == cell["derived_sha256"]
        assert row["freeze_sha256"] == sha(HERE / "freeze.json")
        for key in ("derived", "source"):
            p = Path(cell[f"{key}_path"])
            assert sha(p) == cell[f"{key}_sha256"]
            assert hashlib.sha256(gzip.decompress(p.read_bytes())).hexdigest() == cell[
                f"{key}_raw_sha256"]
        stdout, stderr = folder / "solver.stdout.txt", folder / "solver.stderr.txt"
        assert sha(stdout) == row["stdout_sha256"]
        assert sha(stderr) == row["stderr_sha256"]
        log = stderr.read_text(errors="replace")
        parsed = [tuple(map(int, v)) for v in re.findall(
            r"^Q1478_READY (\d+) (\d+) (\d+) (\d+) (\d+) (\d+)$", log, re.M)]
        assert [list(v) for v in parsed] == row["ready_checkpoints"]
        assert log.splitlines().count(f"Q1469_ORDER {order} 168") == 1
        assert row["order_marker_ok"] and row["search_started"]
        if name == "control":
            full_control_model(frozen, row, stdout)
        else:
            assert row["status"] == "CHECKPOINT_TERMINATED"
            assert row["branch_lower_bound"] == protocol["branch_checkpoint"]
            assert parsed[-1][0] == protocol["branch_checkpoint"]
            assert stdout.stat().st_size == 0
        rows.append(row)
    assert abs(sum(r["solver_wall_seconds_exploratory"] for r in rows) -
               drive["solver_wall_phase_sum_seconds_exploratory"]) < 1e-8
    assert abs(sum(r["solver_user_cpu_seconds_exploratory"] for r in rows) -
               drive["solver_user_cpu_sum_seconds_exploratory"]) < 1e-8
    print("PASS Q1478", [(r["input"], r["order"], r["status"]) for r in rows])


if __name__ == "__main__":
    main()
