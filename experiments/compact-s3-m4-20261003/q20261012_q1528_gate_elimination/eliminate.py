#!/usr/bin/env python3
"""Inline every shared AND output into exact S3 ANF rows and renumber variables."""
from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "q20261012_q1527_native_gate_anf"
spec = importlib.util.spec_from_file_location("q1527_converter", PARENT / "gate_convert.py")
assert spec and spec.loader
q1527 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q1527)
q1519 = q1527.q1519
q1525 = q1527.q1525
INPUTS = q1527.INPUTS


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def split_gate_clauses(formula):
    by_output = {z: (a, b) for (a, b), z in formula.and_cache.items()}
    retained = []
    removed = 0
    i = 0
    while i < len(formula.clauses):
        row = formula.clauses[i]
        z = -row[0] if len(row) == 2 and row[0] < 0 else None
        pair = by_output.get(z)
        next_rows = formula.clauses[i:i + 3]
        if (pair and len(next_rows) == 3 and len(next_rows[1]) == 2 and
                next_rows[1][0] == -z and
                sorted((row[1], next_rows[1][1])) == list(pair) and
                next_rows[2] == [z, -row[1], -next_rows[1][1]]):
            removed += 1
            i += 3
        else:
            retained.append(row)
            i += 1
    assert removed == len(by_output)
    assert not any(abs(lit) in by_output for row in retained for lit in row)
    assert not any(abs(lit) in by_output for pair in formula.and_cache for lit in pair)
    return retained, by_output


def transform(formula):
    retained, gates = split_gate_clauses(formula)
    live = {abs(lit) for row in retained for lit in row}
    live.update(abs(lit) for pair in formula.and_cache for lit in pair)
    live.update(v for row, _ in formula.xors for v in row if v not in gates)
    assert live.isdisjoint(gates)
    ordered = sorted(live)
    mapping = {old: new for new, old in enumerate(ordered, 1)}
    assert len(live) + len(gates) == formula.variables

    def map_lit(lit: int) -> int:
        return mapping[abs(lit)] if lit > 0 else -mapping[-lit]

    lines = []
    for row in retained:
        lines.append(q1525.equation(False, [map_lit(lit) for lit in row]))
    monomial_occurrences = 0
    max_terms = 0
    for row, rhs in formula.xors:
        terms = []
        for v in row:
            if v in gates:
                a, b = gates[v]
                terms.extend((".2", str(map_lit(a)), str(map_lit(b))))
                monomial_occurrences += 1
            else:
                terms.append(str(mapping[v]))
        max_terms = max(max_terms, len(row))
        if not rhs:
            terms.append("T")
        lines.append("x " + " ".join(terms) + " 0\n")
    equations = len(lines)
    data = (f"p cnf {len(live)} {equations}\n" + "".join(lines)).encode()
    packed_map = json.dumps(ordered, separators=(",", ":")).encode()
    counts = {"original_variables": formula.variables,
              "variables": len(live), "eliminated_gate_variables": len(gates),
              "retained_cnf_clauses": len(retained), "xor_rows": len(formula.xors),
              "equations": equations,
              "original_xcnf_rows": len(formula.clauses) + len(formula.xors),
              "quadratic_monomial_occurrences": monomial_occurrences,
              "max_original_xor_row_terms": max_terms,
              "live_variable_map_sha256": sha_bytes(packed_map)}
    return data, counts, mapping, gates


def convert(label: str) -> dict:
    assert label in INPUTS
    formula, meta, source = q1527.source_formula(label)
    data, counts, _, _ = transform(formula)
    folder = HERE / "formulas"
    folder.mkdir(exist_ok=True)
    path = folder / f"{label}.anf.gz"
    assert not path.exists()
    with path.open("wb") as stream:
        with gzip.GzipFile(fileobj=stream, mode="wb", filename="", mtime=0) as packed:
            packed.write(data)
    receipt = {"label": label, "n": meta["n"], **counts,
               "source_xcnf_sha256": q1525.sha(source),
               "anf_sha256": sha_bytes(data), "gzip_sha256": q1525.sha(path)}
    (folder / f"{label}.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


if __name__ == "__main__":
    for name in sys.argv[1:]:
        print(json.dumps(convert(name), sort_keys=True), flush=True)
