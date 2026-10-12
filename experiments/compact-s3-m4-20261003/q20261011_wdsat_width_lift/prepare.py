#!/usr/bin/env python3
"""Lower Q1419 long CNF clauses to at most four literals with exact witnesses."""
from __future__ import annotations

import collections
import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1419 = PARENT / "q1419_partial_pin" / "runs"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_model(path: Path, variables: int) -> dict[int, bool]:
    lines = path.read_text().splitlines()
    assert "s SATISFIABLE" in lines
    model: dict[int, bool] = {}
    for line in lines:
        if line.startswith("v "):
            for token in line[2:].split():
                literal = int(token)
                if literal:
                    assert abs(literal) not in model
                    model[abs(literal)] = literal > 0
    assert set(model) == set(range(1, variables + 1))
    return model


def true(literal: int, model: dict[int, bool]) -> bool:
    return model[abs(literal)] == (literal > 0)


def evaluate(raw: bytes, model: dict[int, bool]) -> dict:
    lines = raw.splitlines()
    header = lines[0].split()
    assert header[:2] == [b"p", b"cnf"] and len(header) == 4
    variables, rows = map(int, header[2:])
    assert set(model) == set(range(1, variables + 1))
    counts = collections.Counter()
    for line in lines[1:]:
        tokens = line.split()
        assert tokens and tokens[-1] == b"0"
        if tokens[0].startswith(b"x"):
            literals = [int(tokens[0][1:]), *(int(t) for t in tokens[1:-1])]
            assert all(1 <= abs(lit) <= variables for lit in literals)
            assert all(lit > 0 for lit in literals[1:])
            assert (sum(model[abs(lit)] for lit in literals) & 1) == (literals[0] > 0)
            counts["xor_rows"] += 1
        else:
            literals = [int(t) for t in tokens[:-1]]
            assert all(1 <= abs(lit) <= variables for lit in literals)
            assert any(true(lit, model) for lit in literals)
            counts["cnf_clauses"] += 1
            counts["max_cnf_width"] = max(counts["max_cnf_width"], len(literals))
    assert counts["cnf_clauses"] + counts["xor_rows"] == rows
    return {"variables": variables, **dict(counts)}


def transform(raw: bytes) -> tuple[bytes, list[tuple[int, tuple[int, ...]]], dict]:
    lines = raw.splitlines()
    header = lines[0].split()
    assert header[:2] == [b"p", b"cnf"] and len(header) == 4
    original_vars, original_rows = map(int, header[2:])
    next_var = original_vars
    output: list[bytes] = []
    witness_rule: list[tuple[int, tuple[int, ...]]] = []
    original_widths = collections.Counter()
    derived_widths = collections.Counter()
    xor_count = 0
    for line in lines[1:]:
        tokens = line.split()
        assert tokens and tokens[-1] == b"0"
        if tokens[0].startswith(b"x"):
            output.append(line)
            xor_count += 1
            continue
        literals = [int(t) for t in tokens[:-1]]
        original_widths[len(literals)] += 1
        if len(literals) <= 4:
            output.append(line)
            derived_widths[len(literals)] += 1
            continue
        next_var += 1
        previous = next_var
        output.append(b" ".join(str(x).encode() for x in [*literals[:3], previous, 0]))
        derived_widths[4] += 1
        consumed = 3
        witness_rule.append((previous, tuple(literals[:consumed])))
        remaining = literals[3:]
        while len(remaining) > 3:
            next_var += 1
            current = next_var
            output.append(b" ".join(str(x).encode() for x in
                                    [-previous, *remaining[:2], current, 0]))
            derived_widths[4] += 1
            consumed += 2
            witness_rule.append((current, tuple(literals[:consumed])))
            previous = current
            remaining = remaining[2:]
        final = [-previous, *remaining]
        assert 2 <= len(final) <= 4
        output.append(b" ".join(str(x).encode() for x in [*final, 0]))
        derived_widths[len(final)] += 1
    assert sum(original_widths.values()) + xor_count == original_rows
    derived = (f"p cnf {next_var} {len(output)}\n".encode() + b"\n".join(output) + b"\n")
    assert all(width <= 4 for width in derived_widths)
    stats = {"original_variables": original_vars, "derived_variables": next_var,
             "auxiliary_variables": next_var - original_vars,
             "original_rows": original_rows, "derived_rows": len(output),
             "xor_rows": xor_count,
             "original_cnf_widths": dict(sorted(original_widths.items())),
             "derived_cnf_widths": dict(sorted(derived_widths.items()))}
    return derived, witness_rule, stats


def main() -> None:
    assert not (HERE / "prepare_receipt.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    cells = {}
    for cell in protocol["cells"]:
        source = Q1419 / cell / "system.xcnf.gz"
        original_archive = source.read_bytes()
        original = gzip.decompress(original_archive)
        derived, rules, stats = transform(original)
        degree = cell.split("_")[0]
        model_path = Q1419 / f"{degree}_full_lock" / "solver.stdout.txt"
        model = parse_model(model_path, stats["original_variables"])
        original_check = evaluate(original, model)
        assert original_check["cnf_clauses"] == sum(stats["original_cnf_widths"].values())
        for auxiliary, prefix in rules:
            model[auxiliary] = not any(true(literal, model) for literal in prefix)
        derived_check = evaluate(derived, model)
        assert derived_check["max_cnf_width"] <= 4
        assert derived_check["xor_rows"] == original_check["xor_rows"]
        archive = gzip.compress(derived, mtime=0)
        target = HERE / f"{cell}.xcnf.gz"
        target.write_bytes(archive)
        cells[cell] = {"source_archive_sha256": sha(original_archive),
                       "source_raw_sha256": sha(original),
                       "derived_archive_sha256": sha(archive),
                       "derived_raw_sha256": sha(derived),
                       "archived_full_lock_witness_sha256": sha(model_path.read_bytes()),
                       "original_witness_replay": original_check,
                       "derived_witness_replay": derived_check, **stats}
        print(cell, stats["auxiliary_variables"], stats["derived_rows"])
    result = {"proposal_id": "Q1459", "candidate_id": None,
              "protocol_sha256": sha((HERE / "protocol.json").read_bytes()),
              "source_sha256": sha(Path(__file__).read_bytes()),
              "cells": cells, "witness_replay_status": "PASS"}
    (HERE / "prepare_receipt.json").write_text(json.dumps(result, indent=2,
                                                           sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
