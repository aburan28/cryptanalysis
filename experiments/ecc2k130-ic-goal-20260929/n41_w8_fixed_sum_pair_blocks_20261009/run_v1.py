#!/usr/bin/env python3
"""Frozen fixed-sum N41 control and unpinned public-point relation query."""

import argparse
import hashlib
import itertools
import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
sys.path.insert(0, str(GOAL))
import run_n41_disjoint_s5_sat as base
import circuit as method

ROOT = GOAL.parents[1]
sys.path.insert(0, str(ROOT / "experiments/koblitz-polynomial-w-pair-20260925"))
from karatsuba_circuit import KaratsubaCircuit

GEOMETRY = HERE / "geometry.json"
PUBLIC = GOAL / "n41_adjacent_pairpair/public_target.json"
PROTOCOL = HERE / "protocol.json"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
R = 549756390943


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rss():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value * 1024


def phi(field, point):
    if point is None or point[0] == 1:
        raise ValueError("exceptional point in target S3 chain")
    return field.inv(point[0] ^ 1)


def target_data(field, curve, geometry, mode):
    public = json.loads(PUBLIC.read_text())
    if mode == "public":
        q = tuple(public["target_q"])
    else:
        q = tuple(geometry["positive_control"]["subgroup_target"])
    if not curve.on_curve(q) or curve.mul(R, q) is not None:
        raise ValueError("target is not in the frozen subgroup")
    raw = base.target_preimages(field, curve, q)
    return q, raw, [phi(field, point) for point in raw]


def control_pins(circuit, wires, geometry, raw_targets):
    control = geometry["positive_control"]
    states = control["states"]
    if tuple(control["raw_target"]) not in raw_targets:
        raise ValueError("positive control raw target lacks a branch")
    def pin(row, value):
        for bit, wire in enumerate(row):
            circuit.clauses.append(f"{wire if value & (1 << bit) else -wire} 0")
    for block, state in enumerate(states):
        pin(wires["mask_wires"][block], state["a"])
        pin(wires["pair_output_wires"][block], state["z"])
    field = base.Field(41, [0, 3])
    curve = base.Curve(field, 0)
    points = [tuple(state["raw_sum"]) for state in states]
    middle = [curve.add(points[0], points[1]),
              curve.add(points[2], points[3]),
              curve.add(points[4], points[5])]
    middle.append(curve.add(middle[0], middle[1]))
    middle.append(curve.add(middle[3], middle[2]))
    if curve.add(middle[4], points[6]) != tuple(control["raw_target"]):
        raise ValueError("positive control balanced chain changed")
    for row, point in zip(wires["middle_wires"], middle):
        pin(row, phi(field, point))
    index = raw_targets.index(tuple(control["raw_target"]))
    circuit.clauses.append(f"{wires['target_flag_wires'][index]} 0")
    return {"target_flag": index, "masks": [row["a"] for row in states],
            "pair_outputs": [row["z"] for row in states]}


