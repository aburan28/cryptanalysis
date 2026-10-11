"""Exact 24-bit reciprocal-output support graphs for two W15 seed pairs."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
PAIR_ROOTS = PARENT / "n131_w15_pair_output_prefix_gate_20261010" / "pair_roots.json"
BITS = 24
EXPECTED = ((12004, 0, 8176), (9022, 13, 8340))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def graph_for(values):
    """Build a reduced decision graph in descending bit order."""
    codes = sorted({value & ((1 << BITS)-1) for value in values})
    unique = {}
    nodes = {}

    def build(subset, bit):
        if not subset:
            return 0
        if bit < 0:
            return 1
        low = [code for code in subset if not (code >> bit & 1)]
        high = [code for code in subset if code >> bit & 1]
        left, right = build(low, bit-1), build(high, bit-1)
        if left == right:
            return left
        key = (bit, left, right)
        if key not in unique:
            node = len(nodes) + 2
            unique[key] = node
            nodes[node] = key
        return unique[key]

    root = build(codes, BITS-1)
    assert root >= 2
    return root, nodes, codes


def evaluate(root, nodes, code):
    node = root
    while node >= 2:
        bit, low, high = nodes[node]
        node = high if code >> bit & 1 else low
    return bool(node)


def load_graphs():
    source = json.loads(PAIR_ROOTS.read_text())
    assert source["status"] == "PASS_COMPLETE_W15_PAIR_OUTPUT_ROOTS"
    assert len(source["pair_rows"]) == len(EXPECTED)
    result = []
    for row, (seed, rotation, expected) in zip(source["pair_rows"], EXPECTED):
        assert (row["seed"], row["rotation"]) == (seed, rotation)
        assert len(row["pairs"]) * 2 == expected
        outputs = [value for pair in row["pairs"] for value in pair[2:]]
        assert len(set(outputs)) == expected
        root, nodes, codes = graph_for(outputs)
        assert all(evaluate(root, nodes, x) for x in outputs)
        result.append({"seed": seed, "rotation": rotation,
                       "outputs": outputs, "root": root,
                       "nodes": nodes, "codes": codes})
    return result


def emit(circuit, output_bits, item):
    """Force exact prefix support using positive-polarity branch clauses."""
    assert len(output_bits) == circuit.n == 131
    wires = {node: circuit.variable() for node in item["nodes"]}
    before = len(circuit.clauses)
    for node, (bit, low, high) in item["nodes"].items():
        if low != 1:
            terms = [-wires[node], output_bits[bit]]
            if low >= 2:
                terms.append(wires[low])
            circuit.clauses.append(" ".join(map(str, terms)) + " 0")
        if high != 1:
            terms = [-wires[node], -output_bits[bit]]
            if high >= 2:
                terms.append(wires[high])
            circuit.clauses.append(" ".join(map(str, terms)) + " 0")
    circuit.clauses.append(f"{wires[item['root']]} 0")
    return wires, len(circuit.clauses) - before


def assignment(item, wires, output):
    code = output & ((1 << BITS)-1)
    values = {}
    for node, (bit, low, high) in item["nodes"].items():
        child = high if code >> bit & 1 else low
        values[node] = bool(child) if child < 2 else values[child]
    assert values[item["root"]]
    return {wires[node]: int(value) for node, value in values.items()}


def projection():
    protocol = json.loads((HERE / "projection_protocol.json").read_text())
    assert protocol["status"] == "FROZEN_W15_PREFIX24_PROJECTION"
    assert protocol["source_sha256"] == {
        "gate": sha(Path(__file__)), "pair_roots": sha(PAIR_ROOTS)}
    graphs = load_graphs()
    rows = []
    for item in graphs:
        root, nodes, codes = item["root"], item["nodes"], item["codes"]
        clauses = sum(int(low != 1) + int(high != 1)
                      for _, low, high in nodes.values()) + 1
        # Count every accepted code in the reduced graph without allocating
        # a 2^24 truth table; compare the count with the complete source set.
        cache = {}
        def count(node, top_bit):
            if node == 0:
                return 0
            if node == 1:
                return 1 << (top_bit + 1)
            key = (node, top_bit)
            if key not in cache:
                bit, low, high = nodes[node]
                cache[key] = (1 << (top_bit-bit)) * (
                    count(low, bit-1) + count(high, bit-1))
            return cache[key]
        assert count(root, BITS-1) == len(codes)
        assert all(evaluate(root, nodes, code) for code in codes)
        allowed = set(codes)
        for code in range(0, 1 << BITS, 4093):
            assert evaluate(root, nodes, code) == (code in allowed)
        rows.append({"seed": item["seed"], "rotation": item["rotation"],
                     "outputs": len(item["outputs"]), "allowed_prefixes": len(codes),
                     "nodes": len(nodes), "forward_clauses": clauses,
                     "accepted_prefix_sha256": hashlib.sha256(
                         b"".join(code.to_bytes(3, "little") for code in codes)).hexdigest()})
    result = {"status": "PASS_EXACT_W15_PREFIX24_PROJECTION",
              "curve_id": protocol["curve_id"], "prefix_bits": BITS,
              "rows": rows, "source_sha256": protocol["source_sha256"],
              "candidate_id": None, "target_count": 0}
    with (HERE / "projection.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"], "rows": rows}))


if __name__ == "__main__":
    projection()
