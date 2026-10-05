#!/usr/bin/env python3
"""Run one bounded N83 implicit-S3 SAT branch on the frozen public point."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import platform
import re
import resource
import subprocess
import sys
import time

import psutil

from circuit import Circuit, s3
from weight34 import require_weight_three_or_four


HERE = Path(__file__).resolve().parent
PROTOCOL = HERE / "n83_w34_sat_protocol.json"
CMS = Path("/opt/homebrew/bin/cryptominisat5")
GF2N = HERE.parent / "pdp-scaling"
sys.path.insert(0, str(GF2N))
from gf2n import Curve, GF2n, Point  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, record: dict) -> None:
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")


def build(target_x: int, conjugates: list[int], pinned_masks: list[list[int]] | None):
    circuit = Circuit(83, [0, 2, 4, 7])
    x_rows = [[circuit.variable() for _ in range(83)] for _ in range(5)]
    middle_rows = [[circuit.variable() for _ in range(83)] for _ in range(3)]
    counter_meta = [require_weight_three_or_four(circuit, row) for row in x_rows]
    if pinned_masks is not None:
        assert len(pinned_masks) == 5
        for row, mask in zip(x_rows, pinned_masks):
            assert len(mask) in (3, 4) and len(set(mask)) == len(mask)
            mask_set = set(mask)
            for bit, variable in enumerate(row):
                circuit.clauses.append(f"{variable if bit in mask_set else -variable} 0")
    xs = [circuit.linear_element(row, conjugates) for row in x_rows]
    middle = [circuit.linear_element(row, [1 << bit for bit in range(83)])
              for row in middle_rows]
    for a, b, c in ((xs[0], xs[1], middle[0]),
                    (middle[0], xs[2], middle[1]),
                    (middle[1], xs[3], middle[2]),
                    (middle[2], xs[4], circuit.constant(target_x))):
        s3(circuit, a, b, c)
    return circuit, {"x_rows": x_rows, "middle_rows": middle_rows,
                     "weight_counters": counter_meta}


def parse_model(stdout: str) -> dict[int, bool] | None:
    if "s SATISFIABLE" not in stdout:
        return None
    assignments = {}
    for line in stdout.splitlines():
        if line.startswith("v "):
            for word in line[2:].split():
                literal = int(word)
                if literal:
                    assignments[abs(literal)] = literal > 0
    return assignments


def verify_model(circuit: Circuit, assignments: dict[int, bool]) -> bool:
    def value(literal: int):
        found = assignments.get(abs(literal))
        return None if found is None else (found if literal > 0 else not found)

    for clause in circuit.clauses:
        values = [value(int(word)) for word in clause.split()[:-1]]
        if not any(item is True for item in values):
            return False
    for row in circuit.xors:
        values = [value(int(word)) for word in row.split()[1:-1]]
        if None in values or sum(values) % 2 != 1:
            return False
    return True


def group_replay(x_codes: list[int], target_xy: list[str]) -> dict:
    modulus = (1 << 83) | (1 << 7) | (1 << 4) | (1 << 2) | 1
    field = GF2n(83, modulus)
    curve = Curve(field, 1)
    target = Point(int(target_xy[0]), int(target_xy[1]))
    assert curve.on_curve(target)
    choices = []
    for x in x_codes:
        point = curve.lift_x(x)
        if point is None:
            return {"verified": False, "reason": "nonrational_factor_x"}
        choices.append((point, curve.neg(point)))
    for option in itertools.product(*choices):
        raw_sum = curve.sum(list(option))
        twice = curve.add(raw_sum, raw_sum)
        projected = curve.add(twice, twice)
        if projected == target:
            return {
                "verified": True,
                "raw_points": [[str(point.x), str(point.y)] for point in option],
                "raw_sum": [str(raw_sum.x), str(raw_sum.y)],
                "projected_sum": target_xy,
            }
    return {"verified": False, "reason": "no_five_point_group_lift"}


def run_solver(xcnf: Path, out: Path, protocol: dict) -> dict:
    command = [str(CMS), "--verb=1", "--threads=1",
               f"--maxtime={protocol['max_seconds_per_branch']}",
               f"--maxconfl={protocol['max_conflicts_per_branch']}", str(xcnf)]
    begin = time.perf_counter_ns()
    with (out / "solver.stdout.txt").open("wb") as stdout, \
         (out / "solver.stderr.txt").open("wb") as stderr:
        child = subprocess.Popen(command, stdout=stdout, stderr=stderr)
        process = psutil.Process(child.pid)
        peak = 0
        guard = None
        deadline = time.monotonic() + protocol["external_wall_limit_seconds_per_branch"]
        while child.poll() is None:
            try:
                peak = max(peak, process.memory_info().rss)
            except psutil.NoSuchProcess:
                pass
            if peak >= protocol["max_rss_bytes_per_branch"]:
                guard = "rss_guard"
                child.kill()
                break
            if time.monotonic() >= deadline:
                guard = "external_watchdog"
                child.kill()
                break
            time.sleep(0.02)
        exit_code = child.wait()
    stdout_text = (out / "solver.stdout.txt").read_text(errors="replace")
    totals = {}
    for name in ("restarts", "decisions", "propagations", "conflicts"):
        values = re.findall(rf"(?m)^c {name}\s*:\s*(\d+)", stdout_text)
        totals[name] = int(values[-1]) if values else None
    return {
        "argv": command, "exit_code": exit_code, "guard": guard,
        "wall_ns": time.perf_counter_ns() - begin,
        "sampled_child_peak_rss_bytes": peak,
        "stdout_sha256": sha(out / "solver.stdout.txt"),
        "stderr_sha256": sha(out / "solver.stderr.txt"),
        "status_lines": [line for line in stdout_text.splitlines() if line.startswith("s ")],
        "search_totals": totals,
    }


def main(public_path: Path, out: Path, branch_x: int, private_path: Path | None) -> None:
    public_path, out = public_path.resolve(), out.resolve()
    if out.exists():
        raise FileExistsError("SAT branch output is immutable")
    out.mkdir(parents=True)
    protocol = json.loads(PROTOCOL.read_text())
    public = json.loads(public_path.read_text())
    assert public["curve_id"] == protocol["curve_id"]
    assert public["full_w4_geometry_sha256"] == protocol["full_w4_geometry_sha256"]
    assert public["field_degree"] == 83 and public["field_polynomial_low_terms"] == [0, 2, 4, 7]
    assert CMS.is_file()
    fiber_x = {int(point["x"]) for point in public["planted"]["raw_target_fiber"]}
    assert branch_x in fiber_x
    pinned_masks = None
    private_sha = None
    if private_path is not None:
        private_path = private_path.resolve()
        private = json.loads(private_path.read_text())
        assert private["public_input_sha256"] == sha(public_path)
        assert branch_x == int(private["raw_sum"][0])
        pinned_masks = [row["mask"] for row in private["selected"]]
        private_sha = sha(private_path)
    source_paths = [Path(__file__), HERE / "circuit.py", HERE / "weight34.py", GF2N / "gf2n.py"]
    save(out / "started.json", {
        "kind": "n83_w34_implicit_s3_sat_branch_start",
        "curve_id": protocol["curve_id"], "candidate_id": None,
        "mode": "pinned" if pinned_masks is not None else "unpinned",
        "branch_target_x_decimal": str(branch_x),
        "public_input_sha256": sha(public_path),
        "private_fixture_sha256_local_only": private_sha,
        "protocol_sha256": sha(PROTOCOL),
        "source_sha256": {path.name: sha(path) for path in source_paths},
        "solver_binary_sha256": sha(CMS),
        "architecture": platform.machine(), "os": platform.platform(),
    })
    report = {"status": "INCOMPLETE", "claim_boundary": protocol["claim_boundary"]}
    try:
        # The limit is on this process (including circuit generation), not just CMS.
        limit = protocol["max_rss_bytes_per_branch"]
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
        before = time.perf_counter_ns()
        conjugates = [int(value) for value in public["normal_conjugates_polynomial_bits_decimal"]]
        assert len(conjugates) == 83
        circuit, meta = build(branch_x, conjugates, pinned_masks)
        report["circuit_build_ns"] = time.perf_counter_ns() - before
        report["circuit"] = {
            "variables": circuit.next_var - 1,
            "and_gates": circuit.and_count,
            "cnf_clauses": len(circuit.clauses),
            "xor_rows": len(circuit.xors),
            "self_peak_rss_highwater": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "self_peak_rss_unit": "bytes" if platform.system() == "Darwin" else "kilobytes",
        }
        xcnf = out / "branch.xcnf"
        write_start = time.perf_counter_ns()
        circuit.write(xcnf)
        report["xcnf_write_ns"] = time.perf_counter_ns() - write_start
        report["xcnf_bytes"] = xcnf.stat().st_size
        report["xcnf_sha256"] = sha(xcnf)
        solver = run_solver(xcnf, out, protocol)
        report["solver"] = solver
        stdout = (out / "solver.stdout.txt").read_text(errors="replace")
        model = parse_model(stdout)
        if model is None:
            report["status"] = "UNSAT" if "s UNSATISFIABLE" in stdout else "BOUNDED_UNKNOWN"
        else:
            report["model_clause_xor_verified"] = verify_model(circuit, model)
            if not report["model_clause_xor_verified"]:
                report["status"] = "MODEL_INVALID"
            else:
                masks = [[bit for bit, variable in enumerate(row) if model[variable]]
                         for row in meta["x_rows"]]
                assert all(len(mask) in (3, 4) for mask in masks)
                x_codes = [0] * 5
                for index, mask in enumerate(masks):
                    for bit in mask:
                        x_codes[index] ^= conjugates[bit]
                report["model"] = {"masks": masks,
                                   "x_codes_decimal": [str(value) for value in x_codes]}
                group = group_replay(x_codes, public["planted"]["target_Q"])
                report["group_check"] = group
                report["status"] = "SAT_GROUP_VERIFIED_PENDING_SAGE" if group["verified"] else "SAT_UNVERIFIED_GROUP"
        report["self_peak_rss_highwater"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except Exception as error:
        report["status"] = "ERROR"
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["started_sha256"] = sha(out / "started.json")
        save(out / "receipt.json", report)
        print(json.dumps({"status": report["status"],
                          "branch_target_x_decimal": str(branch_x)}, sort_keys=True), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("public_input", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("branch_x", type=int)
    parser.add_argument("--pin-private", type=Path)
    args = parser.parse_args()
    main(args.public_input, args.out, args.branch_x, args.pin_private)
