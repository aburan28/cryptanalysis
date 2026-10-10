#!/usr/bin/env python3
"""Independent full-XCNF check of the saved public-point assignment."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def model(path):
    status = None
    values = {}
    for line in Path(path).read_text().splitlines():
        if line.startswith("s "):
            status = line[2:].strip()
        elif line.startswith("v "):
            for token in line[2:].split():
                lit = int(token)
                if lit:
                    values[abs(lit)] = lit > 0
    if status != "SATISFIABLE":
        raise ValueError("saved control model is not SAT")
    return values


def main():
    output = HERE / "formula_audit.json"
    if output.exists():
        raise FileExistsError(output)
    formula = HERE / "public/system.xcnf"
    stdout = HERE / "control/solver.stdout.txt"
    assignment = model(stdout)
    with formula.open() as source:
        header = source.readline().split()
        if header[:2] != ["p", "cnf"] or len(header) != 4:
            raise ValueError("bad XCNF header")
        variables, expected = map(int, header[2:])
        if set(assignment) != set(range(1, variables + 1)):
            raise ValueError("assignment does not cover public formula")
        clauses = xors = 0
        for line in source:
            words = line.split()
            if not words or words[0] == "c":
                continue
            is_xor = words[0] == "x"
            if words[-1] != "0":
                raise ValueError("unterminated XCNF record")
            literals = [int(word) for word in words[1 if is_xor else 0:-1]]
            truths = [assignment[abs(lit)] == (lit > 0) for lit in literals]
            if is_xor:
                if sum(truths) % 2 != 1:
                    raise ValueError(f"violated native XOR {xors}")
                xors += 1
            else:
                if not any(truths):
                    raise ValueError(f"violated clause {clauses}")
                clauses += 1
    if clauses + xors != expected:
        raise ValueError("public XCNF record count mismatch")
    result = {"status": "PASS_FULL_PUBLIC_XCNF_ASSIGNMENT",
              "assignment_variables": variables,
              "checked_cnf_clauses": clauses, "checked_native_xor_rows": xors,
              "public_formula_sha256": sha(formula),
              "control_solver_stdout_sha256": sha(stdout),
              "audit_source_sha256": sha(__file__)}
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
