#!/usr/bin/env python3
"""Measure capped WDSat searches on frozen ordinary N53/N83 XCNFs."""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ADAPTER = PARENT / "q20261011_wdsat_shared_prefix"
sys.path.insert(0, str(ADAPTER))
from prepare import evaluate  # noqa: E402


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("degree", type=int, choices=(53, 83))
    parser.add_argument("variant", choices=("plain", "xor_gauss"))
    args = parser.parse_args()
    name = f"n{args.degree}"
    out = HERE / "runs" / name / args.variant
    assert not out.exists()
    protocol_bytes = (HERE / "protocol.json").read_bytes()
    protocol = json.loads(protocol_bytes)
    freeze_bytes = (HERE / "freeze.json").read_bytes()
    freeze = json.loads(freeze_bytes)
    builder_bytes = (ADAPTER / "build_receipt.json").read_bytes()
    builder = json.loads(builder_bytes)
    assert freeze["protocol_sha256"] == sha(protocol_bytes)
    assert freeze["builder_receipt_sha256"] == sha(builder_bytes)
    record = freeze["cells"][name]
    archive = (HERE / f"{name}_ordinary.xcnf.gz").read_bytes()
    assert sha(archive) == record["derived_archive_sha256"]
    derived = gzip.decompress(archive)
    assert sha(derived) == record["derived_raw_sha256"]
    source_archive_path = PARENT / "runs" / f"{name}_q{1410 if args.degree == 53 else 1408}_ordinary.xcnf.gz"
    source_archive = source_archive_path.read_bytes()
    assert sha(source_archive) == record["source_archive_sha256"]
    original = gzip.decompress(source_archive)
    assert sha(original) == record["source_raw_sha256"]
    binary_record = builder["per_degree"][name]
    binary = Path(binary_record["binary_path"])
    assert sha(binary.read_bytes()) == binary_record["binary_sha256"]
    cap = protocol["limits"]["wall_seconds_per_attempt"]
    assert protocol["limits"]["address_space_mib"] is None
    command = [str(binary), "-i", "INPUT"] + (["-x"] if args.variant == "xor_gauss" else [])
    out.mkdir(parents=True)
    start = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="q1463_ordinary_") as directory:
        xcnf = Path(directory) / "system.xcnf"
        xcnf.write_bytes(derived)
        actual = [str(xcnf) if item == "INPUT" else item for item in command]
        try:
            process = subprocess.run(actual, capture_output=True, timeout=cap)
            stdout, stderr, returncode = process.stdout, process.stderr, process.returncode
            timed_out = False
        except subprocess.TimeoutExpired as error:
            stdout, stderr, returncode = error.stdout or b"", error.stderr or b"", None
            timed_out = True
    wall = time.monotonic() - start
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    (out / "solver.stdout.txt").write_bytes(stdout)
    (out / "solver.stderr.txt").write_bytes(stderr)
    text = stdout.decode("utf-8", "replace")
    error_text = stderr.decode("utf-8", "replace")
    variables = record["transform_stats"]["derived_variables"]
    models = [line.strip() for line in text.splitlines()
              if len(line.strip()) == variables and set(line.strip()) <= {"0", "1", "2"}]
    replay = None
    if timed_out:
        status = "BOUNDED_UNKNOWN" if "Q1458_SEARCH_START" in error_text else "CENSORED_BEFORE_SEARCH"
    elif returncode != 0:
        status = "PRODUCER_FAILURE"
    elif "UNSAT" in text:
        status = "UNSAT_REPORTED_UNVERIFIED"
    elif len(models) == 1 and set(models[0]) <= {"0", "1"}:
        model = {i + 1: value == "1" for i, value in enumerate(models[0])}
        try:
            transformed = evaluate(derived, model)
            projected = evaluate(original, {key: value for key, value in model.items()
                                            if key <= record["transform_stats"]["original_variables"]})
            replay = {"derived": transformed, "original": projected}
            status = "SAT_REPLAYED_XCNF"
        except (AssertionError, ValueError) as error:
            replay = {"error": repr(error)}
            status = "MODEL_REPLAY_FAILED"
    else:
        status = "PRODUCER_FAILURE_NO_MODEL"
    receipt = {"proposal_id": "Q1463", "candidate_id": None, "run_id": None,
               "curve_id": record["curve_id"], "isogeny": "none",
               "workload_id": record["workload_id"],
               "factor_base_actual_B": record["factor_base_actual_B"],
               "factor_base_folded_columns_K": record["factor_base_folded_columns_K"],
               "factor_base_enumerated_set_sha256": record["factor_base_enumerated_set_sha256"],
               "public_target": record["public_target"],
               "degree": args.degree, "variant": args.variant,
               "status": status, "model_replay": replay,
               "model_count": len(models), "return_code": returncode,
               "timed_out": timed_out,
               "after_xor_init": "Q1458_AFTER_XOR_INIT" in error_text,
               "search_started": "Q1458_SEARCH_START" in error_text,
               "wall_seconds_exploratory": wall,
               "user_cpu_seconds": usage.ru_utime,
               "system_cpu_seconds": usage.ru_stime,
               "maxrss_child_bytes_darwin": usage.ru_maxrss,
               "wall_limit_seconds": cap, "address_space_limit_mib": None,
               "ordinary_query": True,
               "verified_natural_relations": None if status == "SAT_REPLAYED_XCNF" else 0,
               "natural_relation_yield_estimate": None,
               "complete_solve_work_log2": None,
               "protocol_sha256": sha(protocol_bytes),
               "freeze_sha256": sha(freeze_bytes),
               "builder_receipt_sha256": sha(builder_bytes),
               "derived_archive_sha256": sha(archive),
               "source_archive_sha256": sha(source_archive),
               "binary_sha256": sha(binary.read_bytes()),
               "runner_sha256": sha(Path(__file__).read_bytes()),
               "stdout_sha256": sha(stdout), "stderr_sha256": sha(stderr),
               "command_template": command}
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2,
                                                 sort_keys=True) + "\n")
    print(json.dumps({"degree": args.degree, "variant": args.variant,
                      "status": status, "wall_seconds": wall,
                      "user_cpu_seconds": usage.ru_utime}))


if __name__ == "__main__":
    main()
