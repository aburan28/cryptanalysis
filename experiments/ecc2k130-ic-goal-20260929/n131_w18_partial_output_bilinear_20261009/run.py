#!/usr/bin/env python3
"""Exact bilinear W18 pair equation with a partially assigned output."""

import hashlib
import json
import resource
import subprocess
import sys
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
PAIR_SOURCE = GOAL.parent / "koblitz-polynomial-w-pair-20260925/pair_oracle.py"
CIRCUIT_SOURCE = GOAL.parent / "koblitz-s5-invariant-20260924/circuit_sat.py"
REPLAY_SOURCE = Path("/Volumes/SSD990/crypto/research/sat_factor_base_review_20260908/autolab_orbit_extract_20260924/independent_replay.py")
PROBE = GOAL / "n131_w18_full_width_pair_oracle/probe.json"
PROBE_AUDIT = GOAL / "n131_w18_full_width_pair_oracle/independent_sage_replay.json"
AFFINE = GOAL / "n131_w18_partial_output_linear_gate.json"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
sys.path.insert(0, str(PAIR_SOURCE.parent))
sys.path.insert(0, str(CIRCUIT_SOURCE.parent))
from pair_oracle import Field, half_trace  # noqa: E402
from circuit_sat import Circuit  # noqa: E402

N = 131
K = 48
PROPOSAL_ID = "Q20261009191200"
SOLVER_CAP_SECONDS = 12
PARENT_CAP_SECONDS = 15
RSS_CAP_BYTES = 4 * 1024**3


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_paths():
    return [HERE / "run.py", HERE / "freeze.py", HERE / "audit.py",
            HERE / "sage_runtime_info.json", PAIR_SOURCE, CIRCUIT_SOURCE,
            REPLAY_SOURCE, PROBE, PROBE_AUDIT, AFFINE, SOLVER]


def first_positive():
    probe = json.loads(PROBE.read_text())
    if probe["status"] != "PASS" or probe["verified_queries"] != 128:
        raise ValueError("positive source is not complete")
    return next(q for q in probe["queries"] if q.get("z") is not None)


def setup():
    field = Field(N, [0, 1, 2, 13])
    half_squares = []
    half_basis = []
    for bit in range(1, 19):
        value = half_trace(field, 1 << bit)
        half_basis.append(value)
        half_squares.append(field.mul(value, value))
    positive = first_positive()
    witness = positive["matching_witnesses"][0]
    w1, w2 = (sum(((mask >> bit) & 1) << (bit + 1) for bit in range(18))
              for mask in witness["w_masks"])
    hsum = 0
    for bit in range(18):
        if ((witness["w_masks"][0] ^ witness["w_masks"][1]) >> bit) & 1:
            hsum ^= half_basis[bit]
    z = positive["z"]
    lhs = field.mul(z, z)
    rhs = (field.mul(hsum, hsum) ^ witness["epsilon"] ^
           field.mul(field.mul(z, z) ^ z, field.mul(w1, w2)))
    if lhs != rhs:
        raise ValueError("frozen positive fails bilinear S3 preflight")
    affine = json.loads(AFFINE.read_text())
    if z != affine["source_positive_pair_outputs"][0]:
        raise ValueError("positive control changed")
    return field, half_squares, positive, affine["uniform_field_controls"][0]


def build_formula(z, half_squares, pinned=None):
    circuit = Circuit(N, [0, 1, 2, 13])
    first = [circuit.variable() for _ in range(18)]
    second = [circuit.variable() for _ in range(18)]
    parity = circuit.variable()
    unknown = set(range(K))
    output = [circuit.variable() if bit in unknown else
              (-1 if (z >> bit) & 1 else 0) for bit in range(N)]
    basis = [1 << (bit + 1) for bit in range(18)]
    w1 = circuit.linear_element(first, basis)
    w2 = circuit.linear_element(second, basis)
    seed_sum = [circuit.xor((a, b)) for a, b in zip(first, second)]
    half_square = circuit.linear_element(seed_sum, half_squares)
    output_square = circuit.square(output)
    artin_schreier = circuit.add(output_square, output)
    pair_product = circuit.mul(w1, w2)
    equation = circuit.add(output_square, half_square)
    equation = circuit.add(equation, [parity] + [0] * (N - 1))
    equation = circuit.add(equation, circuit.mul(artin_schreier, pair_product))
    circuit.require_zero(equation)
    if pinned is not None:
        for wires, mask in ((first, pinned["w_masks"][0]),
                            (second, pinned["w_masks"][1])):
            for bit, wire in enumerate(wires):
                circuit.clauses.append(f"{wire if (mask >> bit) & 1 else -wire} 0")
        circuit.clauses.append(f"{parity if pinned['epsilon'] else -parity} 0")
        for bit in unknown:
            wire = output[bit]
            circuit.clauses.append(f"{wire if (z >> bit) & 1 else -wire} 0")
    text = (f"p cnf {circuit.next_var - 1} "
            f"{len(circuit.clauses) + len(circuit.xors)}\n" +
            "\n".join(circuit.clauses + circuit.xors) + "\n")
    counts = {"variables": circuit.next_var - 1,
              "cnf_clauses": len(circuit.clauses),
              "native_xor_rows": len(circuit.xors),
              "and_gates": circuit.and_count}
    return text, counts


