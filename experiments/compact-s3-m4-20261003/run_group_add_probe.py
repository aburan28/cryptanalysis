#!/usr/bin/env python3
"""Bounded full group-addition PDP stage on frozen public targets."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import resource
import shutil
import subprocess
import time
from pathlib import Path

from chain_group_add import (build_exact_base_group_chain,
                             build_projected_sparse_group_chain)
from chain_s3_base_orbit import decode_base_choice
from run_base_orbit_probe import read_inputs, witness_points
from run_probe import HERE, curves, field, parse_model, sha


def coordinates(bits, model):
    return sum(1 << position for position, bit in enumerate(bits)
               if model.get(bit, False))


def verify_model(n, raw_leaves, choices, leaves, model, onb, curve,
                 order, keys, public):
    points = []
    key_set = set(keys)
    for x_bits, y_bits in leaves:
        x = coordinates(x_bits, model)
        y = coordinates(y_bits, model)
        point = (onb.fromCoords(x), onb.fromCoords(y))
        assert point[0] and curve.onCurve(point)
        assert curve.mul(point, order) is None
        orbit = [onb.toCoords(onb.frob(point[0], shift))
                 for shift in range(n)]
        assert min(orbit) in key_set
        points.append(point)
    total = None
    for point in points:
        total = curve.add(total, point)
    assert total == public
    raw_x = None
    decoded_choices = None
    if n == 53:
        decoded_choices = [decode_base_choice(choice, model)
                           for choice in choices]
        for (index, shift), point in zip(decoded_choices, points):
            expected = onb.frob(onb.fromCoords(keys[index]), shift)
            assert expected == point[0]
    else:
        raw_x = [coordinates(bits, model) for bits in raw_leaves]
        for raw, subgroup in zip(raw_x, points):
            assert 0 < raw < 1 << n and raw.bit_count() <= 4
            raw_point = curve.pointFromX(onb.fromCoords(raw))
            assert raw_point is not None
            projection = curve.mul(raw_point, 4)
            assert projection is not None and projection[0] == subgroup[0]
    return {
        "leaf_points": [[int(x), int(y)] for x, y in points],
        "raw_x_coordinates": raw_x,
        "orbit_choices": decoded_choices,
        "verified_public_sum": [int(public[0]), int(public[1])],
    }


def solve(path, binary, seconds, conflicts):
    command = [str(binary), "--verb", "1", "--threads", "1",
               "--maxconfl", str(conflicts), str(path)]
    started = time.perf_counter()
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                timeout=max(0.01, seconds))
        stdout, stderr, code = (result.stdout, result.stderr,
                                result.returncode)
        status = "sat" if code == 10 else "unsat" if code == 20 else "censored"
    except subprocess.TimeoutExpired as error:
        stdout = (error.stdout or b"").decode(errors="replace")
        stderr = (error.stderr or b"").decode(errors="replace")
        code, status = None, "external_timeout"
    matches = re.findall(r"conflicts\s*[:=]\s*([0-9]+)", stdout,
                         flags=re.IGNORECASE)
    return {
        "command": command,
        "status": status,
        "return_code": code,
        "wall_seconds": time.perf_counter() - started,
        "conflicts_reported": int(matches[-1]) if matches else None,
        "stdout": stdout,
        "stderr": stderr,
        "model": parse_model(stdout),
    }


def stats(formula):
    return {
        "variables": formula.variables,
        "cnf_clauses": len(formula.clauses),
        "xor_rows": len(formula.xors),
        "and_gates": len(formula.and_cache),
        "cnf_literal_occurrences": sum(len(row) for row in formula.clauses),
        "xor_literal_occurrences": sum(len(row) for row, _ in formula.xors),
    }


def archive(path):
    compressed = path.with_suffix(path.suffix + ".gz")
    with compressed.open("wb") as stream:
        with gzip.GzipFile(filename="", mode="wb", fileobj=stream,
                           mtime=0, compresslevel=9) as zipped:
            with path.open("rb") as source:
                for chunk in iter(lambda: source.read(1 << 20), b""):
                    zipped.write(chunk)
    size, digest = path.stat().st_size, sha(path)
    path.unlink()
    return compressed, size, digest


def pin_known_witness(formula, raw_leaves, leaves, baseline, points, onb):
    if raw_leaves is not None:
        for bits, value in zip(raw_leaves,
                               baseline["fixture"]["planted_leaf_x"]):
            formula.clauses.extend(([
                bit if value >> position & 1 else -bit]
                for position, bit in enumerate(bits)))
    for (x_bits, y_bits), point in zip(leaves, points):
        for bits, value in ((x_bits, onb.toCoords(point[0])),
                            (y_bits, onb.toCoords(point[1]))):
            formula.clauses.extend(([
                bit if value >> position & 1 else -bit]
                for position, bit in enumerate(bits)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, choices=(53, 83), required=True)
    parser.add_argument("--kind", choices=("ordinary", "planted"),
                        required=True)
    parser.add_argument("--max-seconds", type=int, default=120)
    parser.add_argument("--max-conflicts", type=int, default=1_000_000)
    args = parser.parse_args()
    assert args.n == 83 or args.kind == "ordinary"
    assert args.max_seconds > 0 and args.max_conflicts > 0
    n, kind = args.n, args.kind
    stem = f"n{n}_{kind}_group_add"
    output = HERE / "runs" / f"{stem}.json"
    formula_path = HERE / "runs" / f"{stem}.xcnf"
    control_path = HERE / "runs" / f"{stem}.locked.xcnf"
    stdout_path = HERE / "runs" / f"{stem}.stdout.txt"
    stderr_path = HERE / "runs" / f"{stem}.stderr.txt"
    control_stdout = HERE / "runs" / f"{stem}.locked.stdout.txt"
    control_stderr = HERE / "runs" / f"{stem}.locked.stderr.txt"
    assert not any(path.exists() for path in (
        output, formula_path, formula_path.with_suffix(".xcnf.gz"),
        control_path, control_path.with_suffix(".xcnf.gz"),
        stdout_path, stderr_path, control_stdout, control_stderr))
    runtime_path = HERE / "group_add_sage_runtime_info.json"
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    baseline_path, baseline, archive_path, base, keys = read_inputs(n, kind)
    onb = field.Onb(n)
    curve = curves.Curve(onb)
    public = tuple(map(int, baseline["public_subgroup_target"]))
    order = int(base["curve"]["subgroup_order"])
    assert curve.onCurve(public) and curve.mul(public, order) is None
    binary = Path(shutil.which("cryptominisat5"))

    started = time.perf_counter()
    if n == 53:
        formula, choices, leaves, mids, slopes = (
            build_exact_base_group_chain(n, keys, public))
        raw_leaves = None
    else:
        formula, raw_leaves, leaves, mids, slopes = (
            build_projected_sparse_group_chain(n, 4, public))
        choices = None
    assert len(mids) == 2 and len(slopes) == 3
    build_seconds = time.perf_counter() - started
    formula_stats = stats(formula)
    formula.write(formula_path)
    formula_bytes = formula_path.stat().st_size
    remaining = args.max_seconds - (time.perf_counter() - started)
    if remaining > 0:
        result = solve(formula_path, binary, remaining, args.max_conflicts)
    else:
        result = {"command": None, "status": "no_solver_budget",
                  "return_code": None, "wall_seconds": 0.0,
                  "conflicts_reported": None, "stdout": "", "stderr": "",
                  "model": None}
    charged_seconds = time.perf_counter() - started
    peak_child_rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    stdout_path.write_text(result["stdout"])
    stderr_path.write_text(result["stderr"])
    relation = (verify_model(n, raw_leaves, choices, leaves,
                             result["model"], onb, curve, order, keys,
                             public) if result["model"] is not None else None)
    formula_archive, formula_bytes_checked, formula_sha = archive(formula_path)
    assert formula_bytes_checked == formula_bytes

    witness_path, points = witness_points(
        n, kind, onb, curve, baseline, int(base["curve"]["cofactor"]))
    control = None
    if points is not None:
        pin_known_witness(formula, raw_leaves, leaves, baseline, points, onb)
        formula.write(control_path)
        locked = solve(control_path, binary, 60, args.max_conflicts)
        control_stdout.write_text(locked["stdout"])
        control_stderr.write_text(locked["stderr"])
        locked_relation = (verify_model(
            n, raw_leaves, choices, leaves, locked["model"], onb, curve,
            order, keys, public) if locked["model"] is not None else None)
        assert locked["status"] == "sat" and locked_relation is not None
        assert locked_relation["leaf_points"] == [
            [int(x), int(y)] for x, y in points]
        locked_archive, locked_bytes, locked_sha = archive(control_path)
        control = {
            "status": "known_witness_sat_verified",
            "solver_wall_seconds": locked["wall_seconds"],
            "solver_conflicts_reported": locked["conflicts_reported"],
            "xcnf_archive": locked_archive.name,
            "xcnf_sha256": locked_sha,
            "xcnf_bytes": locked_bytes,
            "solver_stdout_sha256": sha(control_stdout),
            "solver_stderr_sha256": sha(control_stderr),
            "witness_receipt_sha256": sha(witness_path),
            "verified_relation": locked_relation,
        }
    receipt = {
        "kind": "full_group_addition_four_point_stage_probe",
        "proposal_id": "Q1320" if n == 53 else "Q1321",
        "candidate_id": None, "run_id": None,
        "workload_id": baseline["workload_id"],
        "curve_id": baseline["curve_id"], "isogeny": "none",
        "n": n, "workload_kind": kind,
        "public_target": list(baseline["public_subgroup_target"]),
        "factor_base_policy": "exact archived signed-Frobenius subgroup base",
        "factor_base_actual_B": baseline["factor_base_actual_B"],
        "factor_base_folded_columns": baseline["factor_base_folded_columns"],
        "factor_base_enumerated_set_sha256": baseline[
            "factor_base_enumerated_set_sha256"],
        "base_archive_sha256": sha(archive_path),
        "leaf_encoding": ("canonical orbit-key and Frobenius shift"
                          if n == 53 else
                          "rational sparse raw x projected by cofactor four"),
        "chain": "three nondegenerate affine additions; exact leaf y and public x,y; deterministic Itoh-Tsujii inversion",
        "nondegenerate_restriction": "each intermediate affine-addition denominator x1+x2 must be nonzero",
        "formula_build_seconds": build_seconds,
        "target_pdp_wall_seconds": charged_seconds,
        "solver_wall_seconds": result["wall_seconds"],
        "formula": formula_stats,
        "xcnf_archive": formula_archive.name,
        "xcnf_sha256": formula_sha, "xcnf_bytes": formula_bytes,
        "status": result["status"], "return_code": result["return_code"],
        "solver_conflicts_reported": result["conflicts_reported"],
        "verified_relation": relation,
        "observed_verified_relation_count": int(relation is not None),
        "natural_relation_yield_estimate": None,
        "field_operations": None,
        "complete_solve_work_log2": None,
        "control": control,
        "peak_child_rss_raw_before_control": peak_child_rss,
        "peak_child_rss_units": "bytes on Darwin, KiB on Linux",
        "max_seconds": args.max_seconds,
        "max_conflicts": args.max_conflicts,
        "solver_command": result["command"],
        "solver_binary_sha256": sha(binary),
        "solver_stdout_sha256": sha(stdout_path),
        "solver_stderr_sha256": sha(stderr_path),
        "baseline_receipt_sha256": sha(baseline_path),
        "protocol_sha256": sha(HERE / "protocol.json"),
        "runtime_info_sha256": sha(runtime_path),
        "core_source_sha256": sha(HERE / "chain_s3.py"),
        "group_add_source_sha256": sha(HERE / "chain_group_add.py"),
        "projected_source_sha256": (sha(HERE / "chain_s3_projected_sparse.py")
                                    if n == 83 else None),
        "base_orbit_source_sha256": sha(HERE / "chain_s3_base_orbit.py"),
        "base_probe_source_sha256": sha(HERE / "run_base_orbit_probe.py"),
        "probe_source_sha256": sha(HERE / "run_probe.py"),
        "runner_source_sha256": sha(Path(__file__)),
    }
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"proposal_id": receipt["proposal_id"], "n": n,
                      "kind": kind, "status": result["status"],
                      "verified_relation": relation is not None,
                      "formula": formula_stats,
                      "solver_conflicts": result["conflicts_reported"],
                      "target_pdp_wall_seconds": charged_seconds,
                      "known_witness_control": (control["status"] if control
                                                else None)}))


if __name__ == "__main__":
    main()
