#!/usr/bin/env python3
"""Bind the exact N131 XOR projection to its one-target terminal solver row."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n131_w14_compact_columns_20261010"


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def main():
    protocol = load(HERE / "protocol.json")
    constructed = load(HERE / "constructed/projection_receipt.json")
    control = load(HERE / "constructed/control_audit.json")
    public = load(HERE / "public/projection_receipt.json")
    structure = load(HERE / "public/structure_audit.json")
    result = load(HERE / "public_solver/result.json")
    baseline = load(SOURCE / "public_query/result.json")
    assert protocol["status"] == "FROZEN_BEFORE_COMPACT_N131_XOR_PROJECTION_AND_SEARCH"
    for name, path in {
        "run": HERE / "run.py",
        "projector": HERE.parent / "xor_projection_20261009/project_xcnf.py",
        "public_formula_gzip": SOURCE / "public_query/system.xcnf.gz",
        "constructed_formula_gzip": SOURCE / "constructed.xcnf.gz",
        "public_result": SOURCE / "public_query/result.json",
        "constructed_result": SOURCE / "control_result.json",
        "compact_terminal_audit": SOURCE / "terminal_audit.json",
        "checked_sage_runtime": HERE / "sage_runtime_info.json",
        "solver": Path("/opt/homebrew/bin/cryptominisat5"),
    }.items():
        assert protocol["source_sha256"][name] == sha(path), name
    assert baseline["target_q"] == protocol["target_q"] == result["target_q"]
    assert constructed["status"] == public["status"] == "PASS"
    assert control["status"] == "PASS_PROJECTED_CONSTRUCTED_WITNESS"
    assert structure["status"] == "PASS_EXACT_PUBLIC_XOR_ROW_REPLAY"
    for receipt in (constructed, public):
        assert receipt["source_sha256"]["protocol"] == sha(HERE / "protocol.json")
    assert control["source_sha256"]["protocol"] == sha(HERE / "protocol.json")
    assert control["source_sha256"]["script"] == sha(HERE / "audit_control.py")
    assert structure["source_sha256"]["script"] == sha(HERE / "audit_structure.py")
    assert structure["source_sha256"]["protocol"] == sha(HERE / "protocol.json")
    assert result["source_sha256"]["protocol"] == sha(HERE / "protocol.json")
    assert result["source_sha256"]["public_projection_receipt"] == sha(
        HERE / "public/projection_receipt.json")
    assert result["source_sha256"]["constructed_control_audit"] == sha(
        HERE / "constructed/control_audit.json")
    assert result["source_sha256"]["projected_formula_gzip"] == sha(
        HERE / "public/projected.xcnf.gz")
    input_result = public["projection"]["source_result"]
    assert input_result["original_variables"] == 119952
    assert input_result["projected_variables"] == 87907
    assert input_result["original_cnf_clauses"] == 333529
    assert input_result["original_xor_rows"] == 43195
    assert input_result["projected_xor_rows"] == 11150
    assert input_result["private_pivots"] == 32045
    assert control["reverse_lifted_private_pivots"] == 32038
    assert structure["original_cnf_clauses_mapped_exactly"] == 333529
    assert structure["original_xor_rows_reduced"] == 43195
    assert structure["zero_pivot_rows"] == 32045
    assert structure["projected_xor_rows_matched_as_multiset"] == 11150
    assert result["charged_formula_projection_solver_seconds"] <= protocol[
        "total_construction_projection_search_cap_seconds"]
    assert result["monitor"]["sampled_peak_combined_rss_bytes"] < protocol["rss_cap_bytes"]
    assert result["monitor"]["stdout_sha256"] == sha(HERE / "public_solver/solver.stdout.txt")
    assert result["monitor"]["stderr_sha256"] == sha(HERE / "public_solver/solver.stderr.txt")
    solver_lines = (HERE / "public_solver/solver.stdout.txt").read_text(errors="replace").splitlines()
    assert any(line.startswith("c rst ") for line in solver_lines)
    assert any("[matrix]" in line for line in solver_lines)
    assert result["status"] in ("CENSORED_TIME", "SAT_MODEL_PENDING_CHECK", "UNSAT_FORMULA")
    if result["status"] == "CENSORED_TIME":
        assert result["solver_status_lines"] in ([], ["s INDETERMINATE"])
        assert result["model_lines"] == 0
    if result["status"] == "SAT_MODEL_PENDING_CHECK":
        assert result["solver_status_lines"] == ["s SATISFIABLE"]
        assert result["model_lines"] > 0
    restarts = [line for line in solver_lines if line.startswith("c rst ")]
    receipt = {
        "status": "PASS_PROJECTED_N131_TERMINAL_AUDIT",
        "candidate_id": None,
        "curve_id": protocol["curve_id"],
        "target_q": result["target_q"],
        "solver_status": result["status"],
        "same_public_point_and_original_formula": True,
        "cnf_private_xor_pivots_eliminated": input_result["private_pivots"],
        "projected_variables": input_result["projected_variables"],
        "projected_xor_rows": input_result["projected_xor_rows"],
        "last_logged_conflicts": restarts[-1].split()[6],
        "charged_seconds": result["charged_formula_projection_solver_seconds"],
        "sampled_peak_rss_bytes": result["monitor"]["sampled_peak_combined_rss_bytes"],
        "source_sha256": {name: sha(path) for name, path in {
            "script": Path(__file__),
            "protocol": HERE / "protocol.json",
            "constructed_projection": HERE / "constructed/projection_receipt.json",
            "constructed_control_audit": HERE / "constructed/control_audit.json",
            "public_projection": HERE / "public/projection_receipt.json",
            "public_structure_audit": HERE / "public/structure_audit.json",
            "solver_result": HERE / "public_solver/result.json",
            "solver_stdout": HERE / "public_solver/solver.stdout.txt",
            "solver_stderr": HERE / "public_solver/solver.stderr.txt",
        }.items()},
    }
    with (HERE / "terminal_audit.json").open("x") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": receipt["status"],
                      "solver_status": receipt["solver_status"],
                      "charged_seconds": receipt["charged_seconds"]}))


if __name__ == "__main__":
    main()
