#!/usr/bin/env python3
"""Inventory raw native-XOR components in the two frozen Q1420 XCNFs."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUN = HERE / "runs/R1"
INPUT = ROOT / "experiments/ecc2k130-263-bilinear-ordinary-q0-20261010/runs/R1"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read(path: Path):
    return json.loads(path.read_text())


def source():
    cfg = read(HERE / "source.json")
    if (cfg["schema"] != "ecc2k130-263-gauss-components-source-v1"
            or cfg["parent_commit"] != "025e3a00afa9c0569a8bbb640d7bec6551e68ea3"
            or cfg["policies"] != ["source", "descendant_native"]
            or any(sha(ROOT / name) != digest
                   for name, digest in cfg["pins"].items())):
        raise ValueError("frozen source or archived input differs")
    return cfg


def kind(name: str) -> str:
    if name.startswith("target:"):
        return "target"
    if name.startswith("one:"):
        return "one"
    if name.startswith("f:"):
        return "f"
    return name[0]


def analyze(policy: str) -> dict:
    cfg = source()
    if policy not in cfg["policies"]:
        raise ValueError("curve outside frozen panel")
    archive = INPUT / f"{policy}_wz_only.xcnf.gz"
    receipt = read(INPUT / f"{policy}_wz_only.formula.json")
    named = read(INPUT / f"{policy}_wz_only.inputs.json")
    if (sha(archive) != receipt["formula_gzip_sha256"]
            or sha(INPUT / f"{policy}_wz_only.inputs.json")
            != receipt["named_inputs_sha256"]):
        raise ValueError("archive receipt differs")

    with gzip.open(archive, "rb") as stream:
        head = stream.readline().split()
        if len(head) != 4 or head[:2] != [b"p", b"cnf"]:
            raise ValueError("invalid XCNF header")
        variables, constraints = int(head[2]), int(head[3])
        parent = list(range(variables + 1))
        size = [1] * (variables + 1)

        def find(item: int) -> int:
            while parent[item] != item:
                parent[item] = parent[parent[item]]
                item = parent[item]
            return item

        def union(a: int, b: int) -> None:
            a, b = find(a), find(b)
            if a != b:
                if size[a] < size[b]:
                    a, b = b, a
                parent[b] = a
                size[a] += size[b]

        representatives = []
        xors = clauses = 0
        for line in stream:
            if line.startswith(b"x"):
                signed = [int(token) for token in line[1:].split()]
                if not signed or signed[-1] != 0:
                    raise ValueError("malformed native-XOR line")
                names = [abs(v) for v in signed[:-1]]
                if not names or any(v < 1 or v > variables for v in names):
                    raise ValueError("native-XOR variable outside header")
                for variable in names[1:]:
                    union(names[0], variable)
                representatives.append(names[0])
                xors += 1
            elif line and not line.startswith(b"c"):
                clauses += 1
    if (xors + clauses != constraints
            or xors != receipt["stats"]["xors"]
            or clauses != receipt["stats"]["clauses"]):
        raise ValueError("XCNF constraint counts differ")
    # Re-read the exact uncompressed bytes to bind the structural parse.
    with gzip.open(archive, "rb") as stream:
        h = hashlib.sha256()
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    if h.hexdigest() != receipt["formula_raw_sha256"]:
        raise ValueError("raw XCNF SHA-256 differs")

    xor_counts = Counter(find(rep) for rep in representatives)
    input_counts: dict[int, Counter] = defaultdict(Counter)
    for name, literal in named.items():
        var = abs(literal)
        if not 1 <= var <= variables:
            raise ValueError("named input outside XCNF header")
        input_counts[find(var)][kind(name)] += 1
    nontrivial = [root for root in range(1, variables + 1)
                  if find(root) == root and size[root] > 1]
    nontrivial.sort(key=lambda root: (-size[root], -xor_counts[root], root))
    ranks = {root: index + 1 for index, root in enumerate(nontrivial)}

    def describe(root: int) -> dict:
        return {"raw_component_rank": ranks.get(root),
                "variables": size[root], "native_xor_lines": xor_counts[root],
                "named_inputs": dict(sorted(input_counts[root].items()))}

    selector_roots = {find(abs(named[f"s{leaf}:{bit}"]))
                      for leaf in range(6) for bit in range(24)}
    if len(selector_roots) != 1:
        raise ValueError("selectors do not share the observed raw XOR component")
    selector_root = next(iter(selector_roots))
    row = {
        "schema": "ecc2k130-263-raw-xor-components-v1",
        "policy": policy,
        "proposal_id": "Q1420", "candidate_id": None,
        "formula_sha256": receipt["formula_raw_sha256"],
        "formula_gzip_sha256": sha(archive),
        "source_sha256": sha(HERE / "source.json"),
        "analyzer_sha256": sha(Path(__file__)),
        "variables": variables, "clauses": clauses, "native_xor_lines": xors,
        "nontrivial_components": len(nontrivial),
        "top_raw_components": [describe(root) for root in nontrivial[:12]],
        "selector_component": describe(selector_root),
        "all_144_selector_bits_in_one_raw_component": True,
        "interpretation_boundary": "Raw XCNF variable graph before CryptoMiniSat simplification; matrix sizes after preprocessing need not equal these component sizes.",
    }
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    for policy in source()["policies"]:
        row = analyze(policy)
        data = json.dumps(row, sort_keys=True, indent=2) + "\n"
        path = RUN / f"{policy}.components.json"
        if args.write:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists() and path.read_text() != data:
                raise ValueError("existing component receipt differs")
            if not path.exists():
                path.write_text(data)
        print(json.dumps({"policy": policy,
                          "selector_component": row["selector_component"],
                          "largest": row["top_raw_components"][0]}, sort_keys=True))


if __name__ == "__main__":
    main()
