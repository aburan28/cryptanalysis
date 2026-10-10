#!/usr/bin/env python3
"""Independently replay every saved private-XOR elimination on the public XCNF."""

import gzip
import hashlib
import json
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n131_w14_compact_columns_20261010/public_query/system.xcnf.gz"


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def xor_row(line):
    words = line.split()
    first = words[0]
    assert first.startswith(b"x") and words[-1] == b"0"
    if first == b"x":
        literals = [int(word) for word in words[1:-1]]
    else:
        token = first[2:] if first.startswith(b"x-") else first[1:]
        assert token.isdigit() and int(token) > 0
        literals = [int(token)] + [int(word) for word in words[1:-1]]
    assert literals
    variables = {abs(literal) for literal in literals}
    assert len(variables) == len(literals)
    rhs = int(not first.startswith(b"x-")) ^ (sum(literal < 0 for literal in literals) & 1)
    return variables, rhs


def row_digest(variables, rhs):
    digest = hashlib.sha256()
    digest.update(bytes([rhs]))
    for variable in sorted(variables):
        digest.update(variable.to_bytes(4, "little"))
    return digest.digest()


def main():
    started = time.monotonic()
    protocol = json.loads((HERE / "protocol.json").read_text())
    projection = json.loads((HERE / "public/projection_receipt.json").read_text())
    result = projection["projection"]["source_result"]
    assert projection["status"] == result["status"] == "PASS"
    assert protocol["source_sha256"]["public_formula_gzip"] == sha(SOURCE)
    assert projection["projection"]["gzip_sha256"] == sha(HERE / "public/projected.xcnf.gz")
    assert result["source_sha256"]["lift_rows"] == sha(HERE / "public/lift_rows.jsonl")
    assert result["source_sha256"]["variable_map"] == sha(HERE / "public/variable_map.json")
    mapping = json.loads((HERE / "public/variable_map.json").read_text())
    new_to_old = mapping["new_to_old"]
    assert new_to_old[0] == 0 and mapping["free_private"] == []
    assert len(new_to_old) == result["projected_variables"] + 1
    assert all(left < right for left, right in zip(new_to_old[1:], new_to_old[2:]))
    old_to_new = {old: new for new, old in enumerate(new_to_old) if new}
    pivots = []
    pivot_indices = {}
    with (HERE / "public/lift_rows.jsonl").open() as stream:
        for line in stream:
            item = json.loads(line)
            pivot = item["pivot"]
            variables = set(item["variables"])
            assert pivot in variables and pivot not in pivot_indices
            assert len(variables) == len(item["variables"])
            assert item["rhs"] in (0, 1)
            pivot_indices[pivot] = len(pivots)
            pivots.append((variables, item["rhs"]))
    assert len(pivots) == result["private_pivots"]
    assert len(pivots) + result["projected_variables"] == result["original_variables"]
    assert all(variable not in old_to_new for variable in pivot_indices)
    for index, (variables, _) in enumerate(pivots):
        assert all(pivot_indices[variable] >= index for variable in variables
                   if variable in pivot_indices)

    original_xor_rows = []
    original_cnf = []
    with gzip.open(SOURCE, "rb") as stream:
        header = next(stream).split()
        assert header == [b"p", b"cnf", str(result["original_variables"]).encode(),
                          str(result["original_cnf_clauses"] + result["original_xor_rows"]).encode()]
        for line in stream:
            if line.startswith(b"x"):
                original_xor_rows.append(xor_row(line))
            else:
                literals = [int(value) for value in line.split()]
                assert literals[-1] == 0
                original_cnf.append(literals[:-1])
    assert len(original_cnf) == result["original_cnf_clauses"]
    assert len(original_xor_rows) == result["original_xor_rows"]

    projected_rows = Counter()
    with gzip.open(HERE / "public/projected.xcnf.gz", "rb") as stream:
        header = next(stream).split()
        assert header == [b"p", b"cnf", str(result["projected_variables"]).encode(),
                          str(result["original_cnf_clauses"] + result["projected_xor_rows"]).encode()]
        for literals in original_cnf:
            actual = [int(value) for value in next(stream).split()]
            expected = [old_to_new[abs(value)] * (1 if value > 0 else -1)
                        for value in literals] + [0]
            assert actual == expected
        for line in stream:
            variables, rhs = xor_row(line)
            assert all(1 <= variable <= result["projected_variables"] for variable in variables)
            projected_rows[row_digest(variables, rhs)] += 1
    assert sum(projected_rows.values()) == result["projected_xor_rows"]

    reduced_rows = Counter()
    zero_rows = 0
    for original, parity in original_xor_rows:
        variables = set(original)
        while True:
            candidates = [pivot_indices[variable] for variable in variables
                          if variable in pivot_indices]
            if not candidates:
                break
            index = min(candidates)
            pivot_variables, pivot_rhs = pivots[index]
            variables.symmetric_difference_update(pivot_variables)
            parity ^= pivot_rhs
        assert not any(variable in pivot_indices for variable in variables)
        if not variables:
            assert parity == 0
            zero_rows += 1
        else:
            reduced_rows[row_digest({old_to_new[variable] for variable in variables},
                                    parity)] += 1
    assert zero_rows == result["private_pivots"]
    assert reduced_rows == projected_rows
    receipt = {
        "status": "PASS_EXACT_PUBLIC_XOR_ROW_REPLAY",
        "candidate_id": None,
        "original_cnf_clauses_mapped_exactly": len(original_cnf),
        "original_xor_rows_reduced": len(original_xor_rows),
        "zero_pivot_rows": zero_rows,
        "projected_xor_rows_matched_as_multiset": sum(reduced_rows.values()),
        "distinct_projected_xor_row_digests": len(reduced_rows),
        "wall_seconds": time.monotonic() - started,
        "source_sha256": {
            "script": sha(Path(__file__)),
            "protocol": sha(HERE / "protocol.json"),
            "original_formula_gzip": sha(SOURCE),
            "projected_formula_gzip": sha(HERE / "public/projected.xcnf.gz"),
            "lift_rows": sha(HERE / "public/lift_rows.jsonl"),
            "variable_map": sha(HERE / "public/variable_map.json"),
        },
    }
    with (HERE / "public/structure_audit.json").open("x") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": receipt["status"],
                      "reduced_xor_rows": receipt["projected_xor_rows_matched_as_multiset"],
                      "wall_seconds": receipt["wall_seconds"]}))


if __name__ == "__main__":
    main()
