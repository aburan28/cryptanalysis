#!/usr/bin/env python3
"""Equivalently encode long XCNF OR clauses with shared prefix OR gates.

This is a scratch adapter for WDSat, whose CNF core handles clauses of
length at most four.  Every new gate is defined by its full three-clause
equivalence, so projecting a satisfying assignment onto old variables
satisfies the original formula.
"""

import argparse
import gzip
from collections import Counter


def translate(src: str, dst: str) -> dict:
    opener = gzip.open if src.endswith(".gz") else open
    with opener(src, "rt", encoding="ascii") as f:
        lines = [line.strip() for line in f if line.strip()]
    header = next(line for line in lines if line.startswith("p "))
    _, kind, old_vars, old_clauses = header.split()
    assert kind == "cnf"
    old_vars, old_clauses = int(old_vars), int(old_clauses)
    body = [line for line in lines if not line.startswith(("c", "p"))]
    assert len(body) == old_clauses
    next_var = old_vars
    gates = {}
    output = []
    lengths_before = Counter()
    xor_count = 0

    def gate(prefix):
        nonlocal next_var
        if len(prefix) == 1:
            return prefix[0]
        key = tuple(prefix)
        if key in gates:
            return gates[key]
        a = gate(key[:-1])
        b = key[-1]
        next_var += 1
        g = next_var
        gates[key] = g
        # g iff (a or b).
        output.extend((f"{-g} {a} {b} 0", f"{g} {-a} 0", f"{g} {-b} 0"))
        return g

    for line in body:
        if line.startswith("x"):
            xor_count += 1
            output.append(line)
            continue
        lits = tuple(map(int, line.split()))
        assert lits[-1] == 0
        lits = lits[:-1]
        lengths_before[len(lits)] += 1
        if len(lits) <= 4:
            output.append(line)
        else:
            g = gate(lits[:-1])
            output.append(f"{g} {lits[-1]} 0")
    with open(dst, "w", encoding="ascii") as f:
        f.write(f"p cnf {next_var} {len(output)}\n")
        for line in output:
            f.write(line + "\n")
    return {
        "old_vars": old_vars,
        "new_vars": next_var,
        "old_clauses": old_clauses,
        "new_clauses": len(output),
        "cnf_count": len(output) - xor_count,
        "xor_count": xor_count,
        "gates": len(gates),
        "old_cnf_lengths": dict(sorted(lengths_before.items())),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("destination")
    args = parser.parse_args()
    print(translate(args.source, args.destination))
