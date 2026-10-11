"""Freeze, control, and bounded public query for N131 W15 quartic five-pair."""

import argparse
import gzip
import hashlib
import json
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
sys.path.insert(0, str(GOAL.parent / "koblitz-polynomial-w-pair-20260925"))
from karatsuba_circuit import KaratsubaCircuit  # noqa: E402
import circuit as method  # noqa: E402

INPUT = GOAL / "n131_w15_unrestricted_fivepair_public_20261010/input.json"
BASELINE = GOAL / "n131_w15_unrestricted_fivepair_public_20261010/result.json"
FIBERS = HERE / "fibers.json"
ARITH = HERE / "arith_control.json"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
CAP = 600.0
RSS_CAP = 4 * 1024**3
FLAGS = ["--threads=1", "--xor=0", "--printsol=1", "--random=20261011"]


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def save(path, obj):
    Path(path).write_text(json.dumps(obj, sort_keys=True, indent=2) + "\n")


def sources():
    n41 = GOAL / "n41_basis_aware_quartic_20261011"
    w15 = GOAL / "n131_w15_coupled_sixpair_20261010"
    return {"run.py": HERE / "run.py", "circuit.py": HERE / "circuit.py",
            "arith_control.py": HERE / "arith_control.py",
            "arith_control.json": ARITH, "extract.py": HERE / "extract.py",
            "fibers.json": FIBERS, "input.json": INPUT,
            "baseline_result.json": BASELINE,
            "support_w15.tsv": w15 / "support_w15.tsv",
            "w15_circuit.py": w15 / "w15_circuit.py",
            "n41_sparse.py": n41 / "sparse.py",
            "n41_circuit.py": n41 / "circuit.py",
            "norm_result.json": GOAL / "n41_quartic_joint_public_20261010/norm_result.json",
            "karatsuba_circuit.py": GOAL.parent / "koblitz-polynomial-w-pair-20260925/karatsuba_circuit.py",
            "cryptominisat5": SOLVER,
            "sage_runtime_info.json": HERE / "sage_runtime_info.json"}


def freeze():
    data = json.loads(INPUT.read_text())
    fibers = json.loads(FIBERS.read_text())["fibers"]
    arithmetic = json.loads(ARITH.read_text())
    assert arithmetic["status"] == "PASS_N131_W15_TWO_QUARTIC_CONSTRUCTED_CONTROL"
    assert fibers[0]["projected_target"] == data["constructed_residual_target_q"]
    assert fibers[1]["projected_target"] == data["public_residual_target_q"]
    assert SOLVER.is_file()
    record = {"status": "FROZEN_N131_W15_BASIS_AWARE_FIVEPAIR",
              "candidate_id": None, "curve_id": data["curve_id"],
              "field": "GF(2)[t]/(t^131+t^13+t^2+t+1)",
              "constructed_residual_target_q": data["constructed_residual_target_q"],
              "public_target_q": data["public_target_q"],
              "public_residual_target_q": data["public_residual_target_q"],
              "fixed_prefix_masks": data["prefix_masks"],
              "fixed_prefix_columns": data["prefix_columns"],
              "source_dimension": 15, "rotations": list(method.ROTATIONS),
              "factor_base_B": 16441, "folded_columns_K": 16381,
              "workers": 1, "construction_plus_search_cap_seconds": CAP,
              "rss_cap_bytes": RSS_CAP, "solver_flags": FLAGS,
              "source_sha256": {name: sha(path) for name, path in sources().items()}}
    save(HERE / "protocol.json", record)
    print(json.dumps({"status": record["status"],
                      "source_count": len(record["source_sha256"])}))


def checked():
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["status"] == "FROZEN_N131_W15_BASIS_AWARE_FIVEPAIR"
    assert protocol["source_sha256"] == {name: sha(path) for name, path in sources().items()}
    return protocol


def build(index):
    fibers = json.loads(FIBERS.read_text())["fibers"]
    assert index in (0, 1)
    circuit = KaratsubaCircuit(131, [0, 1, 2, 13])
    started = time.monotonic()
    meta = method.build(circuit, fibers[index]["reciprocals"],
                        json.loads(INPUT.read_text())["prefix_columns"])
    elapsed = time.monotonic() - started
    return circuit, meta, elapsed