def run_one(name, z, half_squares, pinned):
    outdir = HERE / name
    outdir.mkdir()
    online_start = time.monotonic_ns()
    formula, counts = build_formula(z, half_squares, pinned)
    formula_path = outdir / "query.xcnf"
    formula_path.write_text(formula)
    build_ns = time.monotonic_ns() - online_start
    command = [str(SOLVER), "--threads", "1", "--verb", "0",
               "--maxtime", str(SOLVER_CAP_SECONDS), "/dev/stdin"]
    solver_start = time.monotonic_ns()
    stdout_path = outdir / "solver.stdout.txt"
    stderr_path = outdir / "solver.stderr.txt"
    status = "EXITED"
    peak_rss = 0
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        process = subprocess.Popen(command, stdin=subprocess.PIPE,
                                   stdout=stdout, stderr=stderr)
        process.stdin.write(formula.encode())
        process.stdin.close()
        tracked = psutil.Process(process.pid)
        while process.poll() is None:
            try:
                peak_rss = max(peak_rss, tracked.memory_info().rss)
            except psutil.Error:
                pass
            if peak_rss > RSS_CAP_BYTES:
                status = "MEMORY_GUARD"
                process.kill()
                break
            if time.monotonic_ns() - solver_start >= PARENT_CAP_SECONDS * 10**9:
                status = "PARENT_TIME_CAP"
                process.kill()
                break
            time.sleep(0.01)
        process.wait()
    peak_rss = max(peak_rss, resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss *
                   (1 if sys.platform == "darwin" else 1024))
    solver_ns = time.monotonic_ns() - solver_start
    check_start = time.monotonic_ns()
    stdout_text = stdout_path.read_text(errors="replace")
    lines = [line for line in stdout_text.splitlines() if line.startswith("s ")]
    solver_status = lines[-1] if lines else None
    if status == "EXITED":
        status = {"s SATISFIABLE": "SAT", "s UNSATISFIABLE": "UNSAT",
                  "s INDETERMINATE": "INDETERMINATE"}.get(solver_status,
                                                             "NO_STATUS")
    check_ns = time.monotonic_ns() - check_start
    total_ns = time.monotonic_ns() - online_start
    row = {"name": name, "status": status, "z": z,
           "unknown_output_bits": K, "pinned_leaf_witness": pinned is not None,
           "counts": counts, "command": command, "process_returncode": process.returncode,
           "solver_status_line": solver_status, "formula_sha256": sha(formula_path),
           "stdout_sha256": sha(stdout_path), "stderr_sha256": sha(stderr_path),
           "build_ns": build_ns, "solver_ns": solver_ns,
           "terminal_check_ns": check_ns,
           "interval_overhead_ns": total_ns - build_ns - solver_ns - check_ns,
           "charged_stage_ns": total_ns, "sampled_solver_peak_rss_bytes": peak_rss}
    (outdir / "result.json").write_text(json.dumps(row, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: row[key] for key in
                      ("name", "status", "charged_stage_ns", "sampled_solver_peak_rss_bytes")},
                     sort_keys=True), flush=True)
    return row


def main():
    if (HERE / "result.json").exists():
        raise FileExistsError("preserve first frozen result")
    protocol = json.loads((HERE / "protocol.json").read_text())
    if protocol["source_sha256"] != {str(path): sha(path) for path in source_paths()}:
        raise ValueError("frozen source or input changed")
    setup_start = time.monotonic_ns()
    _, half_squares, positive, control_z = setup()
    setup_ns = time.monotonic_ns() - setup_start
    rows = [run_one("pinned_positive", positive["z"], half_squares,
                    positive["matching_witnesses"][0]),
            run_one("positive_partial", positive["z"], half_squares, None),
            run_one("field_control_partial", control_z, half_squares, None)]
    result = {"status": "COMPLETE_THREE_CASE_DIAGNOSTIC",
              "proposal_id": PROPOSAL_ID, "candidate_id": None, "run_id": None,
              "curve_id": "EC1N131Ckb1h136f03e58c98", "target_count": 0,
              "setup_ns": setup_ns, "cases": rows,
              "total_charged_stage_ns": sum(row["charged_stage_ns"] for row in rows),
              "protocol_sha256": sha(HERE / "protocol.json"),
              "source_sha256": protocol["source_sha256"],
              "peak_parent_rss_bytes": (resource.getrusage(resource.RUSAGE_SELF).ru_maxrss *
                                        (1 if sys.platform == "darwin" else 1024))}
    (HERE / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
