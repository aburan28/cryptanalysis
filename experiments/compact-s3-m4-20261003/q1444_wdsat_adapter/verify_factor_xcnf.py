#!/usr/bin/env python3
"""Independently audit the shared-prefix OR-gate XCNF conversion.

The audit reads both formulas.  It recognizes only three-clause gate
definitions, recursively expands each gate, and proves that each converted
long clause is the corresponding source clause.  No SAT solver or Sage is
needed for this Boolean identity check.
"""

import argparse
import gzip
import json
from pathlib import Path


def read_formula(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="ascii") as stream:
        lines = [line.strip() for line in stream if line.strip()]
    header = next(line for line in lines if line.startswith("p "))
    _, kind, nvars, nrows = header.split()
    assert kind == "cnf"
    rows = [line for line in lines if not line.startswith(("c", "p"))]
    assert len(rows) == int(nrows)
    return int(nvars), rows


def cnf_lits(row):
    fields = tuple(map(int, row.split()))
    assert fields[-1] == 0 and 0 not in fields[:-1]
    return fields[:-1]


def xor_lits(row):
    assert row.startswith("x")
    fields = row.split()
    if fields[0] == "x":
        fields = fields[1:]
    else:
        fields[0] = fields[0][1:]
    values = tuple(map(int, fields))
    assert values[-1] == 0 and 0 not in values[:-1]
    return values[:-1]


def read_cms_model(path, oldvars):
    values = {}
    for line in path.read_text(encoding="ascii").splitlines():
        if not line.startswith("v "):
            continue
        for token in line.split()[1:]:
            literal = int(token)
            if literal:
                values[abs(literal)] = literal > 0
    assert set(values) == set(range(1, oldvars + 1))
    return values


def literal_true(literal, values):
    return values[abs(literal)] == (literal > 0)


def count_violations(rows, values):
    cnf_bad = xor_bad = 0
    for row in rows:
        if row.startswith("x"):
            xor_bad += (sum(literal_true(lit, values)
                            for lit in xor_lits(row)) % 2 != 1)
        else:
            cnf_bad += not any(literal_true(lit, values)
                               for lit in cnf_lits(row))
    return int(cnf_bad), int(xor_bad)


def audit(source_path, converted_path, control_model_path=None):
    oldvars, original = read_formula(source_path)
    newvars, converted = read_formula(converted_path)
    assert newvars >= oldvars
    gate_children = {}
    j = 0
    changed = 0
    xor_rows = 0
    max_clause_size = 0
    for source_row in original:
        if source_row.startswith("x"):
            xor_rows += 1
            assert xor_lits(source_row) == xor_lits(converted[j])
            j += 1
            continue
        source_lits = cnf_lits(source_row)
        if len(source_lits) <= 4:
            assert source_lits == cnf_lits(converted[j])
            max_clause_size = max(max_clause_size, len(source_lits))
            j += 1
            continue

        changed += 1
        while j < len(converted):
            row = cnf_lits(converted[j])
            if len(row) != 3 or row[0] >= -oldvars:
                break
            g, a, b = -row[0], row[1], row[2]
            assert oldvars < g <= newvars
            assert g not in gate_children
            assert cnf_lits(converted[j + 1]) == (g, -a)
            assert cnf_lits(converted[j + 2]) == (g, -b)
            assert all(abs(t) < g for t in (a, b) if abs(t) > oldvars)
            gate_children[g] = (a, b)
            j += 3
        g, last = cnf_lits(converted[j])
        assert oldvars < g <= newvars
        assert last == source_lits[-1]
        stack = [g]
        expanded = []
        while stack:
            lit = stack.pop()
            if abs(lit) <= oldvars:
                expanded.append(lit)
            else:
                assert lit > 0 and lit in gate_children
                a, b = gate_children[lit]
                stack.extend((b, a))
        assert tuple(expanded) == source_lits[:-1]
        max_clause_size = max(max_clause_size, 3)
        j += 1
    assert j == len(converted)
    assert set(gate_children) == set(range(oldvars + 1, newvars + 1))
    assert max_clause_size <= 4
    result = {
        "status": "pass",
        "source_variables": oldvars,
        "converted_variables": newvars,
        "source_rows": len(original),
        "converted_rows": len(converted),
        "long_clauses_converted": changed,
        "shared_or_gates": len(gate_children),
        "xor_rows_preserved": xor_rows,
        "converted_max_cnf_clause_size": max_clause_size,
    }
    if control_model_path is not None:
        values = read_cms_model(control_model_path, oldvars)
        source_bad = count_violations(original, values)
        for g, (a, b) in gate_children.items():
            values[g] = literal_true(a, values) or literal_true(b, values)
        converted_bad = count_violations(converted, values)
        assert source_bad == converted_bad == (0, 0)
        result["archived_control_model_satisfies_both"] = True
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("converted", type=Path)
    parser.add_argument("--control-model", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.source, args.converted, args.control_model),
                     sort_keys=True))
