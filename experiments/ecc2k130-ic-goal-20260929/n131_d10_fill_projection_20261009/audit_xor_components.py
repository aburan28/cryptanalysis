#!/usr/bin/env python3
"""Count connected XOR-row components in two frozen XCNF inputs."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def profile(path):
    with path.open() as stream:
        header = stream.readline().split()
    if len(header) < 4 or header[:2] != ["p", "cnf"]:
        raise ValueError("missing XCNF header")
    variables = int(header[2])
    parent = list(range(variables + 1))
    rank = bytearray(variables + 1)

    def find(value):
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(first, second):
        first, second = find(first), find(second)
        if first == second:
            return
        if rank[first] < rank[second]:
            first, second = second, first
        parent[second] = first
        if rank[first] == rank[second]:
            rank[first] += 1

    anchors = []
    with path.open() as stream:
        for line in stream:
            if not line.startswith("x"):
                continue
            fields = line[1:].split()
            if not fields or fields[-1] != "0":
                raise ValueError("unterminated XOR record")
            values = [abs(int(field)) for field in fields[:-1]]
            if not values or any(value < 1 or value > variables for value in values):
                raise ValueError("invalid XOR variable")
            anchor = values[0]
            for value in values[1:]:
                union(anchor, value)
            anchors.append(anchor)

    sizes = Counter(find(anchor) for anchor in anchors)
    return {
        "sha256": digest(path),
        "variables": variables,
        "xor_rows": len(anchors),
        "xor_connected_components": len(sizes),
        "component_row_counts_descending": sorted(sizes.values(), reverse=True),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--projected", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = {
        "kind": "xcnf_xor_connected_component_profile",
        "original": profile(args.original),
        "projected": profile(args.projected),
    }
    if (result["original"]["xor_connected_components"] !=
            result["projected"]["xor_connected_components"]):
        raise ValueError("XOR component count changed")
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({side: result[side]["component_row_counts_descending"][0]
                      for side in ("original", "projected")}))


if __name__ == "__main__":
    main()
