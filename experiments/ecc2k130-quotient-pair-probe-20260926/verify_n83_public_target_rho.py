#!/usr/bin/env python3
"""Independently replay a rho scalar for the frozen n83 public target."""

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

import curves
import field

HERE = Path(__file__).resolve().parent
CURVE_ID = "EC1N83Ckb1h876c2921cb64"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_driver_public_points(path, onb, g, q):
    """Check C++ ONB limbs against the exact public points in the curve record."""
    source = path.read_text()
    expected = {"px": onb.toCoords(g[0]), "py": onb.toCoords(g[1]),
                "qx": onb.toCoords(q[0]), "qy": onb.toCoords(q[1])}
    for name, value in expected.items():
        matches = re.findall(
            rf"static const unsigned long long {name}\[3\]\s*=\s*\{{([^}}]+)\}};",
            source, re.MULTILINE)
        if len(matches) != 1:
            raise SystemExit(f"cannot uniquely parse {name} in {path}")
        limbs = [int(item.strip().removesuffix("ull"), 0)
                 for item in matches[0].split(",") if item.strip()]
        if len(limbs) != 3 or sum(limb << (64 * i) for i, limb in
                                  enumerate(limbs)) != value:
            raise SystemExit(f"embedded {name} differs from the frozen public point: {path}")
    if "runCurve<CfgF83>(o, px, py, qx, qy" not in source:
        raise SystemExit(f"driver does not pass the verified points to n83: {path}")


SOLVED_RE = (r"^\s*solved after (\d+) iterations of (\d+) walks in "
             r"([0-9.]+) s \((\d+) distinguished points\)\s*$")
STOPPED_RE = (r"^stopping: (\d+) iterations of (\d+) walks, "
              r"(\d+) points reported\s*$")
BACKEND_RE = (r"^backend cpu: (\d+) threads x (\d+) slots x (\d+) lanes = "
              r"(\d+) walks, dp weight (\d+), (\d+) steps per launch\s*$")


