#!/usr/bin/env python3
"""Frozen public-target reciprocal-coordinate SAT gate for eight atoms."""

import argparse
import hashlib
import itertools
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
sys.path.insert(0, str(BASE))
import run_n41_disjoint_s5_sat as base
import check_n41_lowpower_w8_s6_witness as witness_tools
import reciprocal_circuit as method

GEOMETRY = BASE / "n41_two_free_pair_occupancy_20261009/geometry_snapshot.json"
SCREEN = HERE / "screen.json"
JOIN = HERE / "join_result.json"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
RUNTIME = HERE / "sage_runtime_info.json"
FORMULA = HERE / "reciprocal_public.xcnf"
PROTOCOL = HERE / "sat_protocol.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def frob(f, p, n):
    x, y = p
    for _ in range(n):
        x, y = f.mul(x, x), f.mul(y, y)
    return x, y


def context():
    geom = json.loads(GEOMETRY.read_text())["n41"]
    field = base.Field(41, [0, 3])
    curve = base.Curve(field, 0)
    rows = geom["point_rows_by_unique_rotation"]["0"]
    columns = {int(row[3]): int(row[2]) for row in rows}
    assert len(columns) == 32 and len(set(columns.values())) == 26
    by_mask_sign = {(int(row[3]), int(row[5])): tuple(row[:2]) for row in rows}
    basis = geom["window_basis_w"][0]
    half_basis = geom["window_basis_halftrace"][0]
    rotations = json.loads(SCREEN.read_text())["slot_rotations"]
    bases = [[field_pow2(field, bit, rotation) for bit in basis]
             for rotation in rotations]
    return field, curve, geom, columns, by_mask_sign, basis, half_basis, rotations, bases


def field_pow2(f, value, steps):
    for _ in range(steps):
        value = f.mul(value, value)
    return value


def raw_atom(f, curve, by_mask_sign, half_basis, mask, sign, rotation):
    u = base.coordinate(half_basis, mask)
    raw_x = 1 ^ f.inv(u)
    source_subgroup = by_mask_sign[(mask, sign)]
    source = [p for p in base.points_with_x(curve, raw_x)
              if curve.mul(4, p) == source_subgroup]
    assert len(source) == 1
    p = frob(f, source[0], rotation)
    d = curve.add(p, frob(f, p, 1))
    assert d is not None
    return d


def chain(curve, atoms):
    middles = [curve.add(atoms[2*i], atoms[2*i+1]) for i in range(4)]
    middles += [curve.add(middles[0], middles[1]),
                curve.add(middles[2], middles[3])]
    total = curve.add(middles[4], middles[5])
    return middles, total


def formula_context():
    f, curve, geom, columns, by_mask_sign, basis, halves, rotations, bases = context()
    q = tuple(geom["public_target_q"])
    lifts = base.target_preimages(f, curve, q)
    assert len(lifts) == 4 and all(p[0] != 0 for p in lifts)
    target_values = [f.inv(p[0]) for p in lifts]
    return f, curve, geom, columns, by_mask_sign, halves, rotations, bases, q, lifts, target_values


def build():
    f, curve, geom, columns, by_mask_sign, halves, rotations, bases, q, lifts, target_values = formula_context()
    circuit = base.KaratsubaCircuit(41, [0, 3])
    meta = method.build(circuit, bases, [columns] * 8, target_values)
    circuit.write(FORMULA)
    stats = {"variables": circuit.next_var - 1,
             "clauses": len(circuit.clauses), "xor_rows": len(circuit.xors),
             "and_gates": circuit.and_count, "bytes": FORMULA.stat().st_size,
             "sha256": sha(FORMULA)}
    return circuit, meta, stats, (f, curve, geom, columns, by_mask_sign,
                                 halves, rotations, bases, q, lifts, target_values)


