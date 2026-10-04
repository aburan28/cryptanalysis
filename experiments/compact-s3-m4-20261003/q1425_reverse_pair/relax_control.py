"""Free the two partner leaves in Q1420's archived full-lock control."""

from __future__ import annotations


def partner_variables(variable_map: bytes, n: int) -> set[int]:
    tokens = variable_map.decode("ascii").split()
    assert tokens[0] == "Q1420MAP1" and int(tokens[1]) == n
    assert len(tokens) >= 3 + 6 * n + 2
    rows = [list(map(int, tokens[3 + j * n:3 + (j + 1) * n]))
            for j in range(6)]
    assert all(len(row) == n for row in rows)
    result = set(rows[1] + rows[3])
    assert len(result) == 2 * n
    return result


def relax_cnf(raw: bytes, variable_map: bytes, n: int) -> tuple[bytes, int]:
    partner = partner_variables(variable_map, n)
    lines = raw.decode("ascii").splitlines()
    header = lines[0].split()
    assert header[:2] == ["p", "cnf"] and len(header) == 4
    variables, clauses = int(header[2]), int(header[3])
    assert len(lines) == clauses + 1
    kept, removed = [], 0
    for line in lines[1:]:
        literals = [int(token) for token in line.split()]
        assert literals and literals[-1] == 0
        if len(literals) == 2 and abs(literals[0]) in partner:
            removed += 1
        else:
            kept.append(line)
    assert removed == 2 * n
    result = (f"p cnf {variables} {clauses - removed}\n" +
              "".join(line + "\n" for line in kept)).encode("ascii")
    return result, removed


def relax_formula(formula, leaf_variables, n: int) -> int:
    partner = set(leaf_variables[1] + leaf_variables[3])
    assert len(partner) == 2 * n
    clauses, removed = [], 0
    for clause in formula.clauses:
        if len(clause) == 1 and abs(clause[0]) in partner:
            removed += 1
        else:
            clauses.append(clause)
    assert removed == 2 * n
    formula.clauses = clauses
    return removed


def serialize_cnf(variables: int, clauses) -> bytes:
    return (f"p cnf {variables} {len(clauses)}\n" +
            "".join(" ".join(map(str, clause)) + " 0\n"
                    for clause in clauses)).encode("ascii")
