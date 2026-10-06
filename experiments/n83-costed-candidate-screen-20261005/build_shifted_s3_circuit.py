#!/usr/bin/env python3
"""Build one frozen ordinary-target S3 XCNF for each shifted N83 proposal."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import resource
import sys
import time


HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "hamming-ic-e2e-20260929"
PUBLIC = PRIOR / "runs/n83_w34_sat_fixture_v1/public_input.json"
PROTOCOL = HERE / "shifted_pdp_protocol.json"
sys.path.insert(0, str(PRIOR))
from circuit import Circuit, s3  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main(label: str, out: Path, runtime: Path) -> None:
    out = out.resolve()
    runtime = runtime.resolve()
    if not out.is_dir() or not runtime.is_file() or runtime.parent != out:
        raise FileNotFoundError("save checked Sage runtime beside output first")
    if (out / "started.json").exists() or (out / "receipt.json").exists():
        raise FileExistsError("encoding output is immutable")
    protocol = json.loads(PROTOCOL.read_text())
    public = json.loads(PUBLIC.read_text())
    options = {option["label"]: option for option in protocol["options"]}
    if label not in options:
        raise ValueError("unknown frozen option")
    geometry_path = HERE / "runs" / f"{label}_v1" / "geometry.json"
    geometry = json.loads(geometry_path.read_text())
    assert sha(PROTOCOL) and sha(PUBLIC) == protocol["public_input_sha256"]
    assert sha(PRIOR / "circuit.py") == protocol["circuit_source_sha256"]
    assert sha(geometry_path) == options[label]["geometry_sha256"]
    assert geometry["status"] == "EXACT_GEOMETRY_PASS"
    assert geometry["curve_id"] == public["curve_id"] == protocol["curve_id"]
    assert public["field_degree"] == 83
    assert public["field_polynomial_low_terms"] == [0, 2, 4, 7]
    m = geometry["arity"]
    d = geometry["dimension"]
    slots = geometry["slot_normal_basis_indices"]
    assert len(slots) == m and all(len(slot) == d for slot in slots)
    conjugates = [int(value) for value in public["normal_conjugates_polynomial_bits_decimal"]]
    assert len(conjugates) == 83
    raw_fiber = public["ordinary"]["raw_target_fiber"]
    assert len(raw_fiber) == 4
    branch_x = int(raw_fiber[0]["x"])
    source_paths = (Path(__file__), PRIOR / "circuit.py", geometry_path)
    save(out / "started.json", {
        "kind": "n83_shifted_s3_encoding_start", "candidate_id": None,
        "label": label, "curve_id": protocol["curve_id"],
        "branch_target_x_decimal": str(branch_x),
        "target_Q": public["ordinary"]["target_Q"],
        "public_input_sha256": sha(PUBLIC), "protocol_sha256": sha(PROTOCOL),
        "source_sha256": {path.name: sha(path) for path in source_paths},
        "sage_runtime_info_sha256": sha(runtime),
    })
    report = {
        "schema_version": 1, "kind": "n83_shifted_s3_encoding_receipt",
        "status": "INCOMPLETE", "candidate_id": None,
        "label": label, "curve_id": protocol["curve_id"],
        "arity": m, "dimension": d,
        "nominal_factor_boolean_coordinates": m * d,
        "unrestricted_middle_boolean_coordinates": (m - 2) * 83,
        "s3_constraints": m - 1,
        "branch_target_x_decimal": str(branch_x),
        "public_input_sha256": sha(PUBLIC), "geometry_sha256": sha(geometry_path),
        "protocol_sha256": sha(PROTOCOL),
        "source_sha256": {path.name: sha(path) for path in source_paths},
        "sage_runtime_info_sha256": sha(runtime),
        "claim_boundary": protocol["claim_boundary"],
    }
    try:
        build_started = time.perf_counter_ns()
        circuit = Circuit(83, [0, 2, 4, 7])
        factor_rows = [[circuit.variable() for _ in range(d)] for _ in range(m)]
        middle_rows = [[circuit.variable() for _ in range(83)] for _ in range(m - 2)]
        factor_x = [circuit.linear_element(row, [conjugates[index] for index in slot])
                    for row, slot in zip(factor_rows, slots)]
        middle_x = [circuit.linear_element(row, [1 << bit for bit in range(83)])
                    for row in middle_rows]
        for link in range(m - 1):
            left = factor_x[0] if link == 0 else middle_x[link - 1]
            right = factor_x[link + 1]
            output = middle_x[link] if link < m - 2 else circuit.constant(branch_x)
            s3(circuit, left, right, output)
        report["circuit_build_wall_ns_exploratory"] = time.perf_counter_ns() - build_started
        report["circuit"] = {
            "variables": circuit.next_var - 1,
            "and_gates": circuit.and_count,
            "cnf_clauses": len(circuit.clauses),
            "xor_rows": len(circuit.xors),
            "max_rss_after_build": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "max_rss_unit": "bytes" if platform.system() == "Darwin" else "kilobytes",
        }
        write_started = time.perf_counter_ns()
        xcnf = out / "branch.xcnf"
        circuit.write(xcnf)
        report["xcnf_write_wall_ns_exploratory"] = time.perf_counter_ns() - write_started
        report["xcnf_bytes"] = xcnf.stat().st_size
        report["xcnf_sha256"] = sha(xcnf)
        report["status"] = "ENCODING_COMPLETE"
    except Exception as error:
        report["status"] = "ERROR"
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["started_sha256"] = sha(out / "started.json")
        save(out / "receipt.json", report)
        print(json.dumps({"label": label, "status": report["status"],
                          "circuit": report.get("circuit")}, sort_keys=True), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("out", type=Path)
    parser.add_argument("runtime", type=Path)
    args = parser.parse_args()
    main(args.label, args.out, args.runtime)