def prepare():
    if FORMULA.exists() or PROTOCOL.exists():
        raise FileExistsError("reciprocal SAT artifacts already exist")
    assert json.loads(RUNTIME.read_text())["status"] == "verified"
    circuit, meta, stats, ctx = build()
    f, curve, geom, columns, by_mask_sign, halves, rotations, bases, q, lifts, target_values = ctx
    witness = json.loads(JOIN.read_text())["verified_relation"]
    masks, signs = witness["seed_masks"], witness["curve_sign_indices"]
    atoms = [raw_atom(f, curve, by_mask_sign, halves, mask, sign, rotation)
             for mask, sign, rotation in zip(masks, signs, rotations)]
    for i, atom in enumerate(atoms):
        assert f.inv(atom[0]) == base.coordinate(bases[i], masks[i])
    middle, raw_total = chain(curve, atoms)
    assert all(p is not None and p[0] != 0 for p in [*middle, raw_total])
    assert curve.mul(4, raw_total) == q
    endpoint = lifts.index(raw_total)
    initial = {}
    for row, mask in zip(meta["masks"], masks):
        initial.update({wire: mask >> bit & 1 for bit, wire in enumerate(row)})
    for i, wire in enumerate(meta["flags"]):
        initial[wire] = int(i == endpoint)
    for row, point in zip(meta["middle"], middle):
        reciprocal = f.inv(point[0])
        initial.update({wire: reciprocal >> bit & 1 for bit, wire in enumerate(row)})
    assert len(initial) == meta["primary_variables"]
    assignment = witness_tools.complete_assignment(circuit, initial)
    xcnf_check = base.check_xcnf(FORMULA, assignment)
    planted = {"status": "PASS_FULL_FORMULA_AND_GROUP_CONTROL",
               "masks": masks, "signs": signs, "target_preimage_index": endpoint,
               "raw_target": list(raw_total), "middle": [list(p) for p in middle],
               "xcnf_check": xcnf_check, "formula": stats}
    save(HERE / "reciprocal_control.json", planted)
    protocol = {"status": "FROZEN", "candidate_id": None,
                "curve_id": geom["curve_id"], "public_target": list(q),
                "method": "eight diagonal atoms, reciprocal leaf linear in W6, balanced S3",
                "limits": {"workers": 1, "online_wall_seconds": 120,
                           "solver_parent_wall_seconds": 115,
                           "peak_rss_bytes": 4294967296},
                "solver_flags": ["--threads=1", "--xor=0", "--printsol=1",
                                 "--random=20261010", "--maxconfl=2000000"],
                "source_sha256": {"sat": sha(Path(__file__)),
                                  "circuit": sha(Path(method.__file__)),
                                  "base": sha(Path(base.__file__)),
                                  "assignment": sha(Path(witness_tools.__file__)),
                                  "geometry": sha(GEOMETRY), "screen": sha(SCREEN),
                                  "join": sha(JOIN), "solver": sha(SOLVER),
                                  "runtime": sha(RUNTIME),
                                  "formula": sha(FORMULA),
                                  "control": sha(HERE / "reciprocal_control.json")}}
    save(PROTOCOL, protocol)
    print(json.dumps({"status": planted["status"], "formula": stats}))


def query():
    protocol = json.loads(PROTOCOL.read_text())
    paths = {"sat": Path(__file__), "circuit": Path(method.__file__),
             "base": Path(base.__file__), "assignment": Path(witness_tools.__file__),
             "geometry": GEOMETRY, "screen": SCREEN, "join": JOIN,
             "solver": SOLVER, "runtime": RUNTIME, "formula": FORMULA,
             "control": HERE / "reciprocal_control.json"}
    assert {name: sha(path) for name, path in paths.items()} == protocol["source_sha256"]
    stdout = HERE / "reciprocal_solver.stdout.txt"
    stderr = HERE / "reciprocal_solver.stderr.txt"
    if stdout.exists() or stderr.exists():
        raise FileExistsError("solver output already exists")
    command = [str(SOLVER), *protocol["solver_flags"], "--maxtime=113", str(FORMULA)]
    parent = psutil.Process(os.getpid())
    began = time.monotonic()
    peak_rss = 0
    stop = None
    with stdout.open("xb") as out, stderr.open("xb") as err:
        proc = subprocess.Popen(command, stdout=out, stderr=err,
                                start_new_session=True)
        child = psutil.Process(proc.pid)
        while proc.poll() is None:
            try:
                peak_rss = max(peak_rss, child.memory_info().rss + parent.memory_info().rss)
            except psutil.NoSuchProcess:
                pass
            elapsed = time.monotonic() - began
            if peak_rss >= protocol["limits"]["peak_rss_bytes"]:
                stop = "RSS_CAP"
            elif elapsed >= protocol["limits"]["solver_parent_wall_seconds"]:
                stop = "SOLVER_WALL_CAP"
            if stop:
                proc.terminate()
                break
            time.sleep(.1)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            stop = (stop or "DRAIN_TIMEOUT") + "_KILLED"
    wall = time.monotonic() - began
    output = stdout.read_text(errors="replace")
    lines = [line for line in output.splitlines() if line.startswith("s ")]
    model_lines = sum(line.startswith("v ") for line in output.splitlines())
    if lines == ["s SATISFIABLE"] and model_lines:
        status = "MODEL_PENDING_GROUP_REPLAY"
    elif lines == ["s UNSATISFIABLE"]:
        status = "UNSAT_FORMULA"
    elif stop or "s INDETERMINATE" in lines:
        status = "CENSORED_TIME" if stop != "RSS_CAP" else "OOM"
    else:
        status = "PRODUCER_OR_SOLVER_FAILURE"
    result = {"status": status, "candidate_id": None,
              "curve_id": protocol["curve_id"], "public_target": protocol["public_target"],
              "solver_command": command, "solver_exit_code": proc.returncode,
              "status_lines": lines, "model_lines": model_lines, "stop_reason": stop,
              "solver_wall_seconds": wall, "sampled_peak_rss_bytes": peak_rss,
              "formula_sha256": sha(FORMULA), "protocol_sha256": sha(PROTOCOL),
              "stdout_sha256": sha(stdout), "stderr_sha256": sha(stderr)}
    save(HERE / "reciprocal_result.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["prepare", "query"])
    args = parser.parse_args()
    {"prepare": prepare, "query": query}[args.mode]()
