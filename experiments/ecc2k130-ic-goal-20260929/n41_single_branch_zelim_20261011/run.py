"""Freeze, control-check, and query the target-coupled N41 quartic circuit."""

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
ROOT = HERE.parent
sys.path.insert(0, str(ROOT.parent / "koblitz-polynomial-w-pair-20260925"))
from karatsuba_circuit import KaratsubaCircuit  # noqa: E402
import circuit as method  # noqa: E402

SOURCE_INPUT = ROOT / "n41_coupled_sixpair_full_ic_20261010" / "heldout_input.txt"
PUBLIC_LIFTS = ROOT / "rotated_fouratom_public_lift_correction_20261010" / "result.json"
KNOWN_BLOCKS = ROOT / "rotated_fouratom_public_lift_correction_20261010" / "lift_result.json"
KNOWN_BRANCHES = ROOT / "n41_quartic_joint_public_20261010" / "audit_result.json"
NORM = ROOT / "n41_quartic_joint_public_20261010" / "norm_result.json"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
RSS_CAP = 4 * 1024**3
CONSTRUCTION_CAP = 120
SOLVER_CAP = 60


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, data):
    Path(path).write_text(json.dumps(data, sort_keys=True, indent=2) + "\n")


def inputs():
    target, columns = method.source_columns(SOURCE_INPUT)
    corrected = json.loads(PUBLIC_LIFTS.read_text())["n41"]
    assert list(target) == corrected["public_target"]
    branches = [row["z_h_reciprocal_x"] for row in corrected["preimages"][:2]]
    assert [row["trace_z_h"] for row in corrected["preimages"]] == [0, 0, 1, 1]
    return target, columns, branches


def sources():
    return {"run.py": Path(__file__), "circuit.py": HERE / "circuit.py",
            "norm_result.json": NORM, "heldout_input.txt": SOURCE_INPUT,
            "corrected_lifts.json": PUBLIC_LIFTS,
            "known_blocks.json": KNOWN_BLOCKS,
            "known_branch_audit.json": KNOWN_BRANCHES,
            "karatsuba_circuit.py": ROOT.parent / "koblitz-polynomial-w-pair-20260925" / "karatsuba_circuit.py",
            "circuit_sat.py": ROOT.parent / "koblitz-s5-invariant-20260924" / "circuit_sat.py",
            "cryptominisat5": SOLVER}


def freeze():
    target, columns, branches = inputs()
    assert SOLVER.is_file()
    record = {"status": "FROZEN_BEFORE_N41_SINGLE_BRANCH_CONTROL_AND_PUBLIC_QUERY",
              "candidate_id": None, "curve_id": "EC1N41Ckb1h023d9a38bbf7",
              "field": "GF(2)[t]/(t^41+t^3+1)", "target_q": list(target),
              "target_raw_lift_indices": [0, 1],
              "target_raw_reciprocal_coordinates": branches,
              "source_dimension": 6, "rotations": [0, 5, 10, 15, 20, 25],
              "factor_base_B": 384, "folded_columns_K": 26,
              "workers": 1, "construction_cap_seconds": CONSTRUCTION_CAP,
              "solver_cap_seconds": SOLVER_CAP, "rss_cap_bytes": RSS_CAP,
              "solver_flags": ["--threads=1", "--xor=0", "--printsol=1",
                               "--random=20261011", "--maxtime=60"],
              "source_sha256": {name: sha(path) for name, path in sources().items()},
              "source_mask_counts": [len(table) for table in columns]}
    save(HERE / "protocol.json", record)
    print(json.dumps({"status": record["status"], "target": target}))


def checked_protocol():
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["source_sha256"] == {name: sha(path) for name, path in sources().items()}
    assert protocol["status"] == "FROZEN_BEFORE_N41_SINGLE_BRANCH_CONTROL_AND_PUBLIC_QUERY"
    return protocol


def build():
    target, columns, branches = inputs()
    circuit = KaratsubaCircuit(41, [0, 3])
    start = time.monotonic()
    meta = method.build(circuit, method.Field(), columns, branches)
    elapsed = time.monotonic() - start
    assert target == tuple(json.loads((HERE / "protocol.json").read_text())["target_q"])
    return circuit, meta, elapsed


