#!/usr/bin/env python3
"""Bind final direct-rho native checks to source, panel, and raw logs."""

import gzip
from hashlib import sha256
import json
from pathlib import Path
import re
import sys


HERE = Path(__file__).resolve().parent


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def log_receipt(name: str) -> dict:
    raw = (HERE / name).read_bytes()
    compressed = gzip.compress(raw, mtime=0)
    (HERE / (name + ".gz")).write_bytes(compressed)
    assert gzip.decompress(compressed) == raw
    return {"raw_bytes": len(raw), "raw_sha256": digest(raw),
            "gzip_bytes": len(compressed), "gzip_sha256": digest(compressed)}


def main() -> None:
    assert len(sys.argv) == 2, "usage: collect_native.py MATERIALIZED_DIRECTORY"
    native = Path(sys.argv[1]).resolve()
    materialization_raw = (native / "materialization.json").read_bytes()
    materialization = json.loads(materialization_raw)
    (HERE / "native-materialization.json").write_bytes(materialization_raw)
    inputs = json.loads((HERE / "input-check.json").read_bytes())
    replay = json.loads((HERE / "fresh-replay.json").read_bytes())
    operation = json.loads((HERE / "operation-model.json").read_bytes())
    edge = json.loads((HERE / "edge-check.json").read_bytes())
    assert inputs["status"] == replay["status"] == operation["status"] == edge["status"] == "passed"
    assert inputs["input_sha256"] == replay["input_sha256"] == \
        materialization["assets_sha256"]["dual-rho0-fresh-inputs.json"]
    assert operation["generated_source_sha256"] == \
        materialization["generated_sha256"]["src/bin/eisenstein_fixed/unit_orbit_windows.rs"]
    assert edge["materialization_sha256"] == digest(materialization_raw)
    targeted = (HERE / "rho-cli-targeted.log").read_text()
    full = (HERE / "rho-cli-full.log").read_text()
    assert "test result: ok. 1 passed; 0 failed;" in targeted
    assert "test result: ok. 142 passed; 0 failed;" in full
    match = re.search(
        r"dual_rho0_folded_cases=(\d+) retained_bytes=(\d+) "
        r"additions=(\d+) gauge_products=(\d+) "
        r"fused_additions=(\d+) fused_gauge_products=(\d+)", targeted)
    assert match is not None
    cases, retained, adds, gauges, fused_adds, fused_gauges = map(int, match.groups())
    assert (cases, retained, adds, fused_adds) == \
        (4096, 54_339_936, 49_152, 49_152)
    receipt = {
        "schema": 1, "status": "passed",
        "timing_class": "correctness_and_static_operation_model_only",
        "source_sha256": digest(Path(__file__).read_bytes()),
        "materialization_sha256": digest(materialization_raw),
        "generated_sha256": materialization["generated_sha256"],
        "input_sha256": inputs["input_sha256"],
        "atlas_sha256": materialization["assets_sha256"]["atlas-r1024-full-dual-rho0.bin"],
        "paired_cases": cases,
        "retained_bytes": retained,
        "window_mixed_additions": adds,
        "gauge_rotations": gauges,
        "fused_window_mixed_additions": fused_adds,
        "fused_gauge_rotations": fused_gauges,
        "full_suite_passed": 142,
        "edge_cases": edge["cases"],
        "edge_binary_sha256": edge["binary_sha256"],
        "rho_active_full_window_cases": replay["panel"]["active_branch_cases"]["1"],
        "operation_model": operation["model"],
        "logs": {"targeted": log_receipt("rho-cli-targeted.log"),
                 "full": log_receipt("rho-cli-full.log")},
    }
    (HERE / "native-check.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"paired_cases": cases, "full_suite_passed": 142,
                      "edge_cases": edge["cases"],
                      "rho_active_full_window_cases":
                      receipt["rho_active_full_window_cases"]}, sort_keys=True))


if __name__ == "__main__":
    main()
