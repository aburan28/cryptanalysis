#!/usr/bin/env python3
"""Audit every bridge replacement and the resulting XOR component bounds."""

import argparse
import hashlib
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path

PARTIAL_FIRST = 157
PARTIAL_LAST = 1466


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def source_records(path):
    with path.open("rt", encoding="ascii") as stream:
        header = stream.readline().split()
        if len(header) != 4 or header[:2] != ["p", "cnf"]:
            raise ValueError("invalid XCNF header")
        for line in stream:
            if line.strip() and not line.startswith("c"):
                yield line


def forbidden_assignments(literals):
    """Independently enumerate the four variable assignments failing odd XOR."""
    variables = [abs(literal) for literal in literals]
    result = set()
    for bits in itertools.product((False, True), repeat=3):
        values = [bit if literal > 0 else not bit
                  for bit, literal in zip(bits, literals)]
        if sum(values) % 2 == 0:
            result.add(tuple(-variable if bit else variable
                             for bit, variable in zip(bits, variables)))
    if len(result) != 4:
        raise ValueError("ternary XOR has the wrong forbidden assignments")
    return result


def audit_records(original, transformed):
    with original.open() as stream:
        source_header = stream.readline().split()
    with transformed.open() as stream:
        output_header = stream.readline().split()
    source = source_records(original)
    output = source_records(transformed)
    converted = source_count = output_count = 0
    for original_line in source:
        source_count += 1
        if not original_line.startswith("x"):
            if next(output) != original_line:
                raise ValueError("unchanged CNF clause differs")
            output_count += 1
            continue
        fields = original_line[1:].split()
        if fields[-1] != "0":
            raise ValueError("unterminated original XOR")
        literals = tuple(map(int, fields[:-1]))
        if any(PARTIAL_FIRST <= abs(value) <= PARTIAL_LAST
               for value in literals):
            if len(literals) != 3:
                raise ValueError("bridge XOR has the wrong width")
            actual = set()
            for unused in range(4):
                line = next(output)
                tokens = line.split()
                if line.startswith("x") or tokens[-1] != "0":
                    raise ValueError("bridge replacement is not CNF")
                actual.add(tuple(map(int, tokens[:-1])))
            if actual != forbidden_assignments(literals):
                raise ValueError("bridge CNF truth table differs")
            converted += 1
            output_count += 4
        else:
            if next(output) != original_line:
                raise ValueError("unchanged XOR row differs")
            output_count += 1
    if next(output, None) is not None:
        raise ValueError("transformed XCNF has extra records")
    if (converted != 3201 or source_count != int(source_header[3]) or
            output_count != int(output_header[3]) or
            int(output_header[2]) != int(source_header[2])):
        raise ValueError("record dimensions or bridge count differ")
    return converted, source_count, output_count


def xor_components(path):
    with path.open() as stream:
        variables = int(stream.readline().split()[2])
    parent = list(range(variables + 1))
    rank = bytearray(variables + 1)

    def find(value):
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(left, right):
        left, right = find(left), find(right)
        if left == right:
            return
        if rank[left] < rank[right]:
            left, right = right, left
        parent[right] = left
        if rank[left] == rank[right]:
            rank[left] += 1

    for line in source_records(path):
        if not line.startswith("x"):
            continue
        values = [abs(int(token)) for token in line[1:].split()[:-1]]
        for value in values[1:]:
            union(values[0], value)
    rows = Counter()
    columns = defaultdict(set)
    for line in source_records(path):
        if not line.startswith("x"):
            continue
        values = [abs(int(token)) for token in line[1:].split()[:-1]]
        root = find(values[0])
        rows[root] += 1
        columns[root].update(values)
    ordered = sorted(((count, len(columns[root]))
                      for root, count in rows.items()), reverse=True)
    return {
        "component_count": len(ordered),
        "xor_rows": sum(rows.values()),
        "largest_components_rows_columns": ordered[:20],
        "max_rows": max(rows.values()),
        "max_columns": max(map(len, columns.values())),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--transform-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.transform_dir / "independent_audit.json"
    if output.exists():
        raise FileExistsError(output)
    receipt_path = args.transform_dir / "result.json"
    receipt = json.loads(receipt_path.read_text())
    transformed = args.transform_dir / "bridge_cnf.xcnf"
    if (receipt["status"] != "PASS" or
            sha(args.original) != receipt["source_sha256"]["input_xcnf"] or
            sha(transformed) != receipt["source_sha256"]["output_xcnf"]):
        raise ValueError("transform input or output digest differs")
    converted, source_count, output_count = audit_records(args.original,
                                                          transformed)
    original_profile = xor_components(args.original)
    profile = xor_components(transformed)
    fits = profile["max_rows"] <= 10000 and profile["max_columns"] <= 15000
    result = {
        "kind": "independent_n131_d13_public_q_bridge_cnf_and_component_audit",
        "status": ("PASS_EQUIVALENT_AND_COMPONENT_FIT" if fits else
                   "PASS_EQUIVALENT_COMPONENT_EXCEEDS_LIMIT"),
        "converted_ternary_xor_rows": converted,
        "source_records": source_count,
        "output_records": output_count,
        "original_xor_components": original_profile,
        "xor_components": profile,
        "source_sha256": {
            "original_xcnf": sha(args.original),
            "transformed_xcnf": sha(transformed),
            "transform_result": sha(receipt_path),
            "audit_script": sha(Path(__file__)),
        },
    }
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"],
                      "converted": converted,
                      "max_rows": profile["max_rows"],
                      "max_columns": profile["max_columns"]}))


if __name__ == "__main__":
    main()
