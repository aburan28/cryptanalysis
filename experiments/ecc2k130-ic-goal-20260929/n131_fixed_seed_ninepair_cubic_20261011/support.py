"""Count fixed-seed signed pair tuples with distinct folded columns exactly."""

import hashlib
import json
from collections import Counter, defaultdict
from fractions import Fraction
from math import comb, factorial
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
R41 = 549756390943
R131 = 680564733841876926932320129493409985129
SOURCES = (
    ("n41_w8_seed184", ROOT / "n41_w7_entropy_cubic_20261011/w8/geometry.json", 184, R41),
    ("n131_w18_seed212", ROOT / "n131_w16_w18_sixpair_width_gate_20261010/support_w18.tsv", 212, R131),
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def columns_from(path):
    if path.suffix == ".json":
        return {int(row["mask"]): int(row["column"])
                for row in json.loads(path.read_text())["rows"]}
    return {int(mask): int(column)
            for mask, column in (line.split() for line in path.read_text().splitlines())}


def multiply(left, right, cap):
    out = [0] * (cap + 1)
    for i, a in enumerate(left):
        for j, b in enumerate(right[:cap + 1 - i]):
            out[i + j] += a * b
    return out


def matching_counts(edges, cap=9):
    # Edges that share a folded column must lie in one conflict component.
    parent = list(range(len(edges)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    incident = defaultdict(list)
    for index, (u, v) in enumerate(edges):
        incident[u].append(index)
        incident[v].append(index)
    for indexes in incident.values():
        for index in indexes[1:]:
            parent[root(index)] = root(indexes[0])
    groups = defaultdict(list)
    for index, edge in enumerate(edges):
        groups[root(index)].append(edge)
    isolated = sum(len(group) == 1 for group in groups.values())
    coeff = [comb(isolated, k) for k in range(cap + 1)]
    sizes = Counter()
    for group in groups.values():
        if len(group) == 1:
            continue
        sizes[len(group)] += 1
        vertices = {vertex for edge in group for vertex in edge}
        bit = {vertex: i for i, vertex in enumerate(vertices)}
        masks = [sum(1 << bit[vertex] for vertex in edge) for edge in group]
        local = [0] * (cap + 1)

        def visit(index, occupied, count):
            if index == len(masks):
                local[count] += 1
                return
            visit(index + 1, occupied, count)
            if count < cap and not occupied & masks[index]:
                visit(index + 1, occupied | masks[index], count + 1)

        visit(0, 0, 0)
        coeff = multiply(coeff, local, cap)
    # Independent k=1 and k=2 checks from the edge-conflict graph.
    conflicts = {tuple(sorted((i, j)))
                 for indexes in incident.values()
                 for pos, i in enumerate(indexes)
                 for j in indexes[pos + 1:]}
    assert coeff[0] == 1 and coeff[1] == len(edges)
    assert coeff[2] == comb(len(edges), 2) - len(conflicts)
    return coeff, dict(sorted(sizes.items())), isolated


def main():
    rows = []
    for label, path, seed, order in SOURCES:
        columns = columns_from(path)
        edges = [(columns[a], columns[a ^ seed])
                 for a in columns if a < (a ^ seed) and a ^ seed in columns
                 and columns[a] != columns[a ^ seed]]
        coeff, components, isolated = matching_counts(edges)
        degree = Counter(vertex for edge in edges for vertex in edge)
        tuples = {str(k): str(coeff[k] * factorial(k) * 4**k)
                  for k in (8, 9)}
        row = {"label": label, "source_sha256": sha(path), "seed_mask": seed,
               "subgroup_order": str(order), "source_masks": len(columns),
               "valid_unordered_pairs": len(edges),
               "selected_folded_columns": len(degree),
               "column_degree_spectrum": dict(sorted(Counter(degree.values()).items())),
               "isolated_pair_components": isolated,
               "nontrivial_component_edge_sizes": components,
               "matching_coefficients_k0_to_k9": list(map(str, coeff)),
               "signed_ordered_distinct_column_tuples": tuples,
               "uniform_target_labeled_mean":
                   {str(k): str(Fraction(int(tuples[str(k)]), order)) for k in (8, 9)},
               "uniform_target_labeled_mean_decimal":
                   {str(k): format(float(Fraction(int(tuples[str(k)]), order)), ".9g")
                    for k in (8, 9)}}
        rows.append(row)
    result = {"status": "PASS_EXACT_DISTINCT_COLUMN_NINE_PAIR_SOURCE_COUNT",
              "scope": "source tuple counting only", "candidate_id": None,
              "target_count": 0, "script_sha256": sha(Path(__file__)), "rows": rows}
    path = HERE / "support_result.json"
    with path.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    for row in rows:
        print(row["label"], row["valid_unordered_pairs"],
              row["uniform_target_labeled_mean_decimal"])


if __name__ == "__main__":
    main()
