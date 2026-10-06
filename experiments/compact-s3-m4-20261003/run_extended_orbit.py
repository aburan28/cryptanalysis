#!/usr/bin/env python3
"""Extended ordinary n53 solve on the cofactor and Frobenius target orbit."""

import json
import re
import resource
import subprocess
import time
from pathlib import Path

from chain_s3_orbit import build_orbit, decode_orbit_choice
from run_probe import HERE, curves, field, lift, parse_model, sha

MAX_SECONDS = 180
MAX_CONFLICTS = 1_000_000
STEM = "n53_ordinary_orbit_extended"


def main():
    stage_path = HERE / "runs/n53_ordinary_orbit.json"
    coset_path = HERE / "runs/n53_ordinary_raw_preimages.json"
    formula_path = HERE / "runs/n53_ordinary_orbit.xcnf"
    output = HERE / "runs" / f"{STEM}.json"
    stdout_path = HERE / "runs" / f"{STEM}.stdout.txt"
    stderr_path = HERE / "runs" / f"{STEM}.stderr.txt"
    assert not output.exists() and not stdout_path.exists()
    assert not stderr_path.exists()
    stage = json.loads(stage_path.read_text())
    coset = json.loads(coset_path.read_text())
    assert stage["proposal_id"] == "Q1309"
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
    shift = None
    lift_status = None
    values = parse_model(stdout)
    if values is not None:
        onb = field.Onb(53)
        curve = curves.Curve(onb)
        xs = coset["raw_target_x_coordinates"]
        formula, leaves, _, target, pre_selector, shift_selector = build_orbit(
            53, 3, xs)
        assert formula.variables == stage["formula_variables"]
        choice, shift = decode_orbit_choice(pre_selector, shift_selector,
                                            values)
        assert choice < len(xs) and shift < 53
        target_x = sum(1 << i for i, bit in enumerate(target)
                       if values.get(bit, False))
        raw = tuple(int(v) for v in coset["raw_target_points"][choice])
        public = tuple(int(v) for v in stage["public_target"])
        shifted_raw = curve.frob(raw, shift)
        shifted_public = curve.frob(public, shift)
        assert target_x == onb.toCoords(shifted_raw[0])
        _, relation, lift_status = lift(onb, curve, leaves, values,
                                        shifted_raw, shifted_public, 428)
        if relation is not None:
            original_points = []
            for encoded, sign in zip(relation["projected_points"],
                                     relation["signs"]):
                projected = tuple(int(v) for v in encoded)
                signed = projected if sign == 1 else curve.neg(projected)
                original_points.append(curve.frob(signed, 53 - shift))
            total = None
            for point in original_points:
                total = curve.add(total, point)
            assert total == public
            relation["original_public_target"] = [str(v) for v in public]
            relation["original_target_projected_points"] = [
                [str(v) for v in point] for point in original_points]
    report = {
        "kind": "extended_cofactor_frobenius_orbit_s3_n53_ordinary_probe",
        "proposal_id": "Q1309",
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
        "chosen_frobenius_shift": shift,
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
        "orbit_source_sha256": sha(HERE / "chain_s3_orbit.py"),
        "runner_source_sha256": sha(Path(__file__)),
        "complete_solve_work_log2": None,
    }
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": status, "solver_wall_seconds": wall_seconds,
                      "conflicts": conflicts, "chosen_preimage_index": choice,
                      "chosen_frobenius_shift": shift,
                      "verified_relation": relation is not None}))


if __name__ == "__main__":
    main()
