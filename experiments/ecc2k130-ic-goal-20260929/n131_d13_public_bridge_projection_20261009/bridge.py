#!/usr/bin/env python3
"""Move ternary XOR rows touching d13 public-Q chain coordinates into exact CNF."""

import argparse
import hashlib
import json
from pathlib import Path

N = 131
DIM = 13
LEAVES = 12
PARTIAL_FIRST = LEAVES * DIM + 1
PARTIAL_LAST = LEAVES * DIM + (LEAVES - 2) * N
EXPECTED_CONVERTED_ROWS = 3201


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def clauses_for_ternary_xor(literals):
    a, b, c = literals
    return ((a, b, c), (a, -b, -c), (-a, b, -c), (-a, -b, c))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise FileExistsError(args.output_dir)
    if sha(args.input) != args.expected_sha256:
        raise ValueError("original d10 query digest changed")
    args.output_dir.mkdir(parents=True)
    records = []
    converted = clauses = xors = 0
    with args.input.open("rt", encoding="ascii") as stream:
        header = stream.readline().split()
        if len(header) != 4 or header[:2] != ["p", "cnf"]:
            raise ValueError("invalid source XCNF header")
        variables, declared = int(header[2]), int(header[3])
        if variables != 232244 or declared != 399907:
            raise ValueError("source XCNF dimensions changed")
        seen = 0
        for line in stream:
            if line.startswith("c") or not line.strip():
                records.append(line)
                continue
            seen += 1
            if not line.startswith("x"):
                clauses += 1
                records.append(line)
                continue
            tokens = line[1:].split()
            if not tokens or tokens[-1] != "0":
                raise ValueError("unterminated XOR record")
            literals = tuple(map(int, tokens[:-1]))
            if any(PARTIAL_FIRST <= abs(value) <= PARTIAL_LAST
                   for value in literals):
                if len(literals) != 3 or len({abs(v) for v in literals}) != 3:
                    raise ValueError("chain bridge is not a ternary XOR")
                for clause in clauses_for_ternary_xor(literals):
                    records.append("%d %d %d 0\n" % clause)
                converted += 1
                clauses += 4
            else:
                records.append(line)
                xors += 1
    if seen != declared or converted != EXPECTED_CONVERTED_ROWS:
        raise ValueError("source record or bridge count changed")
    new_records = clauses + xors
    output = args.output_dir / "bridge_cnf.xcnf"
    with output.open("x", encoding="ascii") as stream:
        stream.write("p cnf %d %d\n" % (variables, new_records))
        stream.writelines(records)
    result = {
        "kind": "n131_d13_public_q_intermediate_coordinate_xor_to_cnf",
        "status": "PASS",
        "field_degree": N,
        "leaf_count": LEAVES,
        "nominal_leaf_dimension": DIM,
        "partial_variable_first": PARTIAL_FIRST,
        "partial_variable_last": PARTIAL_LAST,
        "converted_ternary_xor_rows": converted,
        "added_cnf_clauses": converted * 4,
        "original_record_count": declared,
        "output_record_count": new_records,
        "output_cnf_clauses": clauses,
        "output_xor_rows": xors,
        "output_xcnf_bytes": output.stat().st_size,
        "source_sha256": {
            "input_xcnf": args.expected_sha256,
            "output_xcnf": sha(output),
            "script": sha(Path(__file__)),
        },
    }
    (args.output_dir / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "PASS", "converted": converted,
                      "clauses": clauses, "xors": xors,
                      "bytes": output.stat().st_size}))


if __name__ == "__main__":
    main()
