"""Frozen N41 affine-four-seed m16 control and unpinned public query."""

import argparse
import hashlib
import json
import resource
import subprocess
import sys
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
UPSTREAM = ROOT / "n41_transport_cubic_s8_20261011"
PUBLIC = UPSTREAM / "fixture.json"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
sys.path.insert(0, str(ROOT.parent / "koblitz-polynomial-w-pair-20260925"))
from karatsuba_circuit import KaratsubaCircuit  # noqa: E402
import circuit  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_new(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def source_paths():
    return {"run.py": HERE / "run.py", "circuit.py": HERE / "circuit.py",
            "support.py": HERE / "support.py",
            "support_result.json": HERE / "support_result.json",
            "prepare_sage.py": HERE / "prepare_sage.py",
            "sage_runtime_info.json": HERE / "sage_runtime_info.json",
            "n41_public_fixture": PUBLIC, "n41_circuit": UPSTREAM / "circuit.py",
            "n131_circuit": ROOT / "n131_w18_cubic_s8_20261011" / "circuit.py",
            "halftrace_circuit": ROOT / "n41_cubic_halftrace_public_20261011" / "circuit.py",
            "sparse_algebra": ROOT / "n41_basis_aware_quartic_20261011" / "sparse.py",
            "karatsuba": ROOT.parent / "koblitz-polynomial-w-pair-20260925" / "karatsuba_circuit.py",
            "solver": SOLVER}


def freeze():
    public = json.loads(PUBLIC.read_text())
    support = json.loads((HERE / "support_result.json").read_text())
    assert support["status"] == "EXACT_AFFINE_FOUR_SEED_SOURCE_CENSUS"
    assert json.loads((HERE / "sage_runtime_info.json").read_text())["status"] == "verified"
    record = {"status": "FROZEN_BEFORE_N41_M16_CONTROL_AND_QUERY",
              "candidate_id": None,
              "curve_id": "EC1N41Ckb1h7d5e80d3c4d0",
              "public_target": public["public_target_original"],
              "transported_target": public["public_target_transported"],
              "public_raw_preimages": public["raw_target_reciprocals"],
              "affine_seeds": circuit.SEEDS,
              "rotations": circuit.ROTATIONS,
              "factor_base_B": support["n41"]["factor_base_B_eight_windows"],
              "folded_columns_K": support["n41"]["folded_columns_K"],
              "source_masks_per_window": 32,
              "workers": 1, "construction_cap_seconds": 120,
              "solver_cap_seconds": 120, "parent_cap_seconds": 125,
              "combined_rss_cap_bytes": 4*1024**3,
              "solver_flags": ["--threads=1", "--xor=0", "--printsol=1",
                               "--random=20261011", "--maxtime=120"],
              "source_sha256": {key: sha(path) for key, path in source_paths().items()}}
    save_new(HERE / "protocol.json", record)
    print(json.dumps({"status": record["status"], "B": record["factor_base_B"]}))


def protocol():
    record = json.loads((HERE / "protocol.json").read_text())
    assert record["source_sha256"] == {key: sha(path)
                                       for key, path in source_paths().items()}
    return record


def build(target_zs):
    public = json.loads(PUBLIC.read_text())
    columns = {int(k): int(v) for k, v in public["mask_columns"].items()}
    started = time.monotonic()
    cnf = KaratsubaCircuit(41, [0, 3])
    wires = circuit.build(cnf, circuit.Field(), columns, target_zs)
    return cnf, wires, time.monotonic()-started


def complete_assignment(cnf, initial):
    definitions = {int(out): ("and", int(a), int(b))
                   for (a, b), out in cnf.and_cache.items()}
    for line in cnf.xors:
        literals = [int(x) for x in line.split()[1:-1]]
        definitions[abs(literals[0])] = ("xor", literals)
    values = [None]*cnf.next_var
    for wire, value in initial.items():
        values[wire] = int(value)

    def val(wire):
        return 1 if wire == -1 else 0 if wire == 0 else values[wire]

    for wire in range(1, cnf.next_var):
        if values[wire] is not None:
            continue
        op, *args = definitions[wire]
        if op == "and":
            values[wire] = val(args[0]) & val(args[1])
        else:
            literals = args[0]
            bit = int(literals[0] > 0)
            for literal in literals[1:]:
                bit ^= values[abs(literal)] ^ int(literal < 0)
            values[wire] = bit
    return values


def check_assignment(cnf, values):
    for row in cnf.clauses:
        assert any(values[abs(lit)] == int(lit > 0)
                   for lit in map(int, row.split()[:-1]))
    for row in cnf.xors:
        assert sum(values[abs(lit)] ^ int(lit < 0)
                   for lit in map(int, row.split()[1:-1])) & 1
    return {"clauses": len(cnf.clauses), "native_xor_rows": len(cnf.xors)}


def control():
    p = protocol()
    f = json.loads((HERE / "control_fixture.json").read_text())
    assert f["status"] == "PASS_N41_AFFINE_FOUR_SEED_M16_GROUP_CONTROL"
    cnf, wires, construction = build([f["raw_reciprocal"]])
    initial = {}
    for name, key in (("masks", "masks"), ("pair_z", "pair_reciprocals"),
                      ("middle_z", "middle_reciprocals"),
                      ("upper_z", "upper_reciprocals")):
        for bits, value in zip(wires[name], f[key]):
            initial.update({wire: value >> bit & 1
                            for bit, wire in enumerate(bits)})
    for wire, bit in zip(wires["branch"], f["branch_bits"]):
        initial[wire] = bit
    assert len(initial) == len(wires["primary_variables"])
    checked = check_assignment(cnf, complete_assignment(cnf, initial))
    formula = HERE / "control.xcnf"
    cnf.write(formula)
    result = {"status": "PASS_COMPLETE_N41_M16_CIRCUIT_ASSIGNMENT",
              "formula_sha256": sha(formula), "formula_bytes": formula.stat().st_size,
              "variables": cnf.next_var-1, "and_gates": cnf.and_count,
              "assignment_check": checked, "source_bdd_nodes": wires["source_bdd_nodes"],
              "source_product_and_gates": wires["source_product_and_gates"],
              "construction_seconds_exploratory": construction,
              "control_fixture_sha256": sha(HERE / "control_fixture.json"),
              "protocol_sha256": sha(HERE / "protocol.json")}
    save_new(HERE / "control_result.json", result)
    print(json.dumps({"status": result["status"], "variables": result["variables"]}))


def query():
    p = protocol()
    assert json.loads((HERE / "control_result.json").read_text())["status"] == \
        "PASS_COMPLETE_N41_M16_CIRCUIT_ASSIGNMENT"
    start = time.monotonic()
    cnf, wires, construction = build(p["public_raw_preimages"])
    if construction > p["construction_cap_seconds"] or \
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss > p["combined_rss_cap_bytes"]:
        save_new(HERE / "query_result.json", {"status": "RESOURCE_GATE_EXCEEDED",
                                              "solver_started": False})
        return
    formula = HERE / "public.xcnf"
    write_start = time.monotonic()
    cnf.write(formula)
    write_seconds = time.monotonic()-write_start
    profile = {"variables": cnf.next_var-1, "and_gates": cnf.and_count,
               "clauses": len(cnf.clauses), "native_xor_rows": len(cnf.xors),
               "bytes": formula.stat().st_size, "sha256": sha(formula)}
    del cnf
    argv = [str(SOLVER), *p["solver_flags"], str(formula)]
    solver_start = time.monotonic()
    out, err = HERE / "solver.stdout.txt", HERE / "solver.stderr.txt"
    with out.open("xb") as stdout, err.open("xb") as stderr:
        process = subprocess.Popen(argv, stdout=stdout, stderr=stderr)
        worker, parent = psutil.Process(process.pid), psutil.Process()
        peak, stop_reason = 0, None
        while process.poll() is None:
            try:
                rss = worker.memory_info().rss + parent.memory_info().rss
            except psutil.NoSuchProcess:
                rss = parent.memory_info().rss
            peak = max(peak, rss)
            if rss > p["combined_rss_cap_bytes"]:
                stop_reason = "RSS_CAP"
            elif time.monotonic()-solver_start > p["parent_cap_seconds"]:
                stop_reason = "PARENT_CAP"
            if stop_reason:
                process.kill()
                break
            time.sleep(0.1)
        returncode = process.wait()
    solver_seconds = time.monotonic()-solver_start
    stdout = out.read_bytes()
    status = ("SAT_PENDING_GROUP_REPLAY" if b"s SATISFIABLE" in stdout else
              "UNSAT" if b"s UNSATISFIABLE" in stdout else
              "RESOURCE_GATE_EXCEEDED" if stop_reason == "RSS_CAP" else
              "BOUNDED_UNKNOWN")
    decoded = None
    if status == "SAT_PENDING_GROUP_REPLAY":
        positive, negative = set(), set()
        for line in stdout.splitlines():
            if not line.startswith(b"v "):
                continue
            for token in line.split()[1:]:
                value = int(token)
                if value:
                    (positive if value > 0 else negative).add(abs(value))
        if positive & negative or not set(wires["primary_variables"]) <= positive | negative:
            status = "INCOMPLETE_SAT_MODEL"
        else:
            def read(bits):
                return sum(int(wire in positive) << bit
                           for bit, wire in enumerate(bits))
            decoded = {"masks": [read(bits) for bits in wires["masks"]],
                       "pair_reciprocals": [read(bits) for bits in wires["pair_z"]],
                       "middle_reciprocals": [read(bits) for bits in wires["middle_z"]],
                       "upper_reciprocals": [read(bits) for bits in wires["upper_z"]],
                       "branch_bits": [int(wire in positive) for wire in wires["branch"]],
                       "raw_preimage_index": read(wires["target_flags"]),
                       "formula_sha256": profile["sha256"]}
            save_new(HERE / "model_decoded.json", decoded)
    post_seconds = time.monotonic()-solver_start-solver_seconds
    total = time.monotonic()-start
    result = {"status": status, "solver_started": True,
              "public_target": p["public_target"], "formula": profile,
              "construction_seconds": construction,
              "write_seconds": write_seconds,
              "solver_seconds": solver_seconds,
              "post_seconds": post_seconds,
              "total_seconds": total,
              "unallocated_seconds": total-construction-write_seconds-solver_seconds-post_seconds,
              "peak_combined_rss_bytes": peak,
              "stop_reason": stop_reason, "returncode": returncode,
              "stdout_sha256": sha(out), "stderr_sha256": sha(err),
              "protocol_sha256": sha(HERE / "protocol.json")}
    save_new(HERE / "query_result.json", result)
    print(json.dumps({"status": status, "solver_seconds": solver_seconds,
                      "variables": profile["variables"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "control", "query"))
    mode = parser.parse_args().mode
    {"freeze": freeze, "control": control, "query": query}[mode]()
