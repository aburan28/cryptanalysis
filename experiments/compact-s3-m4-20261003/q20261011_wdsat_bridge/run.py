#!/usr/bin/env python3
"""Run pinned WDSat on frozen Q1419 formulas and replay every SAT row."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import resource
import subprocess
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check_model(raw: bytes, digits: str) -> dict:
    """Evaluate serialized CNF and XOR rows, without calling the formula writer."""
    lines = raw.splitlines()
    header = lines[0].split()
    assert header[:2] == [b"p", b"cnf"] and len(header) == 4
    variables, rows = map(int, header[2:])
    assert len(digits) == variables and set(digits) <= {"0", "1"}
    bits = bytes(1 if value == 49 else 0 for value in digits.encode("ascii"))
    clauses = xors = 0
    for line in lines[1:]:
        tokens = line.split()
        assert tokens and tokens[-1] == b"0"
        if tokens[0].startswith(b"x"):
            first = int(tokens[0][1:])
            literals = [first, *(int(t) for t in tokens[1:-1])]
            assert all(1 <= abs(lit) <= variables for lit in literals)
            assert all(lit > 0 for lit in literals[1:])
            wanted = first > 0
            assert (sum(bits[abs(lit) - 1] for lit in literals) & 1) == wanted
            xors += 1
        else:
            literals = [int(t) for t in tokens[:-1]]
            assert all(1 <= abs(lit) <= variables for lit in literals)
            assert any(bits[abs(lit) - 1] == (lit > 0) for lit in literals)
            clauses += 1
    assert clauses + xors == rows
    return {"variables": variables, "cnf_clauses": clauses, "xor_rows": xors}


def run(cell: str, variant: str) -> dict:
    protocol = json.loads((HERE / "protocol.json").read_text())
    freeze_bytes = (HERE / "freeze.json").read_bytes()
    freeze = json.loads(freeze_bytes)
    build_bytes = (HERE / "build_receipt.json").read_bytes()
    build = json.loads(build_bytes)
    assert freeze["protocol_sha256"] == sha((HERE / "protocol.json").read_bytes())
    assert build["freeze_sha256"] == sha(freeze_bytes)
    assert cell in protocol["cells"] and variant in protocol["upstream_solver"]["variants"]
    degree = cell.split("_")[0]
    run_dir = HERE / "runs" / cell / variant
    assert not run_dir.exists(), run_dir
    run_dir.mkdir(parents=True)
    input_path = PARENT / "q1419_partial_pin" / "runs" / cell / "system.xcnf.gz"
    archive = input_path.read_bytes()
    frozen = freeze["cells"][cell]
    assert sha(archive) == frozen["formula_archive_sha256"]
    raw = gzip.decompress(archive)
    assert sha(raw) == frozen["formula_raw_sha256"]
    binary = Path(build["per_degree"][degree]["binary_path"])
    assert sha(binary.read_bytes()) == build["per_degree"][degree]["binary_sha256"]
    cap_s = protocol["limits"]["wall_seconds_per_cell"]
    mem_mib = protocol["limits"]["address_space_mib_per_cell"]
    assert mem_mib is None
    cmd = [str(binary), "-i", "INPUT"] + (["-x"] if variant == "xor_gauss" else [])
    start = time.monotonic()
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    with tempfile.TemporaryDirectory(prefix="q1458_xcnf_") as directory:
        raw_path = Path(directory) / "system.xcnf"
        raw_path.write_bytes(raw)
        actual = [str(raw_path) if part == "INPUT" else part for part in cmd]
        try:
            process = subprocess.run(actual, capture_output=True, timeout=cap_s)
            stdout, stderr = process.stdout, process.stderr
            returncode = process.returncode
            timed_out = False
        except subprocess.TimeoutExpired as error:
            stdout, stderr = error.stdout or b"", error.stderr or b""
            returncode = None
            timed_out = True
    elapsed = time.monotonic() - start
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    (run_dir / "solver.stdout.txt").write_bytes(stdout)
    (run_dir / "solver.stderr.txt").write_bytes(stderr)
    text = stdout.decode("utf-8", "replace")
    error_text = stderr.decode("utf-8", "replace")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    variables = frozen["formula"]["variables"]
    models = [line for line in lines if len(line) == variables and set(line) <= {"0", "1", "2"}]
    model_check = None
    if timed_out:
        status = "BOUNDED_UNKNOWN" if "Q1458_SEARCH_START" in error_text else "CENSORED_BEFORE_SEARCH"
    elif returncode != 0:
        status = "PRODUCER_FAILURE"
    elif "UNSAT" in text:
        status = "UNSAT_REPORTED"
    elif len(models) == 1:
        try:
            model_check = check_model(raw, models[0])
            assert all(model_check[key] == frozen["formula"][key] for key in model_check)
            status = "SAT_VERIFIED_XCNF"
        except (AssertionError, ValueError) as error:
            status = "MODEL_REPLAY_FAILED"
            model_check = {"error": repr(error)}
    else:
        status = "PRODUCER_FAILURE_NO_STATUS"
    result = {
        "proposal_id": "Q1458", "candidate_id": None, "run_id": None,
        "curve_id": frozen["curve_id"], "stage_config_id": frozen["stage_config_id"],
        "workload_id": frozen["workload_id"], "cell": cell, "variant": variant,
        "isogeny": "none", "status": status, "model_check": model_check,
        "search_result_reported": bool(models or "UNSAT" in text),
        "after_xor_init": "Q1458_AFTER_XOR_INIT" in error_text,
        "search_started": "Q1458_SEARCH_START" in error_text,
        "model_count": len(models), "return_code": returncode,
        "timed_out": timed_out, "wall_seconds_exploratory": elapsed,
        "user_cpu_seconds": after.ru_utime - before.ru_utime,
        "system_cpu_seconds": after.ru_stime - before.ru_stime,
        "maxrss_child_bytes_darwin": after.ru_maxrss,
        "resource_limit_wall_seconds": cap_s,
        "resource_limit_address_space_mib": mem_mib,
        "memory_limit_note": protocol["limits"]["memory_limit_note"],
        "input_archive_sha256": sha(archive), "input_raw_sha256": sha(raw),
        "freeze_sha256": sha(freeze_bytes), "build_receipt_sha256": sha(build_bytes),
        "binary_sha256": sha(binary.read_bytes()),
        "runner_sha256": sha(Path(__file__).read_bytes()),
        "stdout_sha256": sha(stdout), "stderr_sha256": sha(stderr),
        "command_template": cmd,
        "host_isolation": "none; wall-time ratios exploratory",
        "ordinary_relation_yield": None, "complete_solve_work_log2": None,
    }
    (run_dir / "receipt.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"cell": cell, "variant": variant, "status": status,
                      "wall_seconds": elapsed,
                      "maxrss_bytes_darwin": after.ru_maxrss}))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cell", choices=["n53_full_lock", "n83_full_lock",
                                          "n53_free_mids", "n83_free_mids"])
    parser.add_argument("variant", choices=["plain", "xor_gauss"])
    args = parser.parse_args()
    if "free_mids" in args.cell:
        for degree in ("n53", "n83"):
            path = HERE / "runs" / f"{degree}_full_lock" / args.variant / "receipt.json"
            assert path.exists() and json.loads(path.read_text())["status"] == "SAT_VERIFIED_XCNF"
    run(args.cell, args.variant)


if __name__ == "__main__":
    main()
