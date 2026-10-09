#!/usr/bin/env python3
"""Independently reconcile the frozen WDSat control and ordinary stage."""

import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
BASE = GOAL / "fill_controlled_projection_20261009/n41_budget1"
VERIFIER = GOAL / "n131_phi_torsion_frobenius_domains_20261005/m16_prefix_audit_20261006/verify_xcnf_model.py"


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def check_hash(path, expected):
    if sha(path) != expected:
        raise ValueError("digest mismatch: " + str(path))


def main():
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    formula = BASE / "projected.xcnf"
    pinned = HERE / "fully_fixed_control.xcnf"
    control = BASE / "projected_control_model.stdout.txt"
    solver = HERE / "wdsat/wdsat_solver"
    runtime = HERE / "sage_runtime_info.json"
    for path, key in ((formula, "formula_sha256"), (pinned, "pinned_sha256"),
                      (control, "control_model_sha256"), (solver, "solver_sha256"),
                      (HERE / "run_gate.py", "runner_sha256"),
                      (VERIFIER, "verifier_sha256")):
        check_hash(path, protocol[key])
    for name, digest in protocol["solver_source_sha256"].items():
        check_hash(HERE / "wdsat/src" / name, digest)
    if json.loads(runtime.read_text())["status"] != "verified":
        raise ValueError("checked Sage runtime receipt failed")
    spec = importlib.util.spec_from_file_location("xcnf_verifier", VERIFIER)
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    if verifier.verify(formula, control)["status"] != "PASS":
        raise ValueError("source control fails original public formula")
    if verifier.verify(pinned, control)["status"] != "PASS":
        raise ValueError("source control fails pinned formula")

    receipts = {}
    for mode, input_path in (("pinned", pinned), ("ordinary", formula)):
        directory = HERE / mode
        receipt_path = directory / "receipt.json"
        receipt = json.loads(receipt_path.read_text())
        out = directory / "solver.stdout.txt"
        err = directory / "solver.stderr.txt"
        for path, key in ((input_path, "input_sha256"),
                          (protocol_path, "protocol_sha256"),
                          (runtime, "runtime_info_sha256"),
                          (solver, "solver_sha256"),
                          (out, "stdout_sha256"),
                          (err, "stderr_sha256")):
            check_hash(path, receipt[key])
        expected_command = [str(solver), "-i", str(input_path), "-n", "41",
                            "-m", "7", "-l", "41"]
        if (receipt["command"] != expected_command or
                receipt["mode"] != mode or
                receipt["target_count"] != 1 or
                receipt["workload_id"] != protocol["workload_id"] or
                receipt["curve_id"] != protocol["curve_id"] or
                receipt["sampled_peak_group_rss_bytes"] >= protocol["memory_cap_bytes"]):
            raise ValueError("run identity, command, or memory mismatch")
        receipts[mode] = receipt

    fixed = receipts["pinned"]
    if (fixed["status"] != "PINNED_MODEL_PASS" or
            fixed["model_count"] != 1 or fixed["exit_code"] != 0 or
            fixed["stop_reason"] is not None or
            fixed["xcnf_model_check"]["status"] != "PASS"):
        raise ValueError("pinned result disagrees with raw classification")
    returned = HERE / "pinned/solver_model.stdout.txt"
    if verifier.verify(pinned, returned) != fixed["xcnf_model_check"]:
        raise ValueError("returned pinned model fails independent replay")
    if verifier.model_from_stdout(returned, 40313) != verifier.model_from_stdout(control, 40313):
        raise ValueError("returned pinned assignment differs")

    ordinary = receipts["ordinary"]
    out = HERE / "ordinary/solver.stdout.txt"
    err = HERE / "ordinary/solver.stderr.txt"
    if (ordinary["status"] != "CENSORED_TIME" or
            ordinary["stop_reason"] != "WALL_CAP" or
            ordinary["exit_code"] != -2 or
            ordinary["model_count"] != 0 or
            ordinary["xcnf_model_check"] is not None or
            out.stat().st_size != 0 or err.stat().st_size != 0 or
            not 240 <= ordinary["solver_wall_seconds"] < 251 or
            ordinary["started_unix_ns"] <= fixed["started_unix_ns"]):
        raise ValueError("ordinary terminal receipt disagrees with raw output")
    result = {
        "status": "PASS", "ordinary_classification": "CENSORED_TIME",
        "pinned_classification": "PINNED_MODEL_PASS",
        "ordinary_model_count": 0,
        "ordinary_solver_wall_seconds": ordinary["solver_wall_seconds"],
        "ordinary_sampled_peak_group_rss_bytes": ordinary["sampled_peak_group_rss_bytes"],
        "source_sha256": {
            "protocol": sha(protocol_path), "runtime": sha(runtime),
            "formula": sha(formula), "pinned_formula": sha(pinned),
            "solver": sha(solver), "pinned_receipt": sha(HERE / "pinned/receipt.json"),
            "ordinary_receipt": sha(HERE / "ordinary/receipt.json"),
            "pinned_output": sha(HERE / "pinned/solver.stdout.txt"),
            "ordinary_output": sha(out), "auditor": sha(Path(__file__)),
        },
    }
    output = HERE / "independent_terminal_audit.json"
    if output.exists():
        raise FileExistsError(output)
    output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in
                      ("status", "ordinary_classification", "ordinary_model_count")}))


if __name__ == "__main__":
    main()
