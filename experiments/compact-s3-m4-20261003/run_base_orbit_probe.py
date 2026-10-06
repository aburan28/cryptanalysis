#!/usr/bin/env python3
"""Bounded S3 search over the exact folded subgroup factor base."""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import itertools
import json
import re
import resource
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from chain_s3_base_orbit import build_base_orbit_chain, decode_base_choice
from run_probe import HERE, curves, field, lift, parse_model, sha


def read_inputs(n, kind):
    baseline_path = HERE / "runs" / f"n{n}_{kind}_frozen.json"
    baseline = json.loads(baseline_path.read_text())
    archive_path = HERE / "bases" / f"n{n}_weight{3 if n == 53 else 4}_orbits.json.gz"
    with gzip.open(archive_path, "rt") as source:
        archive = json.load(source)
    assert baseline["curve_id"] == archive["curve"]["curve_id"]
    assert baseline["factor_base_archive_sha256"] == sha(archive_path)
    assert baseline["factor_base_enumerated_set_sha256"] == archive[
        "factor_base"]["enumerated_set_sha256"]
    assert baseline["protocol_sha256"] == sha(HERE / "protocol.json")
    packed = base64.b64decode(archive["factor_base"][
        "packed_canonical_x_keys_base64"], validate=True)
    assert hashlib.sha256(packed).hexdigest() == baseline[
        "factor_base_enumerated_set_sha256"]
    width = (n + 7) // 8
    keys = [int.from_bytes(packed[i:i + width], "little")
            for i in range(0, len(packed), width)]
    assert keys == sorted(set(keys))
    assert len(keys) == baseline["factor_base_folded_columns"]
    assert 2 * sum(archive["factor_base"]["orbit_lengths"]) == baseline[
        "factor_base_actual_B"]
    return baseline_path, baseline, archive_path, archive, keys


def point_choice(onb, keys, key_index, point):
    x = onb.toCoords(point[0])
    root = onb.fromCoords(x)
    orbit = [onb.toCoords(onb.frob(root, shift))
             for shift in range(onb.m)]
    canonical = min(orbit)
    index = key_index[canonical]
    canonical_field = onb.fromCoords(keys[index])
    shift = next(shift for shift in range(onb.m)
                 if onb.toCoords(onb.frob(canonical_field, shift)) == x)
    return index, shift


def witness_points(n, kind, onb, curve, baseline, cofactor):
    public = tuple(map(int, baseline["public_subgroup_target"]))
    if kind == "ordinary" and n == 53:
        witness_path = HERE / "runs/n53_ordinary_matched_pair_table.json"
        witness = json.loads(witness_path.read_text())
        assert witness["verified_relation_count"] == 1
        assert witness["target"] == list(baseline["public_subgroup_target"])
        points = [tuple(map(int, row)) for row in witness[
            "ordinary_query"]["relation"]["points"]]
    elif kind == "planted":
        witness_path = HERE / "runs" / f"n{n}_planted_frozen.json"
        raw = tuple(map(int, baseline["raw_target"]))
        unsigned = [curve.pointFromX(onb.fromCoords(x))
                    for x in baseline["fixture"]["planted_leaf_x"]]
        assert all(point is not None for point in unsigned)
        chosen = None
        for signs in itertools.product((1, -1), repeat=4):
            trial = [point if sign == 1 else curve.neg(point)
                     for point, sign in zip(unsigned, signs)]
            total = None
            for point in trial:
                total = curve.add(total, point)
            if total == raw:
                chosen = trial
                break
        assert chosen is not None
        points = [curve.mul(point, cofactor) for point in chosen]
        assert all(point is not None for point in points)
    else:
        return None, None
    total = None
    for point in points:
        total = curve.add(total, point)
    assert total == public
    return witness_path, points


