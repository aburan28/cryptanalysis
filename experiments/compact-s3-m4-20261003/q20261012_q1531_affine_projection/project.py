#!/usr/bin/env python3
"""Eliminate ANF variables that occur only linearly, preserving every model."""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
Q1528 = HERE.parent / "q20261012_q1528_gate_elimination"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(label: str):
    raw = gzip.decompress((Q1528 / "formulas" / f"{label}.anf.gz").read_bytes())
    return parse_data(raw)


def parse_data(raw: bytes):
    lines = raw.decode().splitlines()
    header = lines.pop(0).split()
    assert header[:2] == ["p", "cnf"] and len(lines) == int(header[3])
    n = int(header[2])
    rows = []
    nonlinear_vars = set()
    for line in lines:
        tokens = line.split()
        assert tokens[0] == "x" and tokens[-1] == "0"
        tokens = tokens[1:-1]
        bits, rhs, monomials = 0, 1, []
        i = 0
        while i < len(tokens):
            token = tokens[i]
            if token == "T":
                rhs ^= 1
                i += 1
            elif token.startswith("."):
                degree = int(token[1:])
                assert degree >= 2 and i + degree < len(tokens)
                terms = tuple(tokens[i:i + degree + 1])
                assert all(0 < abs(int(v)) <= n for v in terms[1:])
                nonlinear_vars.update(abs(int(v)) for v in terms[1:])
                monomials.append(terms)
                i += degree + 1
            else:
                var = int(token)
                assert 0 < abs(var) <= n
                bits ^= 1 << abs(var)
                rhs ^= var < 0
                i += 1
        rows.append((bits, rhs, tuple(monomials)))
    return n, rows, nonlinear_vars, raw


def bit_vars(bits: int):
    while bits:
        least = bits & -bits
        yield least.bit_length() - 1
        bits ^= least


def project(n: int, rows: list, nonlinear_vars: set):
    pure = set(range(1, n + 1)) - nonlinear_vars
    pure_mask = sum(1 << v for v in pure)
    basis = []
    residual = []
    for bits, rhs, monomials in rows:
        if monomials:
            continue
        for pivot, pivot_bits, pivot_rhs in basis:
            if bits >> pivot & 1:
                bits ^= pivot_bits
                rhs ^= pivot_rhs
        remaining = bits & pure_mask
        if remaining:
            pivot = (remaining & -remaining).bit_length() - 1
            basis.append((pivot, bits, rhs))
        else:
            residual.append((bits, rhs))
    pivots = {item[0] for item in basis}
    projected = []
    for bits, rhs, monomials in rows:
        for pivot, pivot_bits, pivot_rhs in basis:
            if bits >> pivot & 1:
                bits ^= pivot_bits
                rhs ^= pivot_rhs
        assert not any(bits >> pivot & 1 for pivot in pivots)
        if not bits and not monomials:
            assert not rhs, "inconsistent linear system"
            continue
        projected.append((bits, rhs, monomials))
    live = set()
    for bits, _, monomials in projected:
        live.update(bit_vars(bits))
        for terms in monomials:
            live.update(abs(int(v)) for v in terms[1:])
    live = sorted(live)
    assert not pivots.intersection(live)
    assert len(live) + len(basis) <= n
    mapping = {old: new for new, old in enumerate(live, 1)}
    output = [f"p cnf {len(live)} {len(projected)}\n"]
    for bits, rhs, monomials in projected:
        terms = []
        for item in monomials:
            degree = item[0]
            converted = [degree]
            for lit in item[1:]:
                value = int(lit)
                converted.append(str(mapping[abs(value)] * (1 if value > 0 else -1)))
            terms.extend(converted)
        terms.extend(str(mapping[v]) for v in bit_vars(bits))
        if not rhs:
            terms.append("T")
        output.append("x " + " ".join(terms) + " 0\n")
    data = "".join(output).encode()
    info = {"original_variables": n, "variables": len(live),
            "original_equations": len(rows), "equations": len(projected),
            "pure_linear_variables": len(pure), "linear_rows":
            sum(not mons for _, _, mons in rows),
            "eliminated_pivots": len(basis),
            "residual_linear_rows": len(residual),
            "free_variables_omitted": n - len(live) - len(basis),
            "anf_sha256": sha(data)}
    return data, live, basis, info


def lift_model(reduced: str, live: list, basis: list, n: int) -> str:
    assert len(reduced) == len(live) and set(reduced) <= {"0", "1"}
    values = {i: False for i in range(1, n + 1)}
    values.update({old: reduced[new - 1] == "1" for new, old in enumerate(live, 1)})
    for pivot, bits, rhs in reversed(basis):
        values[pivot] = bool(rhs ^ sum(values[v] for v in bit_vars(bits ^ (1 << pivot))) % 2)
    return "".join("1" if values[i] else "0" for i in range(1, n + 1))


def evaluate(rows: list, model: str) -> bool:
    values = {i: model[i - 1] == "1" for i in range(1, len(model) + 1)}
    for bits, rhs, monomials in rows:
        parity = sum(values[v] for v in bit_vars(bits)) % 2
        for terms in monomials:
            product = all(values[abs(int(lit))] == (int(lit) > 0)
                          for lit in terms[1:])
            parity ^= product
        if parity != rhs:
            return False
    return True


def write_formula(label: str) -> dict:
    n, rows, nonlinear, raw = load(label)
    data, live, basis, info = project(n, rows, nonlinear)
    folder = HERE / "formulas"
    folder.mkdir(exist_ok=True)
    plain = folder / f"{label}.anf"
    plain.write_bytes(data)
    with (folder / f"{label}.anf.gz").open("wb") as stream:
        with gzip.GzipFile(fileobj=stream, mode="wb", filename="", mtime=0) as packed:
            packed.write(data)
    basis_record = {"live": live, "basis": basis}
    (folder / f"{label}.basis.json").write_text(
        json.dumps(basis_record, separators=(",", ":")) + "\n")
    receipt = {"label": label, "source_anf_sha256": sha(raw),
               "source_gzip_sha256": sha((Q1528 / "formulas" / f"{label}.anf.gz").read_bytes()),
               "gzip_sha256": sha((folder / f"{label}.anf.gz").read_bytes()),
               "basis_sha256": sha((folder / f"{label}.basis.json").read_bytes()),
               **info}
    (folder / f"{label}.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


if __name__ == "__main__":
    import sys
    for label in sys.argv[1:]:
        print(json.dumps(write_formula(label), sort_keys=True), flush=True)
