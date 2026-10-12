#!/usr/bin/env python3
"""Exhaustively check existential equivalence of short chain clauses."""
from __future__ import annotations
import hashlib
import itertools
import json
from pathlib import Path

from prepare import transform

HERE = Path(__file__).resolve().parent


def clause_true(clause: list[int], assignment: dict[int, bool]) -> bool:
    return any(assignment[abs(lit)] == (lit > 0) for lit in clause)


def main() -> None:
    cases = []
    for width in range(5, 11):
        original = [i if i % 2 else -i for i in range(1, width + 1)]
        raw = f"p cnf {width} 1\n".encode() + (" ".join(map(str, [*original, 0])) + "\n").encode()
        derived, _, stats = transform(raw)
        clauses = [[int(token) for token in line.split()[:-1]]
                   for line in derived.splitlines()[1:]]
        tested = 0
        for original_bits in itertools.product((False, True), repeat=width):
            initial = dict(enumerate(original_bits, 1))
            expected = clause_true(original, initial)
            found = False
            aux_count = stats["auxiliary_variables"]
            for auxiliary_bits in itertools.product((False, True), repeat=aux_count):
                assignment = dict(initial)
                assignment.update({width + i + 1: bit for i, bit in
                                   enumerate(auxiliary_bits)})
                found |= all(clause_true(clause, assignment) for clause in clauses)
                tested += 1
            assert found == expected, (width, initial)
        cases.append({"original_width": width,
                      "auxiliary_variables": stats["auxiliary_variables"],
                      "derived_clauses": len(clauses),
                      "full_assignment_checks": tested})
    result = {"proposal_id": "Q1459", "status": "PASS",
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "transform_source_sha256": hashlib.sha256((HERE / "prepare.py").read_bytes()).hexdigest(),
              "cases": cases}
    (HERE / "equivalence_check.json").write_text(json.dumps(result, indent=2,
                                                             sort_keys=True) + "\n")
    print(json.dumps({"cases": len(cases),
                      "assignments": sum(item["full_assignment_checks"]
                                         for item in cases)}))


if __name__ == "__main__":
    main()