def lock_control(formula, leaves, mids, choices, keys, onb, curve,
                 public, witness_path, points):
    assert points is not None and witness_path is not None
    key_index = {key: i for i, key in enumerate(keys)}
    chosen = [(point_choice(onb, keys, key_index, point), point)
              for point in points]
    chosen.sort(key=lambda pair: pair[0])
    selected_choices = [choice for choice, _ in chosen]
    selected_points = [point for _, point in chosen]
    first = curve.add(selected_points[0], selected_points[1])
    second = curve.add(first, selected_points[2])
    assert first is not None and second is not None
    assert curve.add(second, selected_points[3]) == public
    with tempfile.TemporaryDirectory() as directory:
        for choice, (index, shift) in zip(choices, selected_choices):
            for variables, value in zip(choice, (index, shift)):
                formula.clauses.extend(([
                    bit if value >> position & 1 else -bit]
                    for position, bit in enumerate(variables)))
        for variables, point in zip(mids, (first, second)):
            value = onb.toCoords(point[0])
            formula.clauses.extend(([
                bit if value >> position & 1 else -bit]
                for position, bit in enumerate(variables)))
        path = Path(directory) / "locked.xcnf"
        formula.write(path)
        start = time.perf_counter()
        result = subprocess.run(["cryptominisat5", "--verb", "0",
                                 "--threads", "1", str(path)],
                                capture_output=True, text=True, timeout=60)
        wall = time.perf_counter() - start
        assert result.returncode == 10, result.stdout[-1000:]
        model = parse_model(result.stdout)
        assert model is not None
        assert [decode_base_choice(choice, model) for choice in choices] == (
            selected_choices)
        leaf_xs, relation, status = lift(
            onb, curve, leaves, model, public, public, 1)
        assert status == "verified_four_point_relation"
        assert leaf_xs == [onb.toCoords(point[0]) for point in selected_points]
        assert relation is not None
        return {
            "status": "locked_sat_verified_public_relation",
            "selected_orbit_choices": selected_choices,
            "leaf_x_coordinates": leaf_xs,
            "solver_wall_seconds": wall,
            "locked_formula_sha256": sha(path),
            "witness_receipt_sha256": sha(witness_path),
            "relation": relation,
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, choices=(53, 83), required=True)
    parser.add_argument("--kind", choices=("ordinary", "planted"),
                        required=True)
    parser.add_argument("--max-seconds", type=int, default=120)
    parser.add_argument("--max-conflicts", type=int, default=1_000_000)
    args = parser.parse_args()
    n, kind = args.n, args.kind
    stem = f"n{n}_{kind}_exact_base_orbit"
    output = HERE / "runs" / f"{stem}.json"
    formula_path = HERE / "runs" / f"{stem}.xcnf"
    archive_formula = HERE / "runs" / f"{stem}.xcnf.gz"
    stdout_path = HERE / "runs" / f"{stem}.stdout.txt"
    stderr_path = HERE / "runs" / f"{stem}.stderr.txt"
    assert not any(path.exists() for path in (
        output, formula_path, archive_formula, stdout_path, stderr_path))
    runtime_path = HERE / "base_orbit_sage_runtime_info.json"
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    setup_started = time.perf_counter()
    baseline_path, baseline, archive_path, archive, keys = read_inputs(n, kind)
    onb = field.Onb(n)
    curve = curves.Curve(onb)
    public = tuple(map(int, baseline["public_subgroup_target"]))
    order = int(archive["curve"]["subgroup_order"])
    assert curve.onCurve(public) and curve.mul(public, order) is None
    setup_seconds = time.perf_counter() - setup_started

    started = time.perf_counter()
    target_x = onb.toCoords(public[0])
    formula, leaves, mids, choices = build_base_orbit_chain(
        n, keys, target_x, ordered_leaves=True)
    build_seconds = time.perf_counter() - started
    formula_stats = {"variables": formula.variables,
                     "cnf_clauses": len(formula.clauses),
                     "xor_rows": len(formula.xors),
                     "and_gates": len(formula.and_cache)}
    formula.write(formula_path)
    formula_sha = sha(formula_path)
    formula_bytes = formula_path.stat().st_size
    remaining = args.max_seconds - (time.perf_counter() - started)
    solver_binary = Path(shutil.which("cryptominisat5"))
    command = [str(solver_binary), "--verb", "1", "--threads", "1",
               "--maxtime", str(max(1, int(remaining))), "--maxconfl",
               str(args.max_conflicts), str(formula_path)]
    if remaining <= 0:
        stdout, stderr, code, status = "", "", None, "no_solver_budget"
        solver_seconds = 0.0
    else:
        solver_started = time.perf_counter()
        try:
            result = subprocess.run(command, capture_output=True, text=True,
                                    timeout=remaining)
            stdout, stderr, code = (result.stdout, result.stderr,
                                    result.returncode)
            status = ("sat" if code == 10 else "unsat" if code == 20
                      else "censored")
        except subprocess.TimeoutExpired as error:
            stdout = (error.stdout or b"").decode(errors="replace")
            stderr = (error.stderr or b"").decode(errors="replace")
            code, status = None, "external_timeout"
        solver_seconds = time.perf_counter() - solver_started
    charged_seconds = time.perf_counter() - started
    stdout_path.write_text(stdout)
    stderr_path.write_text(stderr)
    conflicts = re.findall(r"conflicts\s*[:=]\s*([0-9]+)", stdout,
                           flags=re.IGNORECASE)
    model = parse_model(stdout)
    relation = None
    lift_status = None
    chosen = None
    if model is not None:
        chosen = [decode_base_choice(choice, model) for choice in choices]
        assert all(index < len(keys) and shift < n
                   for index, shift in chosen)
        assert chosen == sorted(chosen)
        leaf_xs, relation, lift_status = lift(
            onb, curve, leaves, model, public, public, 1)
        for x, (index, shift) in zip(leaf_xs, chosen):
            expected = onb.toCoords(onb.frob(
                onb.fromCoords(keys[index]), shift))
            assert x == expected
            point = curve.pointFromX(onb.fromCoords(x))
            assert point is not None and curve.mul(point, order) is None
    peak_child_rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    witness_path, points = witness_points(
        n, kind, onb, curve, baseline, int(archive["curve"]["cofactor"]))
    control = (lock_control(formula, leaves, mids, choices, keys, onb, curve,
                            public, witness_path, points) if points is not None
               else None)
    with archive_formula.open("wb") as stream:
        with gzip.GzipFile(filename="", mode="wb", fileobj=stream,
                           mtime=0, compresslevel=9) as zipped:
            zipped.write(formula_path.read_bytes())
    assert hashlib.sha256(gzip.decompress(
        archive_formula.read_bytes())).hexdigest() == formula_sha
    receipt = {
        "kind": "exact_subgroup_base_orbit_s3_stage_probe",
        "proposal_id": {53: "Q1315", 83: "Q1316"}[n],
        "candidate_id": None, "run_id": None,
        "workload_id": baseline["workload_id"],
        "curve_id": baseline["curve_id"], "isogeny": "none",
        "n": n, "workload_kind": kind,
        "public_target": list(baseline["public_subgroup_target"]),
        "target_x_coordinates": target_x,
        "base_archive_sha256": sha(archive_path),
        "factor_base_enumerated_set_sha256": baseline[
            "factor_base_enumerated_set_sha256"],
        "factor_base_actual_B": baseline["factor_base_actual_B"],
        "factor_base_folded_columns": len(keys),
        "leaf_policy": "four sorted choices of exact subgroup x-orbit key and Frobenius shift; signs checked by group replay",
        "target_policy": "one exact public subgroup point; no raw cofactor-preimage selector",
        "target_independent_base_load_seconds": setup_seconds,
        "formula_build_seconds": build_seconds,
        "target_pdp_wall_seconds": charged_seconds,
        "solver_wall_seconds": solver_seconds,
        "formula": formula_stats,
        "xcnf_sha256": formula_sha,
        "xcnf_bytes": formula_bytes,
        "status": status, "return_code": code,
        "solver_conflicts_reported": (int(conflicts[-1]) if conflicts else None),
        "chosen_orbit_choices": chosen,
        "lift_status": lift_status,
        "verified_relation": relation,
        "observed_verified_relation_count": int(relation is not None),
        "natural_relation_yield_estimate": None,
        "field_operations": None,
        "complete_solve_work_log2": None,
        "locked_control": control,
        "peak_child_rss_raw_before_control": peak_child_rss,
        "peak_child_rss_units": "bytes on Darwin, KiB on Linux",
        "max_seconds": args.max_seconds,
        "max_conflicts": args.max_conflicts,
        "solver_command": command,
        "solver_binary_sha256": sha(solver_binary),
        "solver_stdout_sha256": sha(stdout_path),
        "solver_stderr_sha256": sha(stderr_path),
        "baseline_receipt_sha256": sha(baseline_path),
        "protocol_sha256": sha(HERE / "protocol.json"),
        "runtime_info_sha256": sha(runtime_path),
        "core_source_sha256": sha(HERE / "chain_s3.py"),
        "factored_source_sha256": sha(HERE / "chain_s3_factored.py"),
        "orbit_source_sha256": sha(HERE / "chain_s3_orbit.py"),
        "ordered_source_sha256": sha(HERE / "chain_s3_ordered.py"),
        "base_orbit_source_sha256": sha(HERE / "chain_s3_base_orbit.py"),
        "runner_source_sha256": sha(Path(__file__)),
    }
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"n": n, "kind": kind, "status": status,
                      "verified_relation": relation is not None,
                      "formula": formula_stats,
                      "solver_conflicts": receipt["solver_conflicts_reported"],
                      "target_pdp_wall_seconds": charged_seconds,
                      "locked_control": (control["status"] if control else None)}))


if __name__ == "__main__":
    main()
