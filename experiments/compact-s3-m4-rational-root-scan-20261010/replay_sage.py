#!/usr/bin/env python3
"""Independently replay rational-filter scan hits with checked Sage."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "compact-s3-m4-quadratic-root-scan-20261010"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    started = time.perf_counter_ns()
    import experiment as current_experiment
    current_experiment.check_freeze()
    audit = json.loads((HERE / "audit.json").read_text())
    assert audit["status"] == "PASS" and len(audit["rows"]) == 8
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert runtime["status"] == "verified"
    protocol = json.loads((HERE / "sage_audit_protocol.json").read_text())
    assert protocol["source_sha256"] == sha(Path(__file__))
    assert protocol["audit_sha256"] == sha(HERE / "audit.json")
    assert protocol["runtime_sha256"] == sha(HERE / "sage_runtime_info.json")
    parent_experiment = load_module("q1425_parent_experiment", PARENT / "experiment.py")
    sys.modules["experiment"] = parent_experiment
    replay = load_module("q1425_parent_replay", PARENT / "replay_sage.py")
    replay.HERE = HERE
    old_protocol_path = parent_experiment.OLD / "q1419_partial_pin/protocol.json"
    old_protocol = json.loads(old_protocol_path.read_text())
    rows = [row for n in (53, 83)
            for row in replay.replay_degree(n, old_protocol["profiles"][str(n)])]
    assert len(rows) == 8
    assert all(row["recorded_hits_checked"] == (1 if "control" in row["cell"] else 0)
               for row in rows)
    assert all(hit["status"] == "verified_four_point_relation"
               for row in rows for hit in row["hits"])
    result = {"schema": "q20261010120000-sage-replay-v1",
              "proposal_id": "Q20261010120000", "status": "PASS",
              "protocol_sha256": sha(HERE / "sage_audit_protocol.json"),
              "freeze_sha256": sha(HERE / "freeze.json"),
              "runtime_sha256": sha(HERE / "sage_runtime_info.json"),
              "old_curve_protocol_sha256": sha(old_protocol_path),
              "source_sha256": sha(Path(__file__)),
              "elapsed_ns": str(time.perf_counter_ns() - started),
              "rows": rows}
    output = HERE / "sage_replay.json"
    assert not output.exists()
    output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "cells": len(rows),
                      "verified_hits": sum(row["recorded_hits_checked"]
                                           for row in rows)}))


if __name__ == "__main__":
    main()
