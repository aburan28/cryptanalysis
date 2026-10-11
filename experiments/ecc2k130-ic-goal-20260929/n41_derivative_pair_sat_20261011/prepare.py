"""Freeze derivative formulas and check a complete positive assignment."""

import hashlib
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import circuit


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "experiments/koblitz-polynomial-w-pair-20260925"))
from karatsuba_circuit import KaratsubaCircuit  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def poly_mul(a, b):
    out = 0
    while b:
        if b & 1:
            out ^= a
        a <<= 1
        b >>= 1
    return out


def complete_assignment(c, initial):
    defs = {int(out): ("and", int(a), int(b))
            for (a, b), out in c.and_cache.items()}
    for line in c.xors:
        lits = [int(x) for x in line.split()[1:-1]]
        defs[abs(lits[0])] = ("xor", lits)
    vals = [None] * c.next_var
    for wire, bit in initial.items():
        vals[wire] = int(bit)

    def value(wire):
        return 1 if wire == -1 else 0 if wire == 0 else vals[wire]

    for wire in range(1, c.next_var):
        if vals[wire] is not None:
            continue
        kind, *args = defs[wire]
        if kind == "and":
            vals[wire] = value(args[0]) & value(args[1])
        else:
            lits = args[0]
            bit = int(lits[0] > 0)
            for lit in lits[1:]:
                bit ^= vals[abs(lit)] ^ int(lit < 0)
            vals[wire] = bit
    return vals


def check(c, vals):
    for row in c.clauses:
        assert any(vals[abs(lit)] == int(lit > 0)
                   for lit in map(int, row.split()[:-1]))
    for row in c.xors:
        assert sum(vals[abs(lit)] ^ int(lit < 0)
                   for lit in map(int, row.split()[1:-1])) & 1


def main():
    if (HERE / "protocol.json").exists():
        raise SystemExit("protocol exists")
    fixture_path = HERE.parent / "n41_two_pair_relaxation_20261011/targets.json"
    f = json.loads(fixture_path.read_text())
    positive = f["known_positive"]
    cases = [("positive", positive["target_z"])] + [
        (f"control_{i}", f["controls"][i]["target_z"]) for i in (0, 1)]
    shapes = {}
    for label, target_z in cases:
        start = time.monotonic_ns()
        c = KaratsubaCircuit(41, [0, 3])
        wires = circuit.build(c, circuit.Field(), target_z)
        build_ns = time.monotonic_ns() - start
        if label == "positive":
            initial = {}

            def bind(bits, number):
                for index, wire in enumerate(bits):
                    initial[wire] = (number >> index) & 1

            masks = positive["source_masks"]
            for i in range(2):
                a, b = masks[2*i:2*i+2]
                bind(wires["seed_sum"][i], a ^ b)
                bind(wires["product"][i], poly_mul(a << 1, b << 1) >> 2)
                bind(wires["pair_z"][i], positive["pair_reciprocals"][i])
            assert len(initial) == len(wires["primary_variables"])
            check(c, complete_assignment(c, initial))
        output = HERE / f"{label}.xcnf"
        c.write(output)
        shapes[label] = {"target_z": target_z, "variables": c.next_var-1,
                         "and_gates": c.and_count, "clauses": len(c.clauses),
                         "native_xor_rows": len(c.xors), "bytes": output.stat().st_size,
                         "sha256": sha(output), "construction_ns": build_ns}
    old_result = json.loads((HERE.parent / "n41_two_pair_relaxation_20261011/control_result.json").read_text())
    protocol = {
        "status": "FROZEN_DERIVATIVE_TWO_PAIR_N41",
        "candidate_id": None,
        "curve_id": f["curve_id"],
        "utc": datetime.now(timezone.utc).isoformat(),
        "host": platform.platform(),
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "workers": 1, "solver_cap_seconds": 30, "parent_cap_seconds": 35,
        "rss_cap_bytes": 4 * 1024**3,
        "solver": "/opt/homebrew/bin/cryptominisat5",
        "solver_flags": ["--threads=1", "--xor=0", "--printsol=1",
                         "--random=20261011", "--maxtime=30"],
        "positive_full_assignment": "PASS",
        "prior_halftrace_shape": old_result["formula"],
        "formulas": shapes,
        "sha256": {"circuit": sha(HERE / "circuit.py"),
                   "prepare": sha(HERE / "prepare.py"),
                   "fixture": sha(fixture_path),
                   "karatsuba": sha(ROOT / "experiments/koblitz-polynomial-w-pair-20260925/karatsuba_circuit.py"),
                   "solver": sha("/opt/homebrew/bin/cryptominisat5"),
                   "upstream_circuit": sha(circuit.SOURCE)},
    }
    save(HERE / "protocol.json", protocol)
    print(protocol["status"], shapes)


if __name__ == "__main__":
    main()
