#!/usr/bin/env python3
"""Run exact width-four WDSat controls and replay models against both XCNFs."""
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

from prepare import evaluate

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(cell: str, variant: str) -> None:
    protocol_bytes = (HERE / "protocol.json").read_bytes()
    protocol = json.loads(protocol_bytes)
    freeze_bytes = (HERE / "freeze.json").read_bytes()
    freeze = json.loads(freeze_bytes)
    prepare_bytes = (HERE / "prepare_receipt.json").read_bytes()
    prepared = json.loads(prepare_bytes)
    build_bytes = (HERE / "build_receipt.json").read_bytes()
    build = json.loads(build_bytes)
    assert freeze["protocol_sha256"] == sha(protocol_bytes)
    assert freeze["prepare_receipt_sha256"] == sha(prepare_bytes)
    assert build["freeze_sha256"] == sha(freeze_bytes)
    assert cell in protocol["cells"]
    assert variant in protocol["upstream_solver"]["variants"]
    degree = cell.split("_")[0]
    if "free_mids" in cell:
        for control_degree in ("n53", "n83"):
            control = HERE / "runs" / f"{control_degree}_full_lock" / variant / "receipt.json"
            assert control.exists() and json.loads(control.read_text())["status"] == "SAT_REPLAYED_BOTH"
    dest = HERE / "runs" / cell / variant
    assert not dest.exists()
    dest.mkdir(parents=True)
    prepared_cell = prepared["cells"][cell]
    archive = (HERE / f"{cell}.xcnf.gz").read_bytes()
    assert sha(archive) == prepared_cell["derived_archive_sha256"]
    derived = gzip.decompress(archive)
    assert sha(derived) == prepared_cell["derived_raw_sha256"]
    original_archive = (PARENT / "q1419_partial_pin" / "runs" / cell /
                        "system.xcnf.gz").read_bytes()
    assert sha(original_archive) == prepared_cell["source_archive_sha256"]
    original = gzip.decompress(original_archive)
    assert sha(original) == prepared_cell["source_raw_sha256"]
    binary_record = build["per_degree"][degree]
    assert binary_record["return_code"] == 0
    binary = Path(binary_record["binary_path"])
    assert sha(binary.read_bytes()) == binary_record["binary_sha256"]
    cap = protocol["limits"]["wall_seconds_per_cell"]
    assert protocol["limits"]["address_space_mib_per_cell"] is None
    command = [str(binary), "-i", "INPUT"] + (["-x"] if variant == "xor_gauss" else [])
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="q1460_xcnf_") as directory:
        path = Path(directory) / "system.xcnf"
        path.write_bytes(derived)
        actual = [str(path) if arg == "INPUT" else arg for arg in command]
        try:
            proc = subprocess.run(actual, capture_output=True, timeout=cap)
            stdout, stderr, returncode = proc.stdout, proc.stderr, proc.returncode
            timed_out = False
        except subprocess.TimeoutExpired as error:
            stdout, stderr, returncode = error.stdout or b"", error.stderr or b"", None
            timed_out = True
    elapsed = time.monotonic() - started
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    (dest / "solver.stdout.txt").write_bytes(stdout)
    (dest / "solver.stderr.txt").write_bytes(stderr)
    text = stdout.decode("utf-8", "replace")
    error_text = stderr.decode("utf-8", "replace")
    var_count = prepared_cell["derived_variables"]
    models = [line.strip() for line in text.splitlines()
              if len(line.strip()) == var_count and set(line.strip()) <= {"0", "1", "2"}]
    model_replay = None
    if timed_out:
        status = "BOUNDED_UNKNOWN" if "Q1458_SEARCH_START" in error_text else "CENSORED_BEFORE_SEARCH"
    elif returncode != 0:
        status = "PRODUCER_FAILURE"
    elif "UNSAT" in text:
        status = "UNSAT_REPORTED_AGAINST_WITNESS"
    elif len(models) == 1 and set(models[0]) <= {"0", "1"}:
        model = {i+1: value == "1" for i, value in enumerate(models[0])}
        try:
            transformed = evaluate(derived, model)
            projected = evaluate(original, {key: value for key, value in model.items()
                                            if key <= prepared_cell["original_variables"]})
            model_replay = {"derived": transformed, "original": projected}
            status = "SAT_REPLAYED_BOTH"
        except (AssertionError, ValueError) as error:
            status = "MODEL_REPLAY_FAILED"
            model_replay = {"error": repr(error)}
    else:
        status = "PRODUCER_FAILURE_NO_STATUS"
    receipt = {"proposal_id": "Q1460", "candidate_id": None, "run_id": None,
               "isogeny": "none", "cell": cell, "variant": variant,
               "curve_id": "EC1N53Ckb1hf77aab617904" if degree == "n53" else "EC1N83Ckb1h876c2921cb64",
               "status": status, "model_replay": model_replay,
               "model_count": len(models), "return_code": returncode,
               "timed_out": timed_out,
               "after_xor_init": "Q1458_AFTER_XOR_INIT" in error_text,
               "search_started": "Q1458_SEARCH_START" in error_text,
               "wall_seconds_exploratory": elapsed,
               "user_cpu_seconds": usage.ru_utime,
               "system_cpu_seconds": usage.ru_stime,
               "maxrss_child_bytes_darwin": usage.ru_maxrss,
               "resource_limit_wall_seconds": cap,
               "resource_limit_address_space_mib": None,
               "freeze_sha256": sha(freeze_bytes),
               "prepare_receipt_sha256": sha(prepare_bytes),
               "build_receipt_sha256": sha(build_bytes),
               "derived_archive_sha256": sha(archive),
               "derived_raw_sha256": sha(derived),
               "source_archive_sha256": sha(original_archive),
               "source_raw_sha256": sha(original),
               "binary_sha256": sha(binary.read_bytes()),
               "runner_sha256": sha(Path(__file__).read_bytes()),
               "stdout_sha256": sha(stdout), "stderr_sha256": sha(stderr),
               "command_template": command,
               "host_isolation": "none; wall times exploratory",
               "ordinary_relation_yield": None, "complete_solve_work_log2": None}
    (dest / "receipt.json").write_text(json.dumps(receipt, indent=2,
                                                  sort_keys=True) + "\n")
    print(json.dumps({"cell": cell, "variant": variant, "status": status,
                      "wall_seconds": elapsed,
                      "maxrss_bytes_darwin": usage.ru_maxrss}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cell", choices=["n53_full_lock", "n53_free_mids",
                                          "n83_full_lock", "n83_free_mids"])
    parser.add_argument("variant", choices=["plain", "xor_gauss"])
    args = parser.parse_args()
    run(args.cell, args.variant)


if __name__ == "__main__":
    main()
