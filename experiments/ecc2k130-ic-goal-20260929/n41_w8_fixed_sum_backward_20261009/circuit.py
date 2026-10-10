"""Five forward pair tables constrained by an exact target residual domain."""

N = 41
FORWARD_BLOCKS = 5


def one_hot(circuit, row):
    if not row:
        raise ValueError("empty exact domain")
    circuit.clauses.append(" ".join(map(str, row)) + " 0")
    if len(row) == 1:
        return 0
    aux = [circuit.variable() for _ in range(len(row) - 1)]
    circuit.clauses.append(f"-{row[0]} {aux[0]} 0")
    for i in range(1, len(row) - 1):
        circuit.clauses.append(f"-{row[i]} {aux[i]} 0")
        circuit.clauses.append(f"-{aux[i-1]} {aux[i]} 0")
        circuit.clauses.append(f"-{row[i]} -{aux[i-1]} 0")
    circuit.clauses.append(f"-{row[-1]} -{aux[-1]} 0")
    return len(aux)


def nonzero_nonone(circuit, row):
    for values in (row, row[1:]):
        circuit.clauses.append(" ".join(map(str, values)) + " 0")


def link(circuit, left, right, output):
    a = circuit.add(circuit.square(left), left)
    b = circuit.add(circuit.square(right), right)
    product = circuit.mul(a, b)
    lhs = circuit.mul(product, circuit.add(circuit.square(output), output))
    rhs = circuit.square(circuit.add(circuit.add(left, right), output))
    circuit.require_zero(circuit.add(lhs, rhs))


def descriptors(block):
    grouped = {}
    for state in block["states"]:
        grouped.setdefault((state["a"], state["z"]), []).append(state)
    if len(grouped) != 80:
        raise ValueError("fixed-sum pair-output support changed")
    result = []
    for (a, z), states in sorted(grouped.items()):
        if (len(states) != 2 or
                states[0]["columns"] != states[1]["columns"] or
                z in (0, 1)):
            raise ValueError("signed pair-output multiplicity changed")
        result.append({"a": a, "z": z, "columns": states[0]["columns"]})
    return result


def build(circuit, geometry, reach):
    if (len(geometry["blocks"]) < 6 or len(reach) != 640 or
            geometry["fixed_seed_sum_code"] != 56 or
            geometry["permitted_mask_pairs"] != 40):
        raise ValueError("frozen exact backward domain changed")
    domains = [descriptors(block) for block in geometry["blocks"][:5]]
    reach_flags = [circuit.variable() for _ in reach]
    onehot_aux = one_hot(circuit, reach_flags)
    flags = [[circuit.variable() for _ in domain] for domain in domains]
    onehot_aux += sum(one_hot(circuit, row) for row in flags)
    outputs = [circuit.linear_element(row, [entry["z"] for entry in domain])
               for row, domain in zip(flags, domains)]
    w = circuit.linear_element(reach_flags,
                               [entry["w_phi"] for entry in reach])
    duplicate_clauses = 0
    for i in range(FORWARD_BLOCKS):
        for j in range(i + 1, FORWARD_BLOCKS):
            for left, x in enumerate(domains[i]):
                xcols = set(x["columns"])
                for right, y in enumerate(domains[j]):
                    if xcols.isdisjoint(y["columns"]):
                        continue
                    circuit.clauses.append(f"-{flags[i][left]} -{flags[j][right]} 0")
                    duplicate_clauses += 1
        for left, x in enumerate(domains[i]):
            xcols = set(x["columns"])
            for right, entry in enumerate(reach):
                if xcols.isdisjoint(entry["last_columns"]):
                    continue
                circuit.clauses.append(f"-{flags[i][left]} -{reach_flags[right]} 0")
                duplicate_clauses += 1
    middle = [[circuit.variable() for _ in range(N)] for _ in range(3)]
    for row in middle:
        nonzero_nonone(circuit, row)
    # Place the target-conditioned root equation first in the emitted XCNF.
    link(circuit, middle[2], outputs[4], w)
    link(circuit, outputs[0], outputs[1], middle[0])
    link(circuit, outputs[2], outputs[3], middle[1])
    link(circuit, middle[0], middle[1], middle[2])
    return {"descriptor_flags": flags, "descriptors": domains,
            "pair_output_wires": outputs,
            "reachability_flags": reach_flags, "reachability": reach,
            "partial_w_wires": w, "middle_wires": middle,
            "duplicate_column_clauses": duplicate_clauses,
            "onehot_auxiliary_variables": onehot_aux,
            "primary_variables": 640 + 5*80 + 3*N,
            "chain": "target residual domain then four forward S3 links"}
