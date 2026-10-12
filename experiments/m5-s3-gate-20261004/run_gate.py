#!/usr/bin/env python3
"""Frozen, bounded five-summand S3 PDP gate on exact N53/N83 bases.

This records a point-decomposition stage, not an index-calculus candidate or
a recovered discrete logarithm. All ordinary targets are supplied as public
points from the archived single-target workloads.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import random
import re
import resource
import shutil
import subprocess
import sys
import time
from pathlib import Path

import psutil

from build_m5 import (ROOT, build_formula, canonical_projected_x,
                      pin_bits, replay_model)

S3 = ROOT / "experiments/compact-s3-m4-20261003"
sys.path.insert(0, str(S3))
from cofactor_preimages import kernel_of_cofactor  # noqa: E402
from run_group_add_probe import archive, stats  # noqa: E402
from run_probe import (base_record, curve_record, curves, field,
                       parse_model, sha)  # noqa: E402


HERE = Path(__file__).resolve().parent
PROTOCOL = HERE / "protocol.json"


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_base(n: int, weight: int):
    manifest_path, candidate = curve_record(n)
    base_path, fb = base_record(n, weight, candidate)
    with gzip.open(base_path, "rt") as stream:
        base = json.load(stream)
    packed = base64.b64decode(fb["packed_canonical_x_keys_base64"],
                              validate=True)
    width = (n + 7) // 8
    assert len(packed) == width * fb["signed_frobenius_columns"]
    assert sha_bytes(packed) == fb["enumerated_set_sha256"]
    keys = [int.from_bytes(packed[i:i + width], "little")
            for i in range(0, len(packed), width)]
    assert keys == sorted(set(keys))
    assert base["curve"] == candidate["curve"]
    return manifest_path, candidate, base_path, fb, set(keys)


def planted_fixture(onb, curve, cofactor: int, weight: int,
                    base_keys: set[int], seed: int):
    rng = random.Random(seed)
    points = []
    raw_xs = []
    columns = set()
    for _ in range(10000):
        if len(points) == 5:
            break
        mask = sum(1 << bit for bit in rng.sample(range(onb.m), weight))
        if mask in raw_xs:
            continue
        point = curve.pointFromX(onb.fromCoords(mask))
        if point is None:
            continue
        projected = curve.mul(point, cofactor)
        if projected is None:
            continue
        key = canonical_projected_x(onb, projected, onb.m)
        if key not in base_keys or key in columns:
            continue
        points.append(point)
        raw_xs.append(mask)
        columns.add(key)
    assert len(points) == 5 and len(columns) == 5
    partials = []
    total = points[0]
    for point in points[1:]:
        total = curve.add(total, point)
        if total is None:
            raise AssertionError("frozen planted fixture has an identity prefix")
        partials.append(total)
    public = curve.mul(total, cofactor)
    assert public is not None
    return {
        "raw_leaf_x": raw_xs,
        "raw_leaf_points": [[str(v) for v in point] for point in points],
        "raw_intermediate_x": [onb.toCoords(p[0]) for p in partials[:3]],
        "raw_sum": [str(v) for v in total],
        "public_target": [str(v) for v in public],
        "projected_column_keys": sorted(columns),
    }


def raw_preimage_coset(onb, curve, order: int, cofactor: int,
                      public, kernel):
    base = curve.mul(public, pow(cofactor, -1, order))
    assert base is not None and curve.mul(base, cofactor) == public
    points = {curve.add(base, torsion) for torsion in kernel}
    assert len(points) == cofactor and None not in points
    assert all(curve.mul(point, cofactor) == public for point in points)
    ordered = sorted(points, key=lambda point: (
        onb.toCoords(point[0]), onb.toCoords(point[1])))
    xs = [onb.toCoords(point[0]) for point in ordered]
    assert len(set(xs)) == cofactor
    return ordered, xs


def solve_limited(path: Path, binary: Path, seconds: float,
                  max_conflicts: int, rss_cap_bytes: int) -> dict:
    """Run one attempt with external time and sampled child-RSS guards.

    macOS rejects the attempted RLIMIT_AS/DATA cap on this host. Sampling
    every 50 ms can overshoot the threshold, so the receipt reports the
    observed peak and never calls it a hard memory limit.
    """
    command = [str(binary), "--verb", "1", "--threads", "1",
               "--maxconfl", str(max_conflicts), str(path)]
    started = time.perf_counter_ns()
    deadline = started + int(max(0.01, seconds) * 1e9)
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    monitor = psutil.Process(process.pid)
    observed_peak_rss = 0
    status = None
    while True:
        try:
            observed_peak_rss = max(
                observed_peak_rss, monitor.memory_info().rss)
        except psutil.NoSuchProcess:
            pass
        if observed_peak_rss > rss_cap_bytes:
            process.kill()
            stdout, stderr = process.communicate()
            code, status = process.returncode, "sampled_rss_cap_exceeded"
            break
        remaining = (deadline - time.perf_counter_ns()) / 1e9
        if remaining <= 0:
            process.kill()
            stdout, stderr = process.communicate()
            code, status = process.returncode, "external_timeout"
            break
        try:
            stdout, stderr = process.communicate(timeout=min(0.05, remaining))
            code = process.returncode
            status = ("sat" if code == 10 else "unsat" if code == 20 else
                      "solver_failure" if code not in (0, 10, 20) else
                      "censored")
            break
        except subprocess.TimeoutExpired:
            continue
    matches = re.findall(r"conflicts\s*[:=]\s*([0-9]+)", stdout,
                         flags=re.IGNORECASE)
    return {
        "command": command,
        "status": status,
        "return_code": code,
        "wall_seconds": (time.perf_counter_ns() - started) / 1e9,
        "conflicts_reported": int(matches[-1]) if matches else None,
        "stdout": stdout,
        "stderr": stderr,
        "model": parse_model(stdout),
        "observed_peak_solver_rss_bytes": observed_peak_rss,
        "rss_sample_interval_ms": 50,
    }


def run(n: int, mode: str, output_dir: Path):
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["proposal_id"] == "Q1417"
    assert protocol["candidate_id"] is None and protocol["isogeny"] == "none"
    for name, digest in protocol["source_sha256"].items():
        assert sha(ROOT / name) == digest, name
    runtime_path = HERE / "sage_runtime_info.json"
    assert sha(runtime_path) == protocol["sage_runtime_info_sha256"]
    profile = protocol["profiles"][str(n)]
    weight = profile["normal_basis_weight_bound"]
    manifest_path, candidate, base_path, fb, base_keys = load_base(n, weight)
    assert candidate["curve"]["curve_id"] == profile["curve_id"]
    assert sha(manifest_path) == profile["curve_manifest_sha256"]
    assert sha(base_path) == profile["base_archive_sha256"]
    assert fb["actual_usable_points_B_before_folding"] == profile["actual_B"]
    assert fb["signed_frobenius_columns"] == profile["folded_columns_K"]
    assert fb["enumerated_set_sha256"] == profile["base_digest"]
    ordinary_path = S3 / "runs" / f"n{n}_ordinary_frozen.json"
    preimage_path = S3 / "runs" / f"n{n}_ordinary_raw_preimages.json"
    ordinary = json.loads(ordinary_path.read_text())
    archived_preimages = json.loads(preimage_path.read_text())
    assert sha(ordinary_path) == profile["ordinary_receipt_sha256"]
    assert sha(preimage_path) == profile["ordinary_preimages_sha256"]
    assert ordinary["curve_id"] == profile["curve_id"]
    assert ordinary["workload_id"] == profile["ordinary_workload_id"]
    assert archived_preimages["public_target"] == ordinary[
        "public_subgroup_target"]
    onb = field.Onb(n)
    curve = curves.Curve(onb)
    order = int(candidate["curve"]["subgroup_order"])
    cofactor = int(candidate["curve"]["cofactor"])
    assert cofactor == profile["cofactor"]
    assert fb["cofactor_projection"] == cofactor
    binary = Path(shutil.which("cryptominisat5") or "")
    assert binary.is_file() and sha(binary) == protocol["solver"]["binary_sha256"]
    assert str(binary) == protocol["solver"]["binary_path"]
    assert protocol["solver"]["rss_monitor_library"] == (
        f"psutil {psutil.__version__}")

    setup_started = time.perf_counter_ns()
    kernel, generators, kernel_trials = kernel_of_cofactor(
        curve, onb, order, cofactor, profile["kernel_seed"])
    setup_ns = time.perf_counter_ns() - setup_started
    assert len(kernel) == cofactor
    fixture = None
    if mode == "ordinary":
        public = tuple(map(int, ordinary["public_subgroup_target"]))
    else:
        fixture = planted_fixture(onb, curve, cofactor, weight, base_keys,
                                  profile["planted_seed"])
        public = tuple(map(int, fixture["public_target"]))
    assert curve.onCurve(public) and curve.mul(public, order) is None

    limits = protocol["limits"]
    assert limits["solver_rss_sample_interval_ms"] == 50
    cap_seconds = limits["external_wall_seconds"][mode]
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"n{n}_{mode}"
    receipt_path = output_dir / f"{stem}.json"
    assert not receipt_path.exists(), "refusing to overwrite a frozen run"
    target_started = time.perf_counter_ns()
    preimage_started = time.perf_counter_ns()
    raw_targets, target_xs = raw_preimage_coset(
        onb, curve, order, cofactor, public, kernel)
    preimage_ns = time.perf_counter_ns() - preimage_started
    if mode == "ordinary":
        assert target_xs == archived_preimages["raw_target_x_coordinates"]
        assert [[str(v) for v in point] for point in raw_targets] == (
            archived_preimages["raw_target_points"])
    else:
        assert tuple(map(int, fixture["raw_sum"])) in raw_targets
    formula_started = time.perf_counter_ns()
    formula, leaves, intermediates, selector = build_formula(
        n, weight, target_xs)
    if mode == "planted_locked":
        for bits, value in zip(leaves, fixture["raw_leaf_x"]):
            pin_bits(formula, bits, value)
        for bits, value in zip(intermediates,
                               fixture["raw_intermediate_x"]):
            pin_bits(formula, bits, value)
        pin_bits(formula, selector, raw_targets.index(
            tuple(map(int, fixture["raw_sum"]))))
    formula_ns = time.perf_counter_ns() - formula_started
    formula_shape = stats(formula)
    attempts = []
    relation = None
    deadline = target_started + int(cap_seconds * 1e9)
    for index in range(limits["max_models"]):
        remaining = (deadline - time.perf_counter_ns()) / 1e9
        if remaining <= 0:
            break
        formula_path = output_dir / f"{stem}.attempt{index}.xcnf"
        assert not formula_path.exists() and not Path(
            str(formula_path) + ".gz").exists()
        write_started = time.perf_counter_ns()
        formula.write(formula_path)
        write_ns = time.perf_counter_ns() - write_started
        remaining = (deadline - time.perf_counter_ns()) / 1e9
        if remaining <= 0:
            result = {"command": None, "status": "no_solver_budget",
                      "return_code": None, "wall_seconds": 0.0,
                      "conflicts_reported": None, "stdout": "", "stderr": "",
                      "model": None}
        else:
            result = solve_limited(
                formula_path, binary, remaining, limits["max_conflicts"],
                limits["solver_sampled_rss_stop_bytes"])
        check_started = time.perf_counter_ns()
        replay = None
        if result["model"] is not None:
            replay = replay_model(
                onb, curve, order, cofactor, weight, base_keys, public,
                raw_targets, leaves, selector, result["model"])
            if replay["status"] == "verified_five_point_relation":
                relation = replay
            elif index + 1 < limits["max_models"]:
                block = [-bit if result["model"].get(bit, False) else bit
                         for row in leaves for bit in row]
                block += [-bit if result["model"].get(bit, False) else bit
                          for bit in selector]
                formula.clauses.append(block)
        check_ns = time.perf_counter_ns() - check_started
        attempts.append({
            "index": index,
            "status": result["status"],
            "return_code": result["return_code"],
            "solver_command": result["command"],
            "solver_wall_seconds": result["wall_seconds"],
            "solver_conflicts_reported": result["conflicts_reported"],
            "observed_peak_solver_rss_bytes": result.get(
                "observed_peak_solver_rss_bytes"),
            "rss_sample_interval_ms": result.get("rss_sample_interval_ms"),
            "formula_write_ns": write_ns,
            "relation_check_ns": check_ns,
            "formula_path": formula_path,
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "replay": replay,
        })
        if relation is not None or result["model"] is None:
            break
    online_ns = time.perf_counter_ns() - target_started

    # Receipt serialization and formula compression are instrument-only.
    # They occur after the target-dependent search interval above.
    archived_attempts = []
    for attempt in attempts:
        index = attempt["index"]
        stdout_path = output_dir / f"{stem}.attempt{index}.stdout.txt"
        stderr_path = output_dir / f"{stem}.attempt{index}.stderr.txt"
        stdout_path.write_text(attempt["stdout"])
        stderr_path.write_text(attempt["stderr"])
        compressed, raw_bytes, raw_sha = archive(attempt["formula_path"])
        archived_attempts.append({
            key: value for key, value in attempt.items()
            if key not in ("formula_path", "stdout", "stderr")
        } | {
            "xcnf_gzip": compressed.name,
            "xcnf_gzip_sha256": sha(compressed),
            "xcnf_raw_bytes": raw_bytes,
            "xcnf_raw_sha256": raw_sha,
            "stdout_file": stdout_path.name,
            "stdout_sha256": sha(stdout_path),
            "stderr_file": stderr_path.name,
            "stderr_sha256": sha(stderr_path),
        })
    phases_ns = {
        "target_preimages": preimage_ns,
        "formula_build": formula_ns,
        "formula_write": sum(a["formula_write_ns"] for a in attempts),
        "solver": sum(int(a["solver_wall_seconds"] * 1e9)
                      for a in attempts),
        "relation_check": sum(a["relation_check_ns"] for a in attempts),
    }
    phases_ns["target_dependent_overhead"] = max(
        0, online_ns - sum(phases_ns.values()))
    receipt = {
        "kind": "bounded_five_summand_s3_pdp_stage",
        "proposal_id": "Q1417",
        "candidate_id": None,
        "run_id": None,
        "isogeny": "none",
        "curve_id": profile["curve_id"],
        "workload_id": profile["ordinary_workload_id"] if mode == "ordinary" else None,
        "mode": mode,
        "field_degree_n": n,
        "summands_m": 5,
        "normal_basis_weight_bound": weight,
        "actual_usable_points_B": profile["actual_B"],
        "folded_columns_K": profile["folded_columns_K"],
        "factor_base_digest": profile["base_digest"],
        "cofactor": cofactor,
        "target_count": 1,
        "public_target": [str(v) for v in public],
        "target_generation": "archived_public_point" if mode == "ordinary"
                             else "deterministic_planted_fixture_outside_interval",
        "planted_fixture": fixture,
        "raw_target_preimage_count": len(raw_targets),
        "raw_target_x_sha256": sha_bytes(b"".join(
            value.to_bytes((n + 7) // 8, "little") for value in target_xs)),
        "target_preimage_kernel_size": len(kernel),
        "target_preimage_kernel_generators": [
            [str(v) for v in point] for point in generators],
        "target_preimage_kernel_trials": kernel_trials,
        "target_independent_kernel_setup_ns": setup_ns,
        "formula_shape": formula_shape,
        "limits": limits,
        "attempts": archived_attempts,
        "verified_relation": relation,
        "observed_verified_relation_count": int(relation is not None),
        "online_pdp_interval": "first target-preimage computation through verified relation or final capped attempt; excludes process launch, base loading, kernel setup, fixture construction, and post-interval artifact compression",
        "online_pdp_wall_ns_exploratory": online_ns,
        "online_pdp_phase_ns": phases_ns,
        "peak_rss_raw": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "peak_rss_units": "bytes on Darwin, KiB on Linux",
        "solver_rss_cap_type": "sampled child RSS with 50 ms polling; overshoot possible",
        "verified_single_target_dlp": False,
        "complete_solve_work_log2": None,
        "is_natural_relation_yield_measurement": mode == "ordinary",
        "is_controlled_cpu_speedup": False,
        "protocol_sha256": sha(PROTOCOL),
        "sage_runtime_info_sha256": sha(runtime_path),
        "source_sha256": {name: sha(ROOT / name)
                          for name in protocol["source_sha256"]},
        "solver_binary_sha256": sha(binary),
        "base_archive_sha256": sha(base_path),
        "ordinary_target_receipt_sha256": sha(ordinary_path),
        "ordinary_preimages_receipt_sha256": sha(preimage_path),
    }
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "receipt": str(receipt_path),
        "mode": mode,
        "n": n,
        "attempt_statuses": [a["status"] for a in archived_attempts],
        "verified_relations": receipt["observed_verified_relation_count"],
        "online_pdp_seconds_exploratory": online_ns / 1e9,
    }))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, choices=(53, 83), required=True)
    parser.add_argument("--mode", choices=("planted_locked",
                                           "planted_unpinned", "ordinary"),
                        required=True)
    parser.add_argument("--output-dir", type=Path, default=HERE / "runs")
    args = parser.parse_args()
    run(args.n, args.mode, args.output_dir)


if __name__ == "__main__":
    main()
