#!/usr/bin/env python3
"""Build and solve one frozen shifted S3 fiber inside checked Sage."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import itertools
import json
import os
from pathlib import Path
import platform
import re
import resource
import subprocess
import sys
import time

import psutil

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "hamming-ic-e2e-20260929"
sys.path.insert(0, str(PRIOR))
sys.path.insert(0, str(HERE.parent / "pdp-scaling"))
from circuit import Circuit, s3  # noqa: E402
from gf2n import Curve, GF2n, INF, Point  # noqa: E402

PROTOCOL = HERE / "shifted_sat_protocol.json"
OLD_PUBLIC = PRIOR / "runs/n83_w34_sat_fixture_v1/public_input.json"
CMS = Path("/opt/homebrew/bin/cryptominisat5")
R = 2417851639230796216685689


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def times(curve: Curve, count: int, point: Point) -> Point:
    result = INF
    while count:
        if count & 1:
            result = curve.add(result, point)
        point = curve.add(point, point)
        count >>= 1
    return result


def parse_model(stdout: str) -> dict[int, bool] | None:
    if "s SATISFIABLE" not in stdout:
        return None
    assignments = {}
    for line in stdout.splitlines():
        if line.startswith("v "):
            for token in line[2:].split():
                literal = int(token)
                if literal:
                    assignments[abs(literal)] = literal > 0
    return assignments


def verify_model(circuit: Circuit, assignments: dict[int, bool]) -> bool:
    def value(literal: int):
        found = assignments.get(abs(literal))
        return None if found is None else (found if literal > 0 else not found)

    for clause in circuit.clauses:
        if not any(value(int(token)) is True for token in clause.split()[:-1]):
            return False
    for row in circuit.xors:
        values = [value(int(token)) for token in row.split()[1:-1]]
        if None in values or sum(values) % 2 != 1:
            return False
    return True


def build(geometry: dict, conjugates: list[int], target_x: int,
          pin_masks: list[int] | None, pin_middles: list[int] | None):
    m, d = geometry["arity"], geometry["dimension"]
    slots = geometry["slot_normal_basis_indices"]
    assert len(slots) == m and all(len(slot) == d for slot in slots)
    circuit = Circuit(83, [0, 2, 4, 7])
    factor_rows = [[circuit.variable() for _ in range(d)] for _ in range(m)]
    middle_rows = [[circuit.variable() for _ in range(83)] for _ in range(m - 2)]
    if pin_masks is not None:
        assert len(pin_masks) == m and len(pin_middles) == m - 2
        for mask, row in zip(pin_masks, factor_rows):
            assert 1 <= mask < (1 << d)
            for bit, variable in enumerate(row):
                circuit.clauses.append(f"{variable if mask & (1 << bit) else -variable} 0")
        for value, row in zip(pin_middles, middle_rows):
            assert 0 <= value < (1 << 83)
            for bit, variable in enumerate(row):
                circuit.clauses.append(f"{variable if value & (1 << bit) else -variable} 0")
    xs = [circuit.linear_element(row, [conjugates[i] for i in slot])
          for row, slot in zip(factor_rows, slots)]
    middles = [circuit.linear_element(row, [1 << bit for bit in range(83)])
               for row in middle_rows]
    for link in range(m - 1):
        left = xs[0] if link == 0 else middles[link - 1]
        right = xs[link + 1]
        output = middles[link] if link < m - 2 else circuit.constant(target_x)
        s3(circuit, left, right, output)
    return circuit, factor_rows


def replay(x_codes: list[int], target_xy: list[str], fiber_xy: list[str],
           representatives_path: Path) -> dict:
    field = GF2n(83, (1 << 83) | (1 << 7) | (1 << 4) | (1 << 2) | 1)
    curve = Curve(field, 1)
    target = Point(*map(int, target_xy))
    fiber = Point(*map(int, fiber_xy))
    assert curve.on_curve(target) and curve.on_curve(fiber)
    assert times(curve, 4, fiber) == target
    choices = []
    for x in x_codes:
        point = curve.lift_x(x)
        if point is None or point == INF:
            return {"verified": False, "reason": "nonrational_or_identity_factor_x"}
        choices.append((point, curve.neg(point)))
    raw = gzip.decompress(representatives_path.read_bytes())
    representatives = {tuple(row) for row in json.loads(raw)["representatives"]}

    def orbit_key(point):
        x, y = point.x, point.y
        keys = []
        for _ in range(83):
            keys.extend(((x, y), (x, x ^ y)))
            x, y = field.sqr(x), field.sqr(y)
        return min(keys)

    for option in itertools.product(*choices):
        raw_sum = curve.sum(list(option))
        if raw_sum != fiber:
            continue
        projections = [times(curve, 4, point) for point in option]
        if any(point == INF or times(curve, R, point) != INF for point in projections):
            continue
        keys = [orbit_key(point) for point in projections]
        if any(key not in representatives for key in keys):
            continue
        return {"verified": True,
                "raw_points": [[str(point.x), str(point.y)] for point in option],
                "raw_sum": [str(raw_sum.x), str(raw_sum.y)],
                "target_Q": target_xy,
                "distinct_signed_frobenius_orbits": len(set(keys)) == len(keys),
                "all_projected_factors_in_measured_base_orbits": True}
    return {"verified": False, "reason": "no_exact_fiber_group_lift_in_measured_base"}


def solve(xcnf: Path, out: Path, protocol: dict) -> dict:
    command = [str(CMS), "--verb=1", "--threads=1",
               f"--maxtime={protocol['solver_internal_seconds_per_branch']}",
               f"--maxconfl={protocol['solver_max_conflicts_per_branch']}", str(xcnf)]
    begin = time.perf_counter_ns()
    peak, guard = 0, None
    with (out / "solver.stdout.txt").open("wb") as stdout, \
         (out / "solver.stderr.txt").open("wb") as stderr:
        child = subprocess.Popen(command, stdout=stdout, stderr=stderr)
        process = psutil.Process(child.pid)
        deadline = time.monotonic() + protocol["external_wall_seconds_per_branch"]
        while child.poll() is None:
            try:
                peak = max(peak, process.memory_info().rss)
            except psutil.NoSuchProcess:
                pass
            if peak >= protocol["max_process_tree_rss_bytes_per_branch"]:
                guard = "solver_rss_guard"
            elif time.monotonic() >= deadline:
                guard = "solver_wall_guard"
            if guard:
                child.kill()
                break
            time.sleep(0.02)
        exit_code = child.wait()
    stdout_text = (out / "solver.stdout.txt").read_text(errors="replace")
    totals = {}
    for name in ("restarts", "decisions", "propagations", "conflicts"):
        values = re.findall(rf"(?m)^c {name}\s*:\s*(\d+)", stdout_text)
        totals[name] = int(values[-1]) if values else None
    return {"argv": command, "exit_code": exit_code, "guard": guard,
            "wall_ns": time.perf_counter_ns() - begin,
            "sampled_child_peak_rss_bytes": peak,
            "stdout_sha256": sha(out / "solver.stdout.txt"),
            "stderr_sha256": sha(out / "solver.stderr.txt"),
            "status_lines": [line for line in stdout_text.splitlines()
                             if line.startswith("s ")],
            "search_totals": totals}


def main(label: str, kind: str, index: int, out: Path, private_path: Path | None) -> None:
    out = out.resolve()
    runtime = out / "sage_runtime_info.json"
    if not out.is_dir() or not runtime.is_file() or (out / "started.json").exists():
        raise FileExistsError("branch output needs a fresh checked-Sage runtime receipt")
    if os.environ.get("N83_SHIFTED_SAT_EXTERNAL_GUARD") != "1":
        raise RuntimeError("run through bounded_shifted_sat.py")
    protocol = json.loads(PROTOCOL.read_text())
    geometry_path = HERE / "runs" / f"{label}_v1" / "geometry.json"
    geometry = json.loads(geometry_path.read_text())
    fixture_path = HERE / "runs" / f"{label}_sat_fixture_v1" / "public_input.json"
    public = json.loads(fixture_path.read_text())
    old = json.loads(OLD_PUBLIC.read_text())
    assert label in {item["label"] for item in protocol["geometry"]}
    assert sha(geometry_path) == public["geometry_sha256"]
    assert sha(OLD_PUBLIC) == protocol["public_ordinary_input_sha256"]
    assert public["curve_id"] == protocol["curve_id"] == geometry["curve_id"]
    assert kind in ("planted", "ordinary") and index in range(4)
    assert (private_path is None) or kind == "planted"
    if private_path is not None:
        private_path = private_path.resolve()
        private = json.loads(private_path.read_text())
        assert private["public_input_sha256"] == sha(fixture_path)
        witness = private["witness"]
        selected = witness["selected"]
        raw = [Point(*map(int, row["raw_point"])) for row in selected]
        curve = Curve(GF2n(83, (1 << 83) | (1 << 7) | (1 << 4) | (1 << 2) | 1), 1)
        assert all(curve.on_curve(point) for point in raw)
        assert curve.sum(raw) == Point(*map(int, witness["raw_sum"]))
        pin_masks = [int(row["mask_decimal"]) for row in selected]
        pin_middles = [curve.sum(raw[:count]).x for count in range(2, len(raw))]
    else:
        pin_masks = pin_middles = None
    branch = public[kind]["raw_target_fiber"][index]
    branch_x = int(branch["x"])
    if private_path is not None:
        assert branch_x == int(witness["raw_sum"][0])
    conjugates = [int(value) for value in old["normal_conjugates_polynomial_bits_decimal"]]
    assert len(conjugates) == 83
    assert sha(CMS) == protocol["solver_binary_sha256"]
    save(out / "started.json", {
        "kind": "n83_shifted_s3_bounded_sat_branch_start", "candidate_id": None,
        "label": label, "target_kind": kind, "fiber_index": index,
        "mode": "pinned_all" if private_path else "unpinned",
        "branch_target_x_decimal": str(branch_x),
        "public_input_sha256": sha(fixture_path),
        "private_fixture_sha256_local_only": sha(private_path) if private_path else None,
        "geometry_sha256": sha(geometry_path), "protocol_sha256": sha(PROTOCOL),
        "sage_runtime_info_sha256": sha(runtime),
        "source_sha256": {name: sha(path) for name, path in {
            "runner": Path(__file__), "circuit": PRIOR / "circuit.py",
            "gf2n": HERE.parent / "pdp-scaling/gf2n.py"}.items()},
        "solver_binary_sha256": sha(CMS),
        "architecture": platform.machine(), "os": platform.platform()})
    report = {"schema_version": 1, "kind": "n83_shifted_s3_bounded_sat_branch",
              "status": "INCOMPLETE", "candidate_id": None, "label": label,
              "target_kind": kind, "fiber_index": index,
              "branch_target_x_decimal": str(branch_x),
              "target_Q": public[kind]["target_Q"],
              "claim_boundary": protocol["claim_boundary"]}
    try:
        build_start = time.perf_counter_ns()
        circuit, rows = build(geometry, conjugates, branch_x, pin_masks, pin_middles)
        report["circuit_build_ns"] = time.perf_counter_ns() - build_start
        report["circuit"] = {"variables": circuit.next_var - 1,
                             "and_gates": circuit.and_count,
                             "cnf_clauses": len(circuit.clauses),
                             "xor_rows": len(circuit.xors)}
        xcnf = out / "branch.xcnf"
        write_start = time.perf_counter_ns()
        circuit.write(xcnf)
        report["xcnf_write_ns"] = time.perf_counter_ns() - write_start
        report["xcnf_bytes"] = xcnf.stat().st_size
        report["xcnf_sha256"] = sha(xcnf)
        report["solver"] = solve(xcnf, out, protocol)
        solver_text = (out / "solver.stdout.txt").read_text(errors="replace")
        model = parse_model(solver_text)
        if model is None:
            report["status"] = "UNSAT" if "s UNSATISFIABLE" in solver_text else "BOUNDED_UNKNOWN"
        elif not verify_model(circuit, model):
            report["status"] = "MODEL_INVALID"
        else:
            masks = [sum((1 << bit) for bit, variable in enumerate(row)
                         if model[variable]) for row in rows]
            x_codes = [0] * len(masks)
            for slot, mask in enumerate(masks):
                for bit, basis_index in enumerate(geometry["slot_normal_basis_indices"][slot]):
                    if mask & (1 << bit):
                        x_codes[slot] ^= conjugates[basis_index]
            report["model"] = {"mask_decimal": [str(mask) for mask in masks],
                               "factor_x_decimal": [str(value) for value in x_codes],
                               "cnf_xor_verified": True}
            representatives = geometry_path.parent / "representatives.json.gz"
            report["group_check"] = replay(x_codes, public[kind]["target_Q"],
                                           [branch["x"], branch["y"]], representatives)
            report["status"] = ("SAT_GROUP_VERIFIED_PENDING_SAGE" if
                                report["group_check"]["verified"] else "SAT_UNVERIFIED_GROUP")
        report["self_peak_rss_highwater"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        report["self_peak_rss_unit"] = "bytes" if platform.system() == "Darwin" else "kilobytes"
    except Exception as error:
        report["status"] = "ERROR"
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["started_sha256"] = sha(out / "started.json")
        save(out / "receipt.json", report)
        print(json.dumps({"label": label, "kind": kind, "fiber": index,
                          "status": report["status"]}, sort_keys=True), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("kind", choices=("planted", "ordinary"))
    parser.add_argument("fiber_index", type=int)
    parser.add_argument("out", type=Path)
    parser.add_argument("--pin-private", type=Path)
    args = parser.parse_args()
    main(args.label, args.kind, args.fiber_index, args.out, args.pin_private)
