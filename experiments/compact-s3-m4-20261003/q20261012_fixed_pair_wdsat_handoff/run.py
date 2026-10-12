#!/usr/bin/env python3
"""Bound one exact direct-handoff WDSat run and independently replay a model."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import resource
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1513 = PARENT / "q20261012_fixed_pair_s3_handoff"
Q1459 = PARENT / "q20261011_wdsat_width_lift"
BUILD = json.loads((PARENT / "q20261011_wdsat_phase_restart/build_receipt.json").read_text())
sys.path.insert(0, str(Q1459))
from prepare import evaluate  # noqa: E402
sys.path.insert(0, str(Q1513))
from run import build, verify  # noqa: E402


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main(args):
    prepared = json.loads((HERE / "prepare_receipt.json").read_text())
    record = prepared["cells"][args.label]
    source_receipt = json.loads((Q1513 / f"{args.label}.json").read_text())
    source = (Q1513 / f"{args.label}.xcnf").read_bytes()
    derived = (HERE / f"{args.label}.width4.xcnf").read_bytes()
    assert sha(source) == record["source_sha256"]
    assert sha(derived) == record["derived_sha256"]
    binary_record = (json.loads((HERE / "build_direct_receipt.json").read_text())
                     if args.binary == "direct" else BUILD)
    binary = Path(binary_record["binary_path"])
    assert sha(binary.read_bytes()) == binary_record["binary_sha256"]
    assert record["derived_variables"] <= BUILD["config"]["MAX_ID"]
    assert record["derived_rows"] - record["xor_rows"] <= BUILD["config"]["MAX_EQ"]
    assert record["xor_rows"] <= BUILD["config"]["MAX_XEQ"]
    env = os.environ.copy()
    env["Q1469_ORDER_MODE"] = args.order
    env["Q1472_PHASE_INDEX"] = "0"
    command = [str(binary), "-i", str(HERE / f"{args.label}.width4.xcnf")]
    started = time.perf_counter_ns()
    try:
        child = subprocess.run(command, capture_output=True, timeout=args.wall_cap, env=env)
        stdout, stderr, code = child.stdout, child.stderr, child.returncode
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        stdout, stderr, code = exc.stdout or b"", exc.stderr or b"", None
        timed_out = True
    elapsed = (time.perf_counter_ns() - started) / 1e9
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    (HERE / f"{args.label}.{args.order}.stdout.txt").write_bytes(stdout)
    (HERE / f"{args.label}.{args.order}.stderr.txt").write_bytes(stderr)
    output = stdout.decode(errors="replace")
    errors = stderr.decode(errors="replace")
    model_lines = [line.strip() for line in output.splitlines()
                   if len(line.strip()) == record["derived_variables"]
                   and set(line.strip()) <= {"0", "1", "2"}]
    replay = None
    if len(model_lines) == 1 and set(model_lines[0]) <= {"0", "1"}:
        model = {i + 1: char == "1" for i, char in enumerate(model_lines[0])}
        derived_check = evaluate(derived, model)
        original_model = {i: model[i] for i in range(1, record["original_variables"] + 1)}
        original_check = evaluate(source, original_model)
        formula, raw, leaves, onb = build(source_receipt["n"], source_receipt["complement_x_coords"])
        from run import pin_bits  # noqa: E402
        for bits, value in zip(raw, source_receipt["pin_raw"]):
            pin_bits(formula, bits, value)
        for bits, value in zip(leaves, source_receipt["pin_projected"]):
            pin_bits(formula, bits, value)
        group_check = verify(formula, raw, leaves, onb,
                             source_receipt["complement_x_coords"], original_model)
        replay = {"derived_xcnf": derived_check, "source_xcnf": original_check,
                  "curve": group_check}
    checkpoints = [int(x) for x in re.findall(r"^Q1464_BRANCH (\d+)$", errors, re.M)]
    cap = [int(x) for x in re.findall(r"^Q1464_BRANCH_CAP (\d+)$", errors, re.M)]
    if replay:
        status = "SAT_VERIFIED"
    elif timed_out:
        status = "WALL_TIMEOUT_SEARCH_STARTED" if "Q1458_SEARCH_START" in errors else "WALL_TIMEOUT_BEFORE_SEARCH"
    elif code == 42 and cap == [1048576]:
        status = "BRANCH_CAP_SEARCH_STARTED"
    elif code != 0:
        status = "PRODUCER_FAILURE"
    elif "UNSAT" in output:
        status = "UNSAT_REPORTED_UNVERIFIED"
    else:
        status = "NO_MODEL"
    result = {"proposal_id": "Q1514", "candidate_id": None, "run_id": None,
              "isogeny": "none", "label": args.label, "order": args.order,
              "binary_variant": args.binary,
              "status": status, "search_started": "Q1458_SEARCH_START" in errors,
              "after_xor_init": "Q1458_AFTER_XOR_INIT" in errors,
              "branch_checkpoints": checkpoints, "branch_cap_markers": cap,
              "return_code": code, "wall_cap_seconds": args.wall_cap,
              "solver_wall_seconds_exploratory": elapsed,
              "child_user_cpu_seconds": usage.ru_utime,
              "child_system_cpu_seconds": usage.ru_stime,
              "child_peak_rss_bytes_darwin": usage.ru_maxrss,
              "source_sha256": sha(source), "derived_sha256": sha(derived),
              "binary_sha256": binary_record["binary_sha256"],
              "stdout_sha256": sha(stdout), "stderr_sha256": sha(stderr),
              "model_replay": replay, "command": command}
    (HERE / f"{args.label}.{args.order}.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: result[k] for k in ("label", "order", "status", "return_code",
                                               "search_started", "after_xor_init",
                                               "branch_checkpoints", "solver_wall_seconds_exploratory",
                                               "child_peak_rss_bytes_darwin")}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("label", choices=("n53_known_pair_pinned", "n53_known_complement_unpinned",
                                          "n83_planted_pinned", "n83_ordinary_selected",
                                          "n83_ordinary_holdout"))
    parser.add_argument("--order", choices=("selector_pair_mids", "selector_mid_interleave",
                                             "selector_leaf_interleave", "direct_raw_interleave"),
                        default="selector_pair_mids")
    parser.add_argument("--binary", choices=("prior", "direct"), default="prior")
    parser.add_argument("--wall-cap", type=int, default=20)
    main(parser.parse_args())
