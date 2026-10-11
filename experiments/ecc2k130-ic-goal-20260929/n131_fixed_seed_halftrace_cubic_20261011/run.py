"""Exact fixed-seed N131 pair circuit with halftrace-cubic group links.

Run freeze, control, then query. Each mode writes only new files in HERE.
"""

import argparse
import hashlib
import json
import psutil
import resource
import sys
import time
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OLD = ROOT / "n131_fixed_seed_eight_pair_circuit_20261010"
SUPPORT = ROOT / "n131_w16_w18_sixpair_width_gate_20261010" / "support_w18.tsv"
sys.path[:0] = [str(OLD), str(ROOT / "n41_basis_aware_quartic_20261011"),
                str(ROOT.parent / "koblitz-polynomial-w-pair-20260925")]
import fixed_pair_circuit as pair  # noqa: E402
from sparse import Algebra  # noqa: E402
from karatsuba_circuit import KaratsubaCircuit  # noqa: E402

SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
RSS_CAP = 4 * 1024**3
SOLVER_CAP = 600
PARENT_CAP = 615
SOLVER_FLAGS = ["--threads=1", "--maxtime=600", "--zero-exit-status",
                "--verb=1", "--printsol=1"]


class Field:
    n = pair.N
    mul = staticmethod(pair.gf_mul)
    square = staticmethod(pair.gf_square)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_new(path, data):
    with Path(path).open("x") as stream:
        json.dump(data, stream, sort_keys=True, indent=2)
        stream.write("\n")


def source_paths():
    return {"runner": Path(__file__), "pair_circuit": OLD / "fixed_pair_circuit.py",
            "sparse_algebra": ROOT / "n41_basis_aware_quartic_20261011" / "sparse.py",
            "karatsuba": ROOT.parent / "koblitz-polynomial-w-pair-20260925" / "karatsuba_circuit.py",
            "circuit_sat": ROOT.parent / "koblitz-s5-invariant-20260924" / "circuit_sat.py",
            "support": SUPPORT, "derive": OLD / "derive_result.json",
            "chain": OLD / "planted_chain_result.json",
            "target": OLD / "target_preimages.json", "solver": SOLVER.resolve()}


def inverse(value):
    assert value
    result, base, exponent = 1, value, (1 << pair.N) - 2
    while exponent:
        if exponent & 1:
            result = pair.gf_mul(result, base)
        base = pair.gf_square(base)
        exponent >>= 1
    assert pair.gf_mul(value, result) == 1
    return result


def standard_reciprocal(shifted_reciprocal):
    """Convert z=1/(x+1) to a=1/x, on the nonexceptional domain."""
    assert shifted_reciprocal not in (0, 1)
    return pair.gf_mul(shifted_reciprocal, inverse(shifted_reciprocal ^ 1))


def trace(value):
    result = 0
    for _ in range(pair.N):
        result ^= value
        value = pair.gf_square(value)
    assert result in (0, 1)
    return result


def halftrace(value):
    assert trace(value) == 0
    return pair.gf_half_trace(value)


def source_domain():
    columns = {int(mask): int(column) for mask, column in
               (line.split() for line in SUPPORT.read_text().splitlines())}
    codes = pair.valid_codes(columns)
    root, nodes = pair.build_bdd(codes)
    assert len(codes) == 33191 and len(nodes) == 13093
    return codes, root, nodes


def target_record():
    record = json.loads((OLD / "target_preimages.json").read_text())
    assert record["curve_id"] == "EC1N131Ckb1heb5f1998f20b"
    assert record["workload_id"] == "cc09e7eb202a"
    assert len(record["preimages"]) == 4
    return record


def freeze():
    target = target_record()
    codes, root, nodes = source_domain()
    assert root >= 2 and SOLVER.is_file()
    result = {"status": "FROZEN_BEFORE_CONTROL_AND_ORDINARY_QUERY",
              "candidate_id": None, "curve_id": target["curve_id"],
              "field": "GF(2)[t]/(t^131+t^13+t^2+t+1)",
              "curve": "y^2+xy=x^3+1", "workload_id": target["workload_id"],
              "public_target": target["public_target"], "raw_preimage_index": 0,
              "fixed_seed_mask": pair.SEED, "pair_slots": 8,
              "source_rotations": pair.ROTATIONS,
              "source_codes_per_slot": len(codes), "source_bdd_nodes": len(nodes),
              "solver_flags": SOLVER_FLAGS, "solver_cap_seconds": SOLVER_CAP,
              "parent_cap_seconds": PARENT_CAP, "combined_rss_cap_bytes": RSS_CAP,
              "source_sha256": {name: sha(path) for name, path in source_paths().items()}}
    save_new(HERE / "protocol.json", result)
    print(json.dumps({"status": result["status"], "workload_id": result["workload_id"]}))


