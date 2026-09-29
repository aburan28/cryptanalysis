"""Exact-weight unary counter used as the paired N9 SAT control."""


def require_exact_weight(circuit, xs, weight):
    if not 1 <= weight <= len(xs):
        raise ValueError("unsupported unary weight")
    counter = [[circuit.variable() for _ in range(weight)] for _ in xs]

    def or_equivalence(output, left, right):
        circuit.clauses.extend((f"-{left} {output} 0", f"-{right} {output} 0",
                                f"{left} {right} -{output} 0"))

    circuit.clauses.extend((f"-{counter[0][0]} {xs[0]} 0",
                            f"{counter[0][0]} -{xs[0]} 0"))
    circuit.clauses.extend(f"-{counter[0][j]} 0" for j in range(1, weight))
    for i in range(1, len(xs)):
        or_equivalence(counter[i][0], counter[i - 1][0], xs[i])
        for j in range(1, weight):
            product = circuit.and_(counter[i - 1][j - 1], xs[i])
            or_equivalence(counter[i][j], counter[i - 1][j], product)
        circuit.clauses.append(f"-{counter[i - 1][weight - 1]} -{xs[i]} 0")
    circuit.clauses.append(f"{counter[-1][-1]} 0")
    return {"counter_rows": counter}