def worker_result(log_path, binary, driver_source, run_id):
    log = log_path.read_text()
    solved = re.findall(SOLVED_RE, log, re.MULTILINE)
    stopped = re.findall(STOPPED_RE, log, re.MULTILINE)
    backend = re.findall(BACKEND_RE, log, re.MULTILINE)
    if len(solved) + len(stopped) != 1:
        raise SystemExit(f"worker log is not terminal: {log_path}")
    if len(backend) != 1:
        raise SystemExit(f"worker backend is not unique: {log_path}")
    threads, slots, lanes, backend_walks, dp_weight, steps = map(int, backend[0])
    if solved:
        iterations, walks, seconds, points = solved[0]
        status = "solved"
    else:
        iterations, walks, points = stopped[0]
        seconds = None
        status = "stopped"
    return {
        "run_id": run_id,
        "status": status,
        "iterations_per_walk": int(iterations),
        "walks": int(walks),
        "backend": {"threads": threads, "slots": slots, "lanes": lanes,
                    "walks": backend_walks, "dp_weight": dp_weight,
                    "steps_per_launch": steps},
        "walk_iterations": str(int(iterations) * int(walks)),
        "distinguished_points": int(points),
        "online_seconds_from_runner_if_solved": (
            float(seconds) if seconds is not None else None),
        "log_sha256": digest(log_path),
        "binary_sha256": digest(binary),
        "driver_source_sha256": digest(driver_source),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--driver-source", type=Path, required=True)
    parser.add_argument("--rho-source", type=Path, required=True)
    parser.add_argument("--worker-log", type=Path, action="append", default=[])
    parser.add_argument("--worker-binary", type=Path, action="append", default=[])
    parser.add_argument("--worker-driver-source", type=Path, action="append",
                        default=[])
    parser.add_argument("--worker-dp", type=Path, action="append", default=[])
    parser.add_argument("--worker-run-id", type=int, action="append", default=[])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    reference_path = HERE / "runs" / "n83_perf_prefix.json"
    reference = json.loads(reference_path.read_text())
    stopped_path = HERE / "runs" / "n83_public_target_rho_attempt.json"
    stopped = json.loads(stopped_path.read_text())
    assert reference["curve_id"] == CURVE_ID
    identity = reference["curve_identity_record"]
    canonical_identity = json.dumps(identity, sort_keys=True,
                                    separators=(",", ":")).encode()
    assert CURVE_ID.endswith("h" + hashlib.sha256(
        canonical_identity).hexdigest()[:12])
    g = tuple(reference["curve_identity_record"]["curve"]["generator"])
    q = tuple(reference["workload"]["target"])
    order = int(reference["subgroup_order"])
    assert stopped["curve_id"] == CURVE_ID
    assert tuple(stopped["public_target"]) == q
    onb = field.Onb(83)
    verify_driver_public_points(args.driver_source, onb, g, q)
    for worker_source in args.worker_driver_source:
        verify_driver_public_points(worker_source, onb, g, q)
    log = args.log.read_text()
    scalars = re.findall(r"^\s*k = (\d+)\s*$", log, re.MULTILINE)
    direct_finishes = re.findall(SOLVED_RE, log, re.MULTILINE)
    reloaded_collision = "collision found while reloading" in log
    if (len(scalars) != 1 or len(direct_finishes) > 1 or
            not (direct_finishes or reloaded_collision) or
            "verified [k]P == Q" not in log):
        raise SystemExit("rho log has no single completed, internally verified solve")
    k = int(scalars[0])
    if args.worker_log:
        if not (len(args.worker_log) == len(args.worker_binary) ==
                len(args.worker_driver_source) == len(args.worker_dp) ==
                len(args.worker_run_id)):
            raise SystemExit("each worker needs log, binary, driver source, DP corpus, and run ID")
        if len(set(args.worker_run_id)) != len(args.worker_run_id):
            raise SystemExit("worker run IDs must be distinct")
        worker_inputs = zip(args.worker_log, args.worker_binary,
                            args.worker_driver_source, args.worker_run_id)
    else:
        if not direct_finishes:
            raise SystemExit("a merged solve needs terminal worker logs")
        worker_inputs = [(args.log, args.binary, args.driver_source, None)]
    workers = [worker_result(*item) for item in worker_inputs]
    if args.worker_dp:
        for worker, dp in zip(workers, args.worker_dp):
            size = dp.stat().st_size
            if size % 32 or size // 32 < worker["distinguished_points"]:
                raise SystemExit(f"incomplete or inconsistent DP corpus: {dp}")
            worker["dp_records_total"] = size // 32
            worker["dp_corpus_sha256"] = digest(dp)
    assert all(worker["walks"] == worker["backend"]["walks"] for worker in workers)
    run_ids = [worker["run_id"] for worker in workers]
    first_backend = workers[0]["backend"]
    same_backend = all(worker["backend"] == first_backend for worker in workers)
    if same_backend:
        workload = {"curve_id": CURVE_ID, "target": list(q),
                    "target_count": 1, "walk": "signed-Frobenius rho CPU engine",
                    "worker_run_ids": run_ids,
                    "dp_weight": first_backend["dp_weight"],
                    "threads_per_worker": first_backend["threads"],
                    "steps_per_launch": first_backend["steps_per_launch"]}
    else:
        workload = {"curve_id": CURVE_ID, "target": list(q),
                    "target_count": 1, "walk": "signed-Frobenius rho CPU engine",
                    "worker_run_ids": run_ids,
                    "worker_backends": [worker["backend"] for worker in workers]}
    workload_id = hashlib.sha256(json.dumps(
        workload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:12]
    same_stopped_workload = workload == stopped["workload"]
    if same_stopped_workload:
        assert workload_id == stopped["workload_id"]
    if direct_finishes and digest(args.log) not in {
            worker["log_sha256"] for worker in workers}:
        raise SystemExit("direct solving worker is absent from worker logs")
    curve = curves.Curve(onb)
    assert curve.onCurve(g) and curve.onCurve(q)
    assert curve.mul(g, order) is None
    assert curve.mul(q, order) is None
    assert 0 < k < order
    assert curve.mul(g, k) == q
    total_walk_iterations = sum(int(worker["walk_iterations"])
                                for worker in workers)
    report = {
        "kind": "independent_n83_public_target_rho_replay",
        "curve_id": CURVE_ID,
        "curve_identity_record": reference["curve_identity_record"],
        "isogeny": "none",
        "workload_id": workload_id,
        "workload": workload,
        "worker_count": len(workers),
        "collision_policy": "distinguished points by recorded Hamming-weight threshold; signed-Frobenius canonical-x orbit key; merge same-target worker corpora; independently rewalk colliding seeds and solve their coefficient equation",
        "distinguished_point_corpus_bytes": (sum(
            worker["dp_records_total"] * 32 for worker in workers)
            if args.worker_dp else None),
        "distinguished_point_memory_peak_bytes": None,
        "rho_online_wall_ms": None,
        "subgroup_order": str(order),
        "public_generator": list(g),
        "public_target": list(q),
        "recovered_scalar": str(k),
        "independent_scalar_replay_passed": True,
        "driver_public_points_verified": True,
        "rho_online_seconds_from_runner_if_single_worker": (
            float(direct_finishes[0][2]) if len(workers) == 1 and
            direct_finishes else None),
        "rho_walk_iterations": str(total_walk_iterations),
        "rho_walk_iterations_log2": math.log2(total_walk_iterations),
        "rho_distinguished_points": sum(worker.get(
            "dp_records_total", worker["distinguished_points"])
                                         for worker in workers),
        "workers": workers,
        "work_boundary": "sum of all worker walk iterations including unsuccessful workers; excludes corpus hashing and collision replay; no IC relation yield or IC solve-work claim",
        "complete_IC_work_log2": None,
        "reference_sha256": digest(reference_path),
        "stopped_attempt_receipt_sha256": (
            digest(stopped_path) if same_stopped_workload else None),
        "verification_source_sha256": digest(Path(__file__)),
        "rho_log_sha256": digest(args.log),
        "rho_binary_sha256": digest(args.binary),
        "rho_source_sha256": digest(args.rho_source),
        "executed_driver_source_sha256": digest(args.driver_source),
        "portable_driver_source_sha256": digest(
            HERE / "n83_public_target_rho.cpp"),
    }
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"curve_id": CURVE_ID, "scalar": str(k),
                      "rho_walk_iterations_log2": report[
                          "rho_walk_iterations_log2"],
                      "independent_scalar_replay_passed": True}))


if __name__ == "__main__":
    main()