def checked_protocol():
    record = json.loads((HERE / "protocol.json").read_text())
    assert record["status"] == "FROZEN_BEFORE_CONTROL_AND_ORDINARY_QUERY"
    assert record["source_sha256"] == {name: sha(path) for name, path in source_paths().items()}
    assert record["solver_flags"] == SOLVER_FLAGS
    assert record["combined_rss_cap_bytes"] == RSS_CAP
    return record


def build(target_a, bdd_root, bdd_nodes):
    circuit = KaratsubaCircuit(pair.N, [0, 1, 2, 13])
    algebra = Algebra(circuit, Field(), dense_and_threshold=3000)
    h2 = pair.gf_square(pair.gf_half_trace(pair.coordinate(pair.SEED)))
    coefficient = 1 ^ h2
    selectors, outputs, rotated = [], [], []
    for rotation in pair.ROTATIONS:
        bits = [circuit.variable() for _ in range(17)]
        out = [circuit.variable() for _ in range(pair.N)]
        selectors.append(bits)
        outputs.append(out)
        product = algebra.expression(zip(bits, pair.product_basis()))
        square_term = algebra.expression(
            (wire, pair.gf_mul(coefficient, pair.gf_square(1 << bit)))
            for bit, wire in enumerate(out))
        circuit.require_zero(algebra.add(
            algebra.mul(algebra.from_bits(out), product), square_term,
            algebra.expression(((-1, h2),))).bits())
        circuit.clauses.append(" ".join(map(str, out)) + " 0")
        images = [pair.gf_frobenius(1 << bit, rotation) for bit in range(pair.N)]
        rotated.append(algebra.from_bits(circuit.linear_element(out, images)))

    intermediates = [[circuit.variable() for _ in range(pair.N)] for _ in range(6)]
    branches = [circuit.variable() for _ in range(7)]
    ht_basis, trace_basis = [], []
    for bit in range(pair.N):
        value = pair.gf_square(1 << bit)
        image = 0
        for _ in range((pair.N + 1) // 2):
            image ^= value
            value = pair.gf_square(pair.gf_square(value))
        ht_basis.append(image)
        trace_basis.append(trace(1 << bit))
    running = rotated[0]
    for index in range(1, 8):
        output = (algebra.from_bits(intermediates[index - 1]) if index < 7
                  else algebra.expression(((-1, target_a),)))
        triple = algebra.mul(algebra.mul(running, rotated[index]), output)
        total = algebra.add(running, rotated[index], output)
        ht = circuit.linear_element(total.bits(), ht_basis)
        circuit.require_zero(algebra.add(
            triple, algebra.from_bits(ht),
            algebra.expression(((branches[index - 1], 1),))).bits())
        circuit.require_zero([circuit.xor(
            wire for wire, bit in zip(total.bits(), trace_basis) if bit)])
        if index < 7:
            circuit.clauses.append(" ".join(map(str, intermediates[index - 1])) + " 0")
        running = output

    for bits in selectors:
        literals = {0: 0, 1: -1}
        for node in sorted(bdd_nodes):
            bit, low, high = bdd_nodes[node]
            left, right = literals[low], literals[high]
            literals[node] = circuit.xor((
                left, circuit.and_(bits[bit], circuit.xor((left, right)))))
        circuit.clauses.append(str(literals[bdd_root]) + " 0")
    return circuit, {"selectors": selectors, "outputs": outputs,
                     "intermediates": intermediates, "branches": branches}


def profile(circuit, path, construction_seconds, write_seconds):
    return {"variables": circuit.next_var - 1, "and_gates": circuit.and_count,
            "clauses": len(circuit.clauses), "native_xor_rows": len(circuit.xors),
            "xcnf_bytes": path.stat().st_size, "xcnf_sha256": sha(path),
            "construction_seconds_exploratory": construction_seconds,
            "write_seconds_exploratory": write_seconds,
            "parent_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}


def complete_assignment(circuit, initial):
    definitions = {int(out): ("and", int(a), int(b))
                   for (a, b), out in circuit.and_cache.items()}
    for line in circuit.xors:
        literals = [int(value) for value in line.split()[1:-1]]
        definitions[abs(literals[0])] = ("xor", literals)
    values = [None] * circuit.next_var
    for wire, bit in initial.items():
        values[wire] = bit
    for wire in range(1, circuit.next_var):
        if values[wire] is not None:
            continue
        definition = definitions[wire]
        if definition[0] == "and":
            def value(item):
                return 1 if item == -1 else 0 if item == 0 else values[item]
            values[wire] = value(definition[1]) & value(definition[2])
        else:
            literals = definition[1]
            bit = int(literals[0] > 0)
            for item in literals[1:]:
                bit ^= values[abs(item)] ^ int(item < 0)
            values[wire] = bit
    return values


def check_assignment(circuit, values):
    for line in circuit.clauses:
        literals = [int(value) for value in line.split()[:-1]]
        assert any(values[abs(item)] == int(item > 0) for item in literals)
    for line in circuit.xors:
        literals = [int(value) for value in line.split()[1:-1]]
        assert sum(values[abs(item)] ^ int(item < 0) for item in literals) & 1
    return {"clauses": len(circuit.clauses), "native_xor_rows": len(circuit.xors)}


def control():
    checked_protocol()
    codes, root, nodes = source_domain()
    chain = json.loads((OLD / "planted_chain_result.json").read_text())
    selected = json.loads((OLD / "derive_result.json").read_text())["selected"]
    target_a = standard_reciprocal(chain["raw_target_z"])
    start = time.monotonic()
    circuit, wires = build(target_a, root, nodes)
    constructed = time.monotonic()
    formula = HERE / "control.xcnf"
    assert not formula.exists()
    circuit.write(formula)
    written = time.monotonic()
    initial = {}
    def bind(bits, value):
        initial.update({wire: value >> bit & 1 for bit, wire in enumerate(bits)})
    for item in selected:
        slot = item["slot"]
        code = pair.selector_code(item["masks"][0])
        assert code in codes
        a = standard_reciprocal(item["unrotated_pair_output_z"])
        product = pair.product_from_code(code)
        h2 = pair.gf_square(pair.gf_half_trace(pair.coordinate(pair.SEED)))
        assert pair.gf_mul(1 ^ h2, pair.gf_square(a)) ^ pair.gf_mul(a, product) ^ h2 == 0
        assert pair.gf_frobenius(a, item["rotation"]) == standard_reciprocal(chain["pair_rotated_z"][slot])
        bind(wires["selectors"][slot], code)
        bind(wires["outputs"][slot], a)
    for bits, z in zip(wires["intermediates"], chain["intermediate_z"]):
        bind(bits, standard_reciprocal(z))
    rotated = [standard_reciprocal(z) for z in chain["pair_rotated_z"]]
    middle = [standard_reciprocal(z) for z in chain["intermediate_z"]]
    left, branch_bits = rotated[0], []
    for index in range(1, 8):
        right = middle[index - 1] if index < 7 else target_a
        total = left ^ rotated[index] ^ right
        branch = pair.gf_mul(pair.gf_mul(left, rotated[index]), right) ^ halftrace(pair.gf_square(total))
        assert branch in (0, 1)
        initial[wires["branches"][index - 1]] = branch
        branch_bits.append(branch)
        left = right
    assert len(initial) == 1977
    checked = check_assignment(circuit, complete_assignment(circuit, initial))
    result = {"status": "PASS_FULL_N131_HALFTRACE_CUBIC_CONSTRUCTED_WITNESS",
              "curve_id": "EC1N131Ckb1heb5f1998f20b", "source_codes_per_slot": len(codes),
              "source_bdd_nodes": len(nodes), "source_pair_checks": len(selected),
              "group_link_checks": len(branch_bits), "branch_bits": branch_bits,
              "primary_variables": len(initial), "assignment_check": checked,
              "formula": profile(circuit, formula, constructed - start, written - constructed),
              "protocol_sha256": sha(HERE / "protocol.json")}
    save_new(HERE / "control_result.json", result)
    print(json.dumps({"status": result["status"], "formula": result["formula"]}))


def query():
    protocol = checked_protocol()
    control_result = json.loads((HERE / "control_result.json").read_text())
    assert control_result["status"] == "PASS_FULL_N131_HALFTRACE_CUBIC_CONSTRUCTED_WITNESS"
    target = target_record()
    target_a = standard_reciprocal(target["preimages"][0]["reciprocal_x_z"])
    _, root, nodes = source_domain()
    started = time.monotonic()
    circuit, wires = build(target_a, root, nodes)
    constructed = time.monotonic()
    formula = HERE / "ordinary.xcnf"
    assert not formula.exists()
    circuit.write(formula)
    written = time.monotonic()
    details = profile(circuit, formula, constructed - started, written - constructed)
    assert details["variables"] < 500000 and details["xcnf_bytes"] < 100000000
    del circuit
    outpath, errpath = HERE / "solver.stdout.txt", HERE / "solver.stderr.txt"
    assert not outpath.exists() and not errpath.exists()
    print(json.dumps({"phase": "frozen_ordinary_formula", "target": target["public_target"],
                      "workload_id": target["workload_id"], "formula": details}), flush=True)
    parent = psutil.Process()
    solver_start = time.monotonic()
    peak_combined, stop_reason = 0, None
    with outpath.open("x") as stdout, errpath.open("x") as stderr:
        process = subprocess.Popen([str(SOLVER), *SOLVER_FLAGS, str(formula)],
                                   stdout=stdout, stderr=stderr)
        child = psutil.Process(process.pid)
        while process.poll() is None:
            try:
                combined = parent.memory_info().rss + child.memory_info().rss
            except psutil.NoSuchProcess:
                combined = parent.memory_info().rss
            peak_combined = max(peak_combined, combined)
            if combined > RSS_CAP:
                stop_reason = "RSS_CAP"
                process.kill()
                break
            if time.monotonic() - solver_start > PARENT_CAP:
                stop_reason = "PARENT_TIMEOUT"
                process.kill()
                break
            time.sleep(0.05)
        code = process.wait()
    solver_seconds = time.monotonic() - solver_start
    output = outpath.read_text(errors="replace")
    status = ("BOUNDED_UNKNOWN" if stop_reason else
              "SAT_PENDING_GROUP_REPLAY" if "s SATISFIABLE" in output else
              "UNSAT" if "s UNSATISFIABLE" in output else
              "BOUNDED_UNKNOWN")
    decoded = None
    if status == "SAT_PENDING_GROUP_REPLAY":
        positive = {int(token) for line in output.splitlines() if line.startswith("v ")
                    for token in line.split()[1:] if token.isdigit() and int(token) > 0}
        def decode(bits):
            return sum(int(wire in positive) << bit for bit, wire in enumerate(bits))
        decoded = {"selected_codes": [decode(bits) for bits in wires["selectors"]],
                   "pair_standard_reciprocals": [decode(bits) for bits in wires["outputs"]],
                   "intermediate_standard_reciprocals":
                       [decode(bits) for bits in wires["intermediates"]],
                   "branch_bits": [int(wire in positive) for wire in wires["branches"]],
                   "formula_sha256": details["xcnf_sha256"]}
        save_new(HERE / "decoded_model.json", decoded)
    result = {"status": status, "candidate_id": None,
              "curve_id": protocol["curve_id"], "workload_id": protocol["workload_id"],
              "public_target": protocol["public_target"], "raw_preimage_index": 0,
              "target_standard_reciprocal": target_a,
              "formula": details, "worker_count": 1, "solver_flags": SOLVER_FLAGS,
              "solver_started": True, "solver_exit_code": code,
              "stop_reason": stop_reason, "peak_combined_rss_bytes_sampled": peak_combined,
              "solver_wall_seconds_exploratory": solver_seconds,
              "status_lines": [line for line in output.splitlines() if line.startswith("s ")],
              "restart_rows": sum(line.startswith("c [") for line in output.splitlines()),
              "decoded_model_saved": decoded is not None,
              "stdout_sha256": sha(outpath), "stderr_sha256": sha(errpath),
              "protocol_sha256": sha(HERE / "protocol.json")}
    save_new(HERE / "query_result.json", result)
    print(json.dumps({"status": status, "solver_wall_seconds": solver_seconds,
                      "peak_combined_rss_bytes": peak_combined}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "control", "query"))
    args = parser.parse_args()
    {"freeze": freeze, "control": control, "query": query}[args.mode]()
