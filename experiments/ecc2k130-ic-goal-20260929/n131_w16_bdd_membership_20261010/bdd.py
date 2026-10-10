"""Exact reduced decision graph for a fixed binary-mask membership set.

Each auxiliary variable is only constrained in the forward direction.  A
true root forces the branch selected by the mask down to the true terminal;
the remaining branches may be assigned false.  This is equisatisfiable with
the explicit forbidden-mask clauses, including under assignments to every
original circuit variable.
"""


def build(valid, width):
    if not valid or any(x < 0 or x >= 1 << width for x in valid):
        raise ValueError("invalid membership set")
    nodes = [int(x in valid) for x in range(1 << width)]
    graph = {}
    unique = {}
    for bit in range(width):
        upper = []
        for i in range(0, len(nodes), 2):
            pair = (nodes[i], nodes[i + 1])
            if pair[0] == pair[1]:
                upper.append(pair[0])
                continue
            key = (bit, *pair)
            if key not in unique:
                node = len(graph) + 2
                unique[key] = node
                graph[node] = key
            upper.append(unique[key])
        nodes = upper
    assert len(nodes) == 1 and nodes[0] >= 2
    return nodes[0], graph


def evaluate(root, graph, mask):
    node = root
    while node >= 2:
        bit, low, high = graph[node]
        node = high if mask >> bit & 1 else low
    return bool(node)


def emit(circuit, row, root, graph):
    """Emit short forward clauses; return auxiliary wires and clause count."""
    wires = {node: circuit.variable() for node in graph}
    before = len(circuit.clauses)
    for node, (bit, low, high) in graph.items():
        for choice, child in ((0, low), (1, high)):
            if child == 1:
                continue
            clause = [-wires[node], row[bit] if choice == 0 else -row[bit]]
            if child >= 2:
                clause.append(wires[child])
            circuit.clauses.append(" ".join(map(str, clause)) + " 0")
    circuit.clauses.append(f"{wires[root]} 0")
    return wires, len(circuit.clauses) - before


def assignment(graph, wires, mask):
    values = {}
    for node, (bit, low, high) in graph.items():
        child = high if mask >> bit & 1 else low
        values[node] = child == 1 if child < 2 else values[child]
    return {wires[node]: int(values[node]) for node in graph}