def build_formula(mode, geometry):
    field = base.Field(41, [0, 3])
    curve = base.Curve(field, 0)
    query_start = time.monotonic_ns()
    q, raw_targets, target_us = target_data(field, curve, geometry, mode)
    query_ns = time.monotonic_ns() - query_start
    circuit = KaratsubaCircuit(41, [0, 3])
    wires = method.build(circuit, geometry, target_us)
    pins = control_pins(circuit, wires, geometry, raw_targets) if mode == "control" else None
    output = HERE / mode
    output.mkdir(exist_ok=True)
    formula = output / "system.xcnf"
    if formula.exists():
        raise FileExistsError("preserve first frozen formula")
    circuit.write(formula)
    record = {"status": "FROZEN_FORMULA", "mode": mode,
              "curve_id": geometry["curve_id"], "candidate_id": None,
              "target_q": q, "raw_target_preimages": raw_targets,
              "target_us": target_us, "pins": pins, "wires": wires,
              "variables": circuit.next_var - 1,
              "cnf_clauses": len(circuit.clauses),
              "xor_rows": len(circuit.xors), "and_gates": circuit.and_count,
              "formula_sha256": sha(formula),
              "geometry_sha256": sha(GEOMETRY),
              "target_preimage_ns": query_ns}
    (output / "formula.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return record, formula, q


def parse_model(path):
    status = None
    assignment = {}
    for line in Path(path).read_text(errors="replace").splitlines():
        if line.startswith("s "):
            status = line[2:].strip()
        if line.startswith("v "):
            for token in line[2:].split():
                value = int(token)
                if value:
                    assignment[abs(value)] = value > 0
    return status, assignment


def verify_xcnf(formula_path, assignment):
    records = 0
    with Path(formula_path).open() as stream:
        header = stream.readline().split()
        if len(header) != 4 or header[:2] != ["p", "cnf"]:
            raise ValueError("invalid frozen XCNF header")
        variables, expected_records = int(header[2]), int(header[3])
        if len(assignment) < variables:
            raise ValueError("solver model omits Boolean variables")
        for line in stream:
            parts = line.split()
            if not parts or parts[0] == "c":
                continue
            parity = parts[0] == "x"
            literals = [int(value) for value in parts[1 if parity else 0:-1]]
            if parts[-1] != "0":
                raise ValueError("unterminated XCNF record")
            values = [assignment[abs(value)] == (value > 0) for value in literals]
            if (sum(values) % 2 != 1) if parity else (not any(values)):
                raise ValueError(f"model violates XCNF record {records}")
            records += 1
    if records != expected_records:
        raise ValueError("XCNF record count changed")
    return {"variables": variables, "records": records}


def decode(field, curve, geometry, formula_record, assignment, q):
    wires = formula_record["wires"]
    def code(row):
        return sum(1 << bit for bit, wire in enumerate(row) if assignment[wire])
    chosen = []
    for block in range(7):
        a = code(wires["mask_wires"][block])
        z = code(wires["pair_output_wires"][block])
        states = [state for state in geometry["blocks"][block]["states"]
                  if state["a"] == a and state["z"] == z]
        if len(states) != 2:
            raise ValueError(f"SAT pair output not in exact block {block}")
        chosen.append(states)
    flags = [assignment[wire] for wire in wires["target_flag_wires"]]
    if flags.count(True) != 1:
        raise ValueError("target flag not one-hot")
    raw_target = tuple(formula_record["raw_target_preimages"][flags.index(True)])
    for choices in itertools.product(*chosen):
        cols = [col for state in choices for col in state["columns"]]
        if len(set(cols)) != 14:
            continue
        total = None
        for state in choices:
            total = curve.add(total, tuple(state["raw_sum"]))
        if total == raw_target and curve.mul(4, total) == q:
            return {"raw_target": list(raw_target), "states": list(choices),
                    "folded_columns": cols,
                    "mask_codes": [state["a"] for state in choices],
                    "pair_output_z": [state["z"] for state in choices],
                    "target_flag": flags.index(True)}
    raise ValueError("SAT model did not lift to the target group point")


def run(mode):
    output = HERE / mode
    result_path = output / "result.json"
    if result_path.exists():
        raise FileExistsError("preserve first frozen result")
    protocol = json.loads(PROTOCOL.read_text())
    if protocol["status"] != "FROZEN" or protocol["source_sha256"] != {
            name: sha(path) for name, path in source_paths().items()}:
        raise ValueError("frozen source or runtime changed")
    geometry = json.loads(GEOMETRY.read_text())
    start = time.monotonic_ns()
    formula_record, formula, q = build_formula(mode, geometry)
    formula_ns = time.monotonic_ns() - start
    cap = protocol["control_wall_cap_seconds"] if mode == "control" else protocol["online_wall_cap_seconds"]
    stdout_path, stderr_path = output / "solver.stdout.txt", output / "solver.stderr.txt"
    peak_combined = rss()
    command = [str(SOLVER), "--threads=1", "--xor=0", "--printsol=1",
               "--random=20261009174000", "--maxconfl=2000000", str(formula)]
    solver_start = time.monotonic_ns()
    with stdout_path.open("x") as stdout, stderr_path.open("x") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                   cwd=HERE)
        child = psutil.Process(process.pid)
        terminal = None
        while True:
            exit_code = process.poll()
            if exit_code is not None:
                terminal = "EXIT"
                break
            try:
                combined = psutil.Process(os.getpid()).memory_info().rss + child.memory_info().rss
                peak_combined = max(peak_combined, combined)
            except psutil.NoSuchProcess:
                pass
            if peak_combined > protocol["rss_cap_bytes"]:
                terminal = "MEMORY_CAP"
                process.kill(); exit_code = process.wait(); break
            if (time.monotonic_ns() - start) / 1e9 > cap:
                terminal = "ONLINE_TIME_CAP" if mode == "public" else "CONTROL_TIME_CAP"
                process.kill(); exit_code = process.wait(); break
            time.sleep(0.1)
    solver_ns = time.monotonic_ns() - solver_start
    verification_start = time.monotonic_ns()
    status_line, assignment = parse_model(stdout_path)
    model_check = witness = None
    if status_line == "SATISFIABLE" and assignment:
        model_check = verify_xcnf(formula, assignment)
        witness = decode(base.Field(41, [0, 3]), base.Curve(base.Field(41,[0,3]),0),
                         geometry, formula_record, assignment, q)
        status = "FOUND_VERIFIED_RELATION"
    elif terminal in ("ONLINE_TIME_CAP", "CONTROL_TIME_CAP", "MEMORY_CAP"):
        status = terminal
    elif status_line == "UNSATISFIABLE":
        status = "PROVED_UNSAT"
    else:
        status = "BOUNDED_UNKNOWN" if exit_code == 0 else "PRODUCER_FAILURE"
    verification_ns = time.monotonic_ns() - verification_start
    total_ns = time.monotonic_ns() - start
    result = {"status": status, "mode": mode, "curve_id": geometry["curve_id"],
              "proposal_id": geometry["proposal_id"], "candidate_id": None,
              "run_id": None, "target_q": q, "target_count": 1,
              "target_preimage_ns": formula_record["target_preimage_ns"],
              "formula_build_and_query_ns": formula_ns,
              "solver_ns": solver_ns, "model_and_relation_check_ns": verification_ns,
              "charged_target_dependent_wall_ns": total_ns,
              "peak_combined_rss_bytes": max(peak_combined, rss()),
              "solver_status_line": status_line, "solver_exit_code": exit_code,
              "terminal_guard": terminal, "solver_command": command,
              "solver_stdout_sha256": sha(stdout_path),
              "solver_stderr_sha256": sha(stderr_path),
              "formula_sha256": formula_record["formula_sha256"],
              "model_check": model_check, "witness": witness,
              "protocol_sha256": sha(PROTOCOL),
              "source_sha256": protocol["source_sha256"]}
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: result[k] for k in
                      ("status", "mode", "charged_target_dependent_wall_ns",
                       "peak_combined_rss_bytes", "solver_status_line")}))


def source_paths():
    crypto = ROOT.parent / "crypto"
    return {
        "geometry.json": GEOMETRY, "geometry.py": HERE / "geometry.py",
        "circuit.py": HERE / "circuit.py", "run.py": HERE / "run.py",
        "audit.py": HERE / "audit.py", "public_target.json": PUBLIC,
        "basis8.json": GOAL / "n41_lowpower_w8_s6/basis8.json",
        "native_input.txt": GOAL / "n41_lowpower_w8_s6/native_input.txt",
        "run_n41_disjoint_s5_sat.py": GOAL / "run_n41_disjoint_s5_sat.py",
        "karatsuba_circuit.py": ROOT / "experiments/koblitz-polynomial-w-pair-20260925/karatsuba_circuit.py",
        "circuit_sat.py": ROOT / "experiments/koblitz-s5-invariant-20260924/circuit_sat.py",
        "independent_replay.py": crypto / "research/sat_factor_base_review_20260908/autolab_orbit_extract_20260924/independent_replay.py",
        "solver": SOLVER, "sage_runtime_info.json": HERE / "sage_runtime_info.json",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("control", "public"))
    run(parser.parse_args().mode)
