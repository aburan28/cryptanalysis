"""Exact ternary-XOR XCNF to ordinary CNF conversion for the frozen gate."""
from __future__ import annotations

import hashlib


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def xor3_clauses(literals: tuple[int, int, int]) -> list[tuple[int, int, int]]:
    clauses = []
    for assignment in range(8):
        if assignment.bit_count() % 2 == 0:
            clauses.append(tuple(literal if not assignment & (1 << index)
                                 else -literal
                                 for index, literal in enumerate(literals)))
    return clauses


def check_xor3_truth_table() -> None:
    for signs in range(8):
        literals = tuple((-1 if signs & (1 << index) else 1) * (index + 1)
                         for index in range(3))
        clauses = xor3_clauses(literals)
        for values in range(8):
            def true(literal: int) -> bool:
                return bool(values & (1 << (abs(literal) - 1))) == (literal > 0)

            expected = sum(true(literal) for literal in literals) % 2 == 1
            actual = all(any(true(literal) for literal in clause)
                         for clause in clauses)
            assert expected == actual, (literals, values)


def convert(raw: bytes, units: bytes = b"") -> tuple[bytes, dict]:
    check_xor3_truth_table()
    lines = raw.splitlines()
    header = lines[0].split()
    if len(header) != 4 or header[:2] != [b"p", b"cnf"]:
        raise ValueError("XCNF header differs")
    variables, declared = map(int, header[2:])
    if variables < 1 or declared < 1:
        raise ValueError("empty XCNF")
    ordinary: list[bytes] = []
    converted: list[bytes] = []
    xors = 0
    for line in lines[1:]:
        if not line or line.startswith(b"c"):
            continue
        native = line.startswith(b"x")
        tokens = (line[1:] if native else line).split()
        literals = tuple(map(int, tokens))
        if not literals or literals[-1] != 0 or any(
                literal == 0 or abs(literal) > variables
                for literal in literals[:-1]):
            raise ValueError("malformed XCNF constraint")
        if native:
            if len(literals) != 4:
                raise ValueError("this frozen gate requires ternary XOR")
            for clause in xor3_clauses(literals[:3]):
                converted.append((" ".join(map(str, clause)) + " 0\n").encode())
            xors += 1
        else:
            ordinary.append(line + b"\n")
    if len(ordinary) + xors != declared:
        raise ValueError("XCNF header count differs")
    unit_lines = units.splitlines()
    for line in unit_lines:
        tokens = tuple(map(int, line.split()))
        if len(tokens) != 2 or tokens[1] != 0 or not 0 < abs(tokens[0]) <= variables:
            raise ValueError("malformed frozen unit delta")
        ordinary.append(line + b"\n")
    clause_count = len(ordinary) + len(converted)
    output = (f"p cnf {variables} {clause_count}\n".encode()
              + b"".join(ordinary) + b"".join(converted))
    assert output.count(b"\n") == clause_count + 1
    return output, {
        "variables": variables,
        "original_constraints": declared,
        "original_ordinary_clauses": len(ordinary) - len(unit_lines),
        "native_xors": xors,
        "added_unit_clauses": len(unit_lines),
        "cnf_clauses": clause_count,
        "cnf_sha256": sha(output),
        "cnf_bytes": len(output),
        "xcnf_sha256": sha(raw),
        "unit_sha256": sha(units) if units else None,
    }


def check_model(raw: bytes, units: bytes, output: bytes) -> dict:
    head = raw.splitlines()[0].split()
    variables = int(head[2])
    values: dict[int, bool] = {}
    for line in output.splitlines():
        if not line.startswith(b"v "):
            continue
        for token in line[2:].split():
            literal = int(token)
            if not literal:
                continue
            index = abs(literal)
            if index in values and values[index] != (literal > 0):
                raise ValueError("conflicting model assignment")
            values[index] = literal > 0
    if len(values) != variables:
        raise ValueError("model does not assign every original variable")

    def true(literal: int) -> bool:
        return values[abs(literal)] == (literal > 0)

    clauses = xors = 0
    for line in raw.splitlines()[1:] + units.splitlines():
        if not line or line.startswith(b"c"):
            continue
        native = line.startswith(b"x")
        literals = tuple(map(int, (line[1:] if native else line).split()))[:-1]
        if native:
            if sum(true(literal) for literal in literals) % 2 != 1:
                raise ValueError("model fails native XOR")
            xors += 1
        else:
            if not any(true(literal) for literal in literals):
                raise ValueError("model fails ordinary clause")
            clauses += 1
    return {"ordinary_clauses_replayed": clauses,
            "native_xors_replayed": xors,
            "variables_assigned": len(values)}
