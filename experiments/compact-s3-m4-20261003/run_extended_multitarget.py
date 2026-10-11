#!/usr/bin/env python3
"""Extended ordinary n53 solve on the complete cofactor-preimage formula."""

import json
import re
import resource
import subprocess
import time
from pathlib import Path

from chain_s3_multitarget import build_multitarget, decode_choice
from run_probe import HERE, curves, field, lift, parse_model, sha

MAX_SECONDS = 120
MAX_CONFLICTS = 1_000_000
STEM = "n53_ordinary_multitarget_extended"


def main():
    stage_path = HERE / "runs/n53_ordinary_multitarget.json"
    coset_path = HERE / "runs/n53_ordinary_raw_preimages.json"
    formula_path = HERE / "runs/n53_ordinary_multitarget.xcnf"
    output = HERE / "runs" / f"{STEM}.json"
    stdout_path = HERE / "runs" / f"{STEM}.stdout.txt"
    stderr_path = HERE / "runs" / f"{STEM}.stderr.txt"
    assert not output.exists() and not stdout_path.exists()
    assert not stderr_path.exists()
    stage = json.loads(stage_path.read_text())
    coset = json.loads(coset_path.read_text())
    assert stage["proposal_id"] == "Q1306"
    assert stage["workload_kind"] == "ordinary"
    assert stage["raw_preimage_receipt_sha256"] == sha(coset_path)
    assert sha(formula_path) == stage["xcnf_sha256"]
    command = ["cryptominisat5", "--verb", "1", "--threads", "1",
               "--maxtime", str(MAX_SECONDS), "--maxconfl",
               str(MAX_CONFLICTS), str(formula_path)]
    start = time.perf_counter()
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                timeout=MAX_SECONDS)
        stdout, stderr, code = result.stdout, result.stderr, result.returncode
        status = ("sat" if code == 10 else "unsat" if code == 20
                  else "censored")
    except subprocess.TimeoutExpired as error:
        stdout = (error.stdout or b"").decode(errors="replace")
        stderr = (error.stderr or b"").decode(errors="replace")
        code, status = None, "external_timeout"
    wall_seconds = time.perf_counter() - start
    stdout_path.write_text(stdout)
    stderr_path.write_text(stderr)
    match = re.findall(r"conflicts\s*[:=]\s*([0-9]+)", stdout,
                       flags=re.IGNORECASE)
    conflicts = int(match[-1]) if match else None
    relation = None
    choice = None
    lift_status = None
    values = parse_model(stdout)
    if values is not None:
        onb = field.Onb(53)
        curve = curves.Curve(onb)
        xs = coset["raw_target_x_coordinates"]
        formula, leaves, _, target, selector = build_multitarget(53, 3, xs)
        assert formula.variables == stage["formula_variables"]
        choice = decode_choice(selector, values)
        assert choice < len(xs)
        target_x = sum(1 << i for i, bit in enumerate(target)
                       if values.get(bit, False))
        assert target_x == xs[choice]
        raw = tuple(int(v) for v in coset["raw_target_points"][choice])
        public = tuple(int(v) for v in stage["public_target"])
        _, relation, lift_status = lift(onb, curve, leaves, values, raw,
                                        public, 428)
    report = {
        "kind": "extended_complete_preimage_s3_n53_ordinary_stage_probe",
        "proposal_id": "Q1306",
        "candidate_id": None,
        "run_id": None,
        "workload_id": stage["workload_id"],
        "curve_id": stage["curve_id"],
        "isogeny": "none",
        "status": status,
        "return_code": code,
        "solver_wall_seconds": wall_seconds,
        "solver_conflicts_reported": conflicts,
        "chosen_preimage_index": choice,
        "verified_relation": relation,
        "lift_status": lift_status,
        "formula_precomputed": True,
        "formula_sha256": sha(formula_path),
        "max_seconds": MAX_SECONDS,
        "max_conflicts": MAX_CONFLICTS,
        "command": command,
        "stdout_sha256": sha(stdout_path),
        "stderr_sha256": sha(stderr_path),
        "peak_child_rss_raw": resource.getrusage(
            resource.RUSAGE_CHILDREN).ru_maxrss,
        "peak_child_rss_units": "bytes on Darwin, KiB on Linux",
        "matched_stage_receipt_sha256": sha(stage_path),
        "coset_receipt_sha256": sha(coset_path),
        "multitarget_source_sha256": sha(HERE / "chain_s3_multitarget.py"),
        "runner_source_sha256": sha(Path(__file__)),
        "complete_solve_work_log2": None,
    }
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": status, "solver_wall_seconds": wall_seconds,
                      "conflicts": conflicts, "chosen_preimage_index": choice,
                      "verified_relation": relation is not None}))


if __name__ == "__main__":
    main()