def point_add(field, left, right):
    if left is None:
        return right
    if right is None:
        return left
    x1, y1 = left
    x2, y2 = right
    if x1 == x2:
        if y1 ^ y2 == x1:
            return None
        assert left == right and x1
        slope = x1 ^ field.mul(y1, field.inv(x1))
        x3 = field.square(slope) ^ slope
        y3 = field.square(x1) ^ field.mul(slope ^ 1, x3)
    else:
        slope = field.mul(y1 ^ y2, field.inv(x1 ^ x2))
        x3 = field.square(slope) ^ slope ^ x1 ^ x2
        y3 = field.mul(slope, x1 ^ x3) ^ x3 ^ y1
    return x3, y3


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


def profile(circuit, meta, construction_seconds):
    return {"variables": circuit.next_var - 1, "and_gates": circuit.and_count,
            "clauses": len(circuit.clauses), "native_xor_rows": len(circuit.xors),
            "quartic_field_multiplications": meta["quartic_field_multiplications"],
            "quartic_field_squares": meta["quartic_field_squares"],
            "column_and_order_forbids": meta["column_and_order_forbids"],
            "construction_seconds_exploratory": construction_seconds,
            "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}


def control():
    protocol = checked_protocol()
    circuit, meta, elapsed = build()
    frozen = json.loads(KNOWN_BLOCKS.read_text())
    audit = json.loads(KNOWN_BRANCHES.read_text())
    assert frozen["raw_preimage_index"] == 1
    assert audit["target"] == protocol["target_q"]
    field = method.Field()
    points = [tuple(row["point"]) for row in frozen["four_atom_blocks"]]
    joined = point_add(field, points[0], points[1])
    assert joined is not None and joined[0]
    assert point_add(field, joined, points[2]) == tuple(frozen["raw_sum"])
    joined_z = field.inv(joined[0])
    initial = {}
    def bind(wires, value):
        initial.update({wire: value >> index & 1 for index, wire in enumerate(wires)})
    for wires, value in zip(meta["masks"], frozen["masks"]):
        bind(wires, value)
    for wires, row in zip(meta["branch_w"], audit["blocks"]):
        bind(wires, row["existential_branch_witness"])
    bind(meta["intermediate"], joined_z)
    initial[meta["target_flag"]] = 1
    assert len(initial) == len(meta["primary_variables"])
    values = complete_assignment(circuit, initial)
    for wires, block in zip(meta["output_z"], frozen["four_atom_blocks"]):
        decoded = sum((1 if wire == -1 else 0 if wire == 0 else values[wire]) << bit
                      for bit, wire in enumerate(wires))
        assert decoded == block["z_h_reciprocal_x"]
    check = check_assignment(circuit, values)
    record = {"status": "PASS_FULL_N41_PUBLIC_WITNESS_ASSIGNMENT",
              "target": protocol["target_q"], "known_masks": frozen["masks"],
              "raw_lift_index": 1, "joined_reciprocal": joined_z,
              "formula": profile(circuit, meta, elapsed), "assignment_check": check,
              "source_sha256": {"protocol.json": sha(HERE / "protocol.json")}}
    save(HERE / "control_result.json", record)
    print(json.dumps({"status": record["status"], "formula": record["formula"]}))


def query():
    protocol = checked_protocol()
    control_record = json.loads((HERE / "control_result.json").read_text())
    assert control_record["status"] == "PASS_FULL_N41_PUBLIC_WITNESS_ASSIGNMENT"
    start = time.monotonic()
    circuit, meta, elapsed = build()
    if elapsed > CONSTRUCTION_CAP or resource.getrusage(resource.RUSAGE_SELF).ru_maxrss > RSS_CAP:
        record = {"status": "RESOURCE_GATE_EXCEEDED", "target": protocol["target_q"],
                  "formula": profile(circuit, meta, elapsed), "solver_started": False}
        save(HERE / "query_result.json", record)
        print(json.dumps(record, sort_keys=True))
        return
    with tempfile.NamedTemporaryFile(prefix="n41_single_branch_", suffix=".xcnf",
                                     dir="/private/tmp", delete=False) as handle:
        formula = Path(handle.name)
    try:
        circuit.write(formula)
        formula_hash = sha(formula)
        formula_bytes = formula.stat().st_size
        formula_profile = profile(circuit, meta, elapsed)
        del circuit
        solver_start = time.monotonic()
        with tempfile.NamedTemporaryFile(prefix="n41_single_branch_stdout_", dir="/private/tmp") as out, \
             tempfile.NamedTemporaryFile(prefix="n41_single_branch_stderr_", dir="/private/tmp") as err:
            process = subprocess.Popen([str(SOLVER), *protocol["solver_flags"], str(formula)],
                                       stdout=out, stderr=err)
            child = psutil.Process(process.pid)
            parent = psutil.Process()
            timed_out = False
            rss_exceeded = False
            peak_combined_rss = 0
            while process.poll() is None:
                try:
                    combined = child.memory_info().rss + parent.memory_info().rss
                except psutil.NoSuchProcess:
                    combined = parent.memory_info().rss
                peak_combined_rss = max(peak_combined_rss, combined)
                if combined > RSS_CAP:
                    rss_exceeded = True
                    process.kill()
                    break
                if time.monotonic() - solver_start > SOLVER_CAP + 5:
                    timed_out = True
                    process.kill()
                    break
                time.sleep(0.1)
            returncode = process.wait()
            out.flush()
            err.flush()
            stdout = Path(out.name).read_text(errors="replace")
            stderr = Path(err.name).read_text(errors="replace")
        solver_seconds = time.monotonic() - solver_start
        full_seconds = time.monotonic() - start
        status = ("RESOURCE_GATE_EXCEEDED" if rss_exceeded else
                  "SAT_PENDING_GROUP_REPLAY" if "s SATISFIABLE" in stdout else
                  "BOUNDED_UNKNOWN" if timed_out or "s INDETERMINATE" in stdout else
                  "UNSAT" if "s UNSATISFIABLE" in stdout else "BOUNDED_UNKNOWN")
        model_primary = None
        if status == "SAT_PENDING_GROUP_REPLAY":
            positive = set()
            negative = set()
            for row in stdout.splitlines():
                if not row.startswith("v "):
                    continue
                for token in row.split()[1:]:
                    literal = int(token)
                    if literal > 0:
                        positive.add(literal)
                    elif literal < 0:
                        negative.add(-literal)
            primary = set(meta["primary_variables"])
            if len(primary & (positive | negative)) != len(primary) or positive & negative:
                status = "INCOMPLETE_SAT_MODEL"
            else:
                model_primary = {str(wire): int(wire in positive)
                                 for wire in meta["primary_variables"]}
                save(HERE / "model_primary.json", model_primary)
                def decode(wires):
                    return sum(int(wire in positive) << index
                               for index, wire in enumerate(wires))
                save(HERE / "model_decoded.json", {
                    "target": protocol["target_q"],
                    "masks": [decode(row) for row in meta["masks"]],
                    "block_reciprocals": [decode(row) for row in meta["output_z"]],
                    "branch_w": [decode(row) for row in meta["branch_w"]],
                    "intermediate_reciprocal": decode(meta["intermediate"]),
                    "raw_lift_index": int(meta["target_flag"] in positive),
                    "formula_sha256": formula_hash})
        with gzip.open(HERE / "solver.stdout.gz", "wb", compresslevel=6) as stream:
            stream.write(stdout.encode())
        with gzip.open(HERE / "solver.stderr.gz", "wb", compresslevel=6) as stream:
            stream.write(stderr.encode())
        record = {"status": status, "target": protocol["target_q"],
                  "formula": {**formula_profile,
                              "bytes": formula_bytes, "sha256": formula_hash},
                  "phase_seconds": {"construction": elapsed,
                                    "write_and_hash": solver_start - start - elapsed,
                                    "solver": solver_seconds,
                                    "total": full_seconds},
                  "solver_started": True, "solver_returncode": returncode,
                  "solver_timed_out": timed_out,
                  "solver_rss_exceeded": rss_exceeded,
                  "peak_combined_rss_bytes": peak_combined_rss,
                  "primary_model_saved": model_primary is not None,
                  "stdout_sha256": hashlib.sha256(stdout.encode()).hexdigest(),
                  "stderr_sha256": hashlib.sha256(stderr.encode()).hexdigest(),
                  "stdout_gzip_sha256": sha(HERE / "solver.stdout.gz"),
                  "stderr_gzip_sha256": sha(HERE / "solver.stderr.gz"),
                  "source_sha256": {"protocol.json": sha(HERE / "protocol.json")}}
        save(HERE / "query_result.json", record)
        print(json.dumps({"status": status, "phases": record["phase_seconds"],
                          "formula_bytes": formula_bytes}, sort_keys=True))
    finally:
        formula.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "control", "query"))
    mode = parser.parse_args().mode
    {"freeze": freeze, "control": control, "query": query}[mode]()