def profile(circuit, meta, elapsed):
    return {"variables": circuit.next_var - 1, "and_gates": circuit.and_count,
            "clauses": len(circuit.clauses), "native_xor_rows": len(circuit.xors),
            "quartic_and_gates": meta["quartic_and_gates"],
            "quartic_sparse_multiplications": meta["quartic_sparse_multiplications"],
            "quartic_generic_multiplications": meta["quartic_generic_multiplications"],
            "quartic_sparse_pair_products": meta["quartic_sparse_pair_products"],
            "last_pair_bilinear_ands": meta["last_pair_bilinear_ands"],
            "target_linear_ands": meta["target_linear_ands"],
            "construction_seconds_exploratory": elapsed,
            "parent_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}


def complete_assignment(circuit, initial):
    definitions = {int(out): ("and", int(a), int(b))
                   for (a, b), out in circuit.and_cache.items()}
    for line in circuit.xors:
        literals = [int(x) for x in line.split()[1:-1]]
        definitions[abs(literals[0])] = ("xor", literals)
    values = [None] * circuit.next_var
    for wire, bit in initial.items():
        values[wire] = int(bit)
    for wire in range(1, circuit.next_var):
        if values[wire] is not None:
            continue
        definition = definitions.get(wire)
        if definition is None:
            raise RuntimeError(f"unassigned primary wire {wire}")
        if definition[0] == "and":
            def value(x):
                return 1 if x == -1 else 0 if x == 0 else values[x]
            values[wire] = value(definition[1]) & value(definition[2])
        else:
            literals = definition[1]
            bit = int(literals[0] > 0)
            for literal in literals[1:]:
                bit ^= values[abs(literal)] ^ int(literal < 0)
            values[wire] = bit
    return values


def check_assignment(circuit, values):
    for row in circuit.clauses:
        literals = map(int, row.split()[:-1])
        assert any(values[abs(wire)] == int(wire > 0) for wire in literals)
    for row in circuit.xors:
        literals = map(int, row.split()[1:-1])
        assert sum(values[abs(wire)] ^ int(wire < 0) for wire in literals) & 1
    return {"clauses": len(circuit.clauses), "native_xor_rows": len(circuit.xors)}


def control():
    protocol = checked()
    data = json.loads(INPUT.read_text())
    arithmetic = json.loads(ARITH.read_text())
    circuit, meta, elapsed = build(0)
    initial = {}
    def bind(wires, value):
        initial.update({wire: value >> i & 1 for i, wire in enumerate(wires)})
    for wires, value in zip(meta["masks"], data["constructed_remaining_masks"]):
        bind(wires, value)
    selected = data["constructed_residual_preimage_index"]
    for i, wire in enumerate(meta["flags"]):
        initial[wire] = int(i == selected)
    for block in range(2):
        bind(meta["output_z"][block], arithmetic["blocks"][block]["z"])
        bind(meta["branch_w"][block], arithmetic["blocks"][block]["branches"][0])
    bind(meta["pair_z"], data["constructed_remaining_middle_reciprocals"][4])
    bind(meta["intermediate"], data["constructed_remaining_middle_reciprocals"][7])
    assert len(initial) == len(meta["primary_variables"])
    values = complete_assignment(circuit, initial)
    check = check_assignment(circuit, values)
    record = {"status": "PASS_N131_W15_FULL_QUARTIC_CONSTRUCTED_ASSIGNMENT",
              "candidate_id": None, "target": protocol["constructed_residual_target_q"],
              "selected_raw_lift": selected, "primary_variables": len(initial),
              "formula": profile(circuit, meta, elapsed), "assignment_check": check,
              "protocol_sha256": sha(HERE / "protocol.json")}
    save(HERE / "control_result.json", record)
    print(json.dumps({"status": record["status"], "formula": record["formula"]}))


def query():
    protocol = checked()
    control_result = json.loads((HERE / "control_result.json").read_text())
    assert control_result["status"] == "PASS_N131_W15_FULL_QUARTIC_CONSTRUCTED_ASSIGNMENT"
    start = time.monotonic()
    circuit, meta, elapsed = build(1)
    if elapsed >= 120 or resource.getrusage(resource.RUSAGE_SELF).ru_maxrss >= RSS_CAP:
        save(HERE / "query_result.json", {"status": "CONSTRUCTION_GATE_EXCEEDED",
                                         "solver_started": False,
                                         "formula": profile(circuit, meta, elapsed)})
        return
    with tempfile.NamedTemporaryFile(prefix="n131_w15_quartic_", suffix=".xcnf",
                                     dir="/private/tmp", delete=False) as handle:
        formula = Path(handle.name)
    try:
        circuit.write(formula)
        form = profile(circuit, meta, elapsed)
        form.update({"bytes": formula.stat().st_size, "sha256": sha(formula)})
        del circuit
        before_solver = time.monotonic() - start
        remaining = CAP - before_solver - 6
        assert remaining > 0
        with tempfile.NamedTemporaryFile(prefix="n131_w15_quartic_out_", dir="/private/tmp") as out, \
             tempfile.NamedTemporaryFile(prefix="n131_w15_quartic_err_", dir="/private/tmp") as err:
            process = subprocess.Popen([str(SOLVER), *FLAGS,
                                        f"--maxtime={int(remaining)-2}", str(formula)],
                                       stdout=out, stderr=err)
            parent = psutil.Process()
            child = psutil.Process(process.pid)
            solver_start = time.monotonic()
            peak = 0
            stop = None
            while process.poll() is None:
                try:
                    peak = max(peak, parent.memory_info().rss + child.memory_info().rss)
                except psutil.NoSuchProcess:
                    pass
                if peak >= RSS_CAP:
                    stop = "RSS_CAP"
                elif time.monotonic() - solver_start >= remaining:
                    stop = "TIME_CAP"
                if stop:
                    process.terminate()
                    break
                time.sleep(.1)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                stop = (stop or "DRAIN_TIMEOUT") + "_KILLED"
            solver_seconds = time.monotonic() - solver_start
            out.seek(0)
            err.seek(0)
            stdout = out.read()
            stderr = err.read()
        statuses = [line for line in stdout.splitlines() if line.startswith(b"s ")]
        model_lines = sum(line.startswith(b"v ") for line in stdout.splitlines())
        status = ("SAT_MODEL_PENDING_REPLAY" if statuses == [b"s SATISFIABLE"] and model_lines
                  else "UNSAT_FORMULA" if statuses == [b"s UNSATISFIABLE"]
                  else "BOUNDED_UNKNOWN" if stop == "TIME_CAP" or b"s INDETERMINATE" in statuses
                  else "RESOURCE_CAP" if stop == "RSS_CAP" else "SOLVER_FAILURE")
        with gzip.open(HERE / "solver.stdout.gz", "wb") as stream:
            stream.write(stdout)
        with gzip.open(HERE / "solver.stderr.gz", "wb") as stream:
            stream.write(stderr)
        with formula.open("rb") as source, gzip.open(HERE / "query.xcnf.gz", "wb") as dest:
            for block in iter(lambda: source.read(1 << 20), b""):
                dest.write(block)
        record = {"status": status, "target": protocol["public_target_q"],
                  "residual_target": protocol["public_residual_target_q"],
                  "solver_started": True, "solver_returncode": process.returncode,
                  "solver_stop": stop, "solver_status_lines": [x.decode() for x in statuses],
                  "model_lines": model_lines, "formula": form,
                  "peak_combined_rss_bytes": peak,
                  "phase_seconds": {"construction": elapsed,
                                    "write_and_hash": before_solver - elapsed,
                                    "solver": solver_seconds,
                                    "total": before_solver + solver_seconds},
                  "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
                  "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
                  "query_xcnf_gzip_sha256": sha(HERE / "query.xcnf.gz"),
                  "protocol_sha256": sha(HERE / "protocol.json")}
        save(HERE / "query_result.json", record)
        print(json.dumps({"status": status, "formula": form,
                          "phase_seconds": record["phase_seconds"]}))
    finally:
        formula.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "control", "query"))
    args = parser.parse_args()
    globals()[args.action]()
