#!/usr/bin/env python3
"""Lower frozen S3 XCNFs using exact shared OR prefixes of width three."""
from __future__ import annotations

import collections
import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1460 = PARENT / "q20261011_wdsat_shared_prefix"
Q1463 = PARENT / "q20261011_wdsat_ordinary"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def transform(raw: bytes) -> tuple[bytes, list[tuple[int, tuple[int, ...]]], dict]:
    lines = raw.splitlines()
    header = lines[0].split()
    assert header[:2] == [b"p", b"cnf"] and len(header) == 4
    old_variables, old_rows = map(int, header[2:])
    next_variable = old_variables
    output: list[bytes] = []
    witness_rules: list[tuple[int, tuple[int, ...]]] = []
    prefix_variables: dict[tuple[int, ...], int] = {}
    old_widths = collections.Counter()
    new_widths = collections.Counter()
    xor_rows = 0

    def append_clause(literals: list[int]) -> None:
        assert 1 <= len(literals) <= 3
        output.append(b" ".join(str(value).encode() for value in [*literals, 0]))
        new_widths[len(literals)] += 1

    def intern(prefix: tuple[int, ...], terms: list[int]) -> int:
        nonlocal next_variable
        assert len(terms) == 2
        if prefix in prefix_variables:
            return prefix_variables[prefix]
        next_variable += 1
        variable = next_variable
        prefix_variables[prefix] = variable
        witness_rules.append((variable, prefix))
        append_clause([-variable, *terms])
        for term in terms:
            append_clause([variable, -term])
        return variable

    for line in lines[1:]:
        tokens = line.split()
        assert tokens and tokens[-1] == b"0"
        if tokens[0].startswith(b"x"):
            output.append(line)
            xor_rows += 1
            continue
        literals = [int(value) for value in tokens[:-1]]
        assert literals and all(1 <= abs(value) <= old_variables for value in literals)
        old_widths[len(literals)] += 1
        if len(literals) <= 3:
            output.append(line)
            new_widths[len(literals)] += 1
            continue
        consumed = 2
        previous = intern(tuple(literals[:consumed]), literals[:2])
        remaining = literals[consumed:]
        while len(remaining) > 2:
            consumed += 1
            previous = intern(tuple(literals[:consumed]), [previous, remaining[0]])
            remaining = remaining[1:]
        append_clause([previous, *remaining])
    assert sum(old_widths.values()) + xor_rows == old_rows
    derived = (f"p cnf {next_variable} {len(output)}\n".encode() +
               b"\n".join(output) + b"\n")
    stats = {"original_variables": old_variables, "derived_variables": next_variable,
             "auxiliary_variables": next_variable - old_variables,
             "shared_prefixes": len(prefix_variables),
             "original_rows": old_rows, "derived_rows": len(output),
             "xor_rows": xor_rows,
             "original_cnf_widths": dict(sorted(old_widths.items())),
             "derived_cnf_widths": dict(sorted(new_widths.items()))}
    assert stats["auxiliary_variables"] == stats["shared_prefixes"]
    return derived, witness_rules, stats


def main() -> None:
    assert not (HERE / "prepare_receipt.json").exists()
    protocol_bytes = (HERE / "protocol.json").read_bytes()
    protocol = json.loads(protocol_bytes)
    parent_control = json.loads((Q1460 / "prepare_receipt.json").read_text())
    parent_ordinary = json.loads((Q1463 / "freeze.json").read_text())
    cells = {}
    for degree in (53, 83):
        name = f"n{degree}"
        for kind in ("full_lock", "ordinary"):
            cell = f"{name}_{kind}"
            if kind == "ordinary":
                source = PARENT / "runs" / f"{name}_q{1410 if degree == 53 else 1408}_ordinary.xcnf.gz"
                expected = parent_ordinary["cells"][name]["source_archive_sha256"]
            else:
                source = PARENT / "q1419_partial_pin/runs" / f"{cell}/system.xcnf.gz"
                expected = parent_control["cells"][cell]["source_archive_sha256"]
            archive = source.read_bytes()
            assert sha(archive) == expected
            original = gzip.decompress(archive)
            derived, rules, stats = transform(original)
            encoded = gzip.compress(derived, mtime=0)
            (HERE / f"{cell}.xcnf.gz").write_bytes(encoded)
            cells[cell] = {"source_archive_sha256": sha(archive),
                           "source_raw_sha256": sha(original),
                           "derived_archive_sha256": sha(encoded),
                           "derived_raw_sha256": sha(derived),
                           "witness_rules": len(rules), "stats": stats}
            print(cell, stats["auxiliary_variables"], stats["derived_rows"])
    output = {"proposal_id": "Q1465", "candidate_id": None,
              "protocol_sha256": sha(protocol_bytes),
              "source_sha256": sha(Path(__file__).read_bytes()),
              "parent_control_prepare_receipt_sha256": sha((Q1460 / "prepare_receipt.json").read_bytes()),
              "parent_ordinary_freeze_sha256": sha((Q1463 / "freeze.json").read_bytes()),
              "cells": cells}
    (HERE / "prepare_receipt.json").write_text(json.dumps(output, indent=2,
                                                         sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
