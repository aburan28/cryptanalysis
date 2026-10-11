"""Independent column-graph and closed-form matching-count replay."""

from collections import Counter, defaultdict
from fractions import Fraction
from itertools import combinations
from math import comb, factorial
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
SUPPORT = GOAL / "n131_w16_w18_sixpair_width_gate_20261010" / "support_w18.tsv"
SOURCE = GOAL / "n131_fixed_seed_eight_pair_circuit_20261010" / "support_result.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mul(a, b):
    return [sum(a[i] * b[k-i] for i in range(len(a))
                if 0 <= k-i < len(b)) for k in range(9)]


def power(poly, exponent):
    out = [1] + [0]*8
    while exponent:
        if exponent & 1:
            out = mul(out, poly)
        poly = mul(poly, poly)
        exponent >>= 1
    return out


def main():
    protocol = json.loads((HERE / "audit_protocol.json").read_text())
    paths = {"audit": HERE / "audit.py", "support": SUPPORT,
             "support_receipt": SOURCE, "result": HERE / "result.json"}
    assert protocol["source_sha256"] == {key: digest(path) for key, path in paths.items()}
    recorded = json.loads(paths["result"].read_text())
    source = json.loads(SOURCE.read_text())
    masks = {int(a): int(b) for a, b in
             (line.split() for line in SUPPORT.read_text().splitlines())}
    seed = 212
    pivot = seed.bit_length() - 1
    bits = [i for i in range(18) if i != pivot]
    graph = {}
    for a in masks:
        b = a ^ seed
        if a < b and b in masks and masks[a] != masks[b]:
            code = sum(((a >> bit) & 1) << i for i, bit in enumerate(bits))
            assert code not in graph
            graph[code] = frozenset((masks[a], masks[b]))
    incidence = defaultdict(set)
    for code, columns in graph.items():
        for column in columns:
            incidence[column].add(code)
    unseen = set(graph)
    types = Counter()
    while unseen:
        stack = [unseen.pop()]
        component = set(stack)
        while stack:
            for column in graph[stack.pop()]:
                for code in incidence[column]:
                    if code in unseen:
                        unseen.remove(code)
                        component.add(code)
                        stack.append(code)
        size = len(component)
        independent_pairs = sum(graph[a].isdisjoint(graph[b])
                                for a, b in combinations(component, 2))
        assert size <= 3
        types[(size, independent_pairs)] += 1
    assert types == {(1, 0): 33082, (2, 0): 26,
                     (3, 1): 18, (3, 0): 1}
    polynomial = [1] + [0]*8
    for kind, count in types.items():
        size, independent_pairs = kind
        polynomial = mul(polynomial, power([1, size, independent_pairs], count))
    ordered = factorial(8)*polynomial[8]
    subgroup_order = int(source["subgroup_order"])
    mean = Fraction(ordered*4**8, subgroup_order)
    assert str(ordered) == recorded["ordered_distinct_column_code_tuples_exact"]
    assert str(mean) == recorded["uniform_target_mean_exact"]
    assert len(graph) == recorded["valid_pair_codes"]
    audit = {"status": "PASS_INDEPENDENT_MATCHING_POLYNOMIAL_AUDIT",
             "component_type_counts": {str(key): val for key, val in sorted(types.items())},
             "matching_polynomial": "(1+x)^33082(1+2x)^26(1+3x+x^2)^18(1+3x)",
             "degree_eight_coefficient": str(polynomial[8]),
             "ordered_distinct_column_code_tuples": str(ordered),
             "uniform_target_mean": str(mean),
             "source_sha256": protocol["source_sha256"],
             "protocol_sha256": digest(HERE / "audit_protocol.json")}
    (HERE / "audit_result.json").write_text(json.dumps(audit, indent=2, sort_keys=True)+"\n")
    print(json.dumps({"status": audit["status"],
                      "degree_eight_coefficient": audit["degree_eight_coefficient"]}))


if __name__ == "__main__":
    main()
