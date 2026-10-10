#!/usr/bin/env python3
"""Rebuild all paired CNFs and replay archived Kissat statuses and models."""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

from converter import check_model, convert, sha
from run import HERE, REPO, source_input

ORDER = ("source_control_z0", "descendant_native_control_z0",
         "source_ordinary_q0", "descendant_native_ordinary_q0")


def audit_cell(repo: Path, cfg: dict, cell: str) -> dict:
    evidence = HERE / "runs/R1"
    receipt = json.loads((evidence / f"{cell}.json").read_text())
    stdout_gzip = (evidence / f"{cell}.stdout.txt.gz").read_bytes()
    stdout = gzip.decompress(stdout_gzip)
    stderr = (evidence / f"{cell}.stderr.txt").read_bytes()
    raw, units = source_input(repo, cfg, cell)
    _, formula = convert(raw, units)
    if (receipt["schema"] != "ecc2k130-xcnf-kissat-cell-v1"
            or receipt["cell"] != cell
            or receipt["input_commit"] != cfg["input_commit"]
            or receipt["source_manifest_sha256"] != sha((HERE / "source.json").read_bytes())
            or receipt["protocol_sha256"] != sha((HERE / "PROTOCOL.md").read_bytes())
            or receipt["converter_sha256"] != sha((HERE / "converter.py").read_bytes())
            or receipt["runner_sha256"] != sha((HERE / "run.py").read_bytes())
            or receipt["solver_sha256"] != cfg["kissat_sha256"]
            or receipt["solver_version"] != cfg["kissat_version"]
            or receipt["formula"] != formula
            or receipt["stdout_gzip_sha256"] != sha(stdout_gzip)
            or receipt["stdout_sha256"] != sha(stdout)
            or receipt["stderr_sha256"] != sha(stderr)):
        raise ValueError("frozen source, formula, or transcript differs: " + cell)
    terminals = [line.decode(errors="replace") for line in stdout.splitlines()
                 if line.startswith(b"s ")]
    if receipt["terminal"] != terminals:
        raise ValueError("terminal differs: " + cell)
    if receipt["status"] == "SAT_XCNF_MODEL_VERIFIED":
        if terminals != ["s SATISFIABLE"] or receipt["exit_code"] != 10:
            raise ValueError("SAT status lacks terminal certificate: " + cell)
        model = check_model(raw, units, stdout)
        if model != receipt["model_replay"]:
            raise ValueError("model replay differs: " + cell)
    elif receipt["status"] == "BOUNDED_UNKNOWN":
        if not (terminals == ["s UNKNOWN"] and receipt["exit_code"] == 0
                or receipt["guard"] == "WALL_CAP"):
            raise ValueError("bounded cell lacks a recorded cap: " + cell)
        model = None
    elif receipt["status"] in ("OOM_GUARD", "PRODUCER_FAILURE", "UNSAT_UNVERIFIED"):
        model = None
    else:
        raise ValueError("unexpected status: " + cell)
    if receipt["status"] != "SAT_XCNF_MODEL_VERIFIED" and receipt["model_replay"] is not None:
        raise ValueError("non-SAT cell has a model: " + cell)
    if receipt["verified_group_relation"] is not None or receipt["novel_rank"] is not None:
        raise ValueError("stage result silently claims a relation or rank")
    return {
        "status": receipt["status"],
        "exit_code": receipt["exit_code"],
        "terminal": terminals,
        "formula": formula,
        "model_replay": model,
        "solver_wall_ms": receipt["solver_wall_ms"],
        "sampled_peak_rss_bytes": receipt["sampled_peak_rss_bytes"],
        "guard": receipt["guard"],
        "receipt_sha256": sha((evidence / f"{cell}.json").read_bytes()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--out", type=Path, default=HERE / "runs/R1/audit.json")
    args = parser.parse_args()
    cfg = json.loads((HERE / "source.json").read_text())
    assert set(cfg["cells"]) == set(ORDER)
    cells = {name: audit_cell(args.repo.resolve(), cfg, name) for name in ORDER}
    result = {
        "schema": "ecc2k130-xcnf-kissat-audit-v1",
        "status": "PASS_PINNED_INPUTS_CONVERSION_AND_TRANSCRIPTS",
        "source_manifest_sha256": sha((HERE / "source.json").read_bytes()),
        "protocol_sha256": sha((HERE / "PROTOCOL.md").read_bytes()),
        "converter_sha256": sha((HERE / "converter.py").read_bytes()),
        "runner_sha256": sha((HERE / "run.py").read_bytes()),
        "auditor_sha256": sha(Path(__file__).read_bytes()),
        "cells": cells,
    }
    if args.out.exists():
        raise FileExistsError(args.out)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({name: row["status"] for name, row in cells.items()},
                     sort_keys=True))


if __name__ == "__main__":
    main()
