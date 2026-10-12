#!/usr/bin/env python3
"""Losslessly map frozen XCNF S3 circuits to DPLL_ANF equations.

An OR clause is false exactly when every literal is false, so one monomial
over the complemented literals constrained to zero represents the clause.
An extended-DIMACS XOR row constrains the XOR of its signed literals to one;
appending the ANF constant T makes its equation equal to zero.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "q20261012_fixed_pair_s3_handoff"
INPUTS = {
    "n53_pinned": "n53_known_pair_pinned.xcnf",
    "n53_unpinned": "n53_known_complement_unpinned.xcnf",
    "n53_ordinary": "n53_ordinary_seed1513.xcnf",
    "n83_pinned": "n83_planted_pinned.xcnf",
    "n83_selected": "n83_ordinary_selected.xcnf",
    "n83_holdout": "n83_ordinary_holdout.xcnf",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_xcnf(path: Path):
    with path.open() as stream:
        header = stream.readline().split()
        assert header[:2] == ["p", "cnf"] and len(header) == 4
        nvars, nrows = map(int, header[2:])
        rows = []
        for line in stream:
            if not line or line[0] == "c":
                continue
            is_xor = line.startswith("x")
            parts = line[1:].split() if is_xor else line.split()
            assert parts[-1] == "0"
            lits = [int(part) for part in parts[:-1]]
            assert all(lit and abs(lit) <= nvars for lit in lits)
            rows.append((is_xor, lits))
    assert len(rows) == nrows
    return nvars, rows


def equation(is_xor: bool, lits: list[int]) -> str:
    if is_xor:
        return "x " + " ".join(map(str, lits)) + " T 0\n"
    if not lits:
        return "x T 0\n"
    false_lits = [-lit for lit in lits]
    if len(lits) == 1:
        return f"x {false_lits[0]} 0\n"
    return "x ." + str(len(lits)) + " " + " ".join(map(str, false_lits)) + " 0\n"


def convert(label: str) -> dict:
    assert label in INPUTS
    source = PARENT / INPUTS[label]
    nvars, rows = parse_xcnf(source)
    destination = HERE / "formulas" / f"{label}.anf"
    destination.parent.mkdir(exist_ok=True)
    assert not destination.exists()
    with destination.open("w") as out:
        out.write(f"p cnf {nvars} {len(rows)}\n")
        for is_xor, lits in rows:
            out.write(equation(is_xor, lits))
    receipt = {"label": label, "nvars": nvars, "equations": len(rows),
               "cnf_rows": sum(not x for x, _ in rows),
               "xor_rows": sum(x for x, _ in rows),
               "input_sha256": sha(source), "output_sha256": sha(destination),
               "source": str(source), "output": str(destination)}
    (HERE / "formulas" / f"{label}.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


if __name__ == "__main__":
    for name in sys.argv[1:]:
        print(json.dumps(convert(name), sort_keys=True), flush=True)
