#!/usr/bin/env python3
"""Replace exact Tseitin AND triples with native quadratic ANF equations."""
from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "q20261012_fixed_pair_s3_handoff"
Q1525 = HERE.parent / "q20261012_q1525_anf_solver"

spec = importlib.util.spec_from_file_location("q1519_gate_source", PARENT / "run.py")
assert spec and spec.loader
q1519 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q1519)

spec2 = importlib.util.spec_from_file_location("q1525_clause_converter", Q1525 / "convert.py")
assert spec2 and spec2.loader
q1525 = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(q1525)

INPUTS = q1525.INPUTS


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_formula(label: str):
    assert label in INPUTS
    source = PARENT / INPUTS[label]
    meta = json.loads((PARENT / INPUTS[label].replace(".xcnf", ".json")).read_text())
    formula, raw, leaves, onb = q1519.build(meta["n"], meta["complement_x_coords"])
    for bits, value in zip(raw, meta["pin_raw"]):
        q1519.pin_bits(formula, bits, value)
    for bits, value in zip(leaves, meta["pin_projected"]):
        q1519.pin_bits(formula, bits, value)
    assert formula.variables == meta["variables"]
    lines = [f"p cnf {formula.variables} {len(formula.clauses) + len(formula.xors)}\n"]
    lines += [" ".join(map(str, row)) + " 0\n" for row in formula.clauses]
    for row, rhs in formula.xors:
        lines.append(("x" if rhs else "x-") + str(row[0]) + " " +
                     " ".join(map(str, row[1:])) + " 0\n")
    regenerated = "".join(lines).encode()
    assert sha_bytes(regenerated) == q1525.sha(source), label
    return formula, meta, source


def gate_equation(z: int, a: int, b: int) -> str:
    # DPLL_ANF interprets each row as XOR=1.  z XOR (a AND b) XOR 1=1.
    return f"x {z} .2 {a} {b} T 0\n"


def transform(formula) -> tuple[bytes, dict]:
    by_output = {z: (a, b) for (a, b), z in formula.and_cache.items()}
    assert len(by_output) == len(formula.and_cache)
    lines = []
    gates = clauses = 0
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
            lines.append(gate_equation(z, *pair))
            gates += 1
            i += 3
        else:
            lines.append(q1525.equation(False, formula.clauses[i]))
            clauses += 1
            i += 1
    assert gates == len(formula.and_cache)
    for row, rhs in formula.xors:
        literals = [row[0] if rhs else -row[0], *row[1:]]
        lines.append(q1525.equation(True, literals))
    equations = len(lines)
    data = (f"p cnf {formula.variables} {equations}\n" + "".join(lines)).encode()
    return data, {"variables": formula.variables, "and_gates": gates,
                  "retained_cnf_clauses": clauses, "xor_rows": len(formula.xors),
                  "equations": equations,
                  "source_xcnf_rows": len(formula.clauses) + len(formula.xors),
                  "rows_saved": 2 * gates}


def convert(label: str) -> dict:
    formula, meta, source = source_formula(label)
    data, counts = transform(formula)
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
