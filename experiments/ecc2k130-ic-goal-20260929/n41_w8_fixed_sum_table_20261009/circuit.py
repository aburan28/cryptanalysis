"""Exact 80-descriptor fixed-sum pair tables in a six-block target S3 tree."""

N = 41
BLOCKS = 6


def one_hot(circuit, row):
    """At least one plus a linear-size sequential at-most-one encoding."""
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


def build(circuit, geometry, target_us):
    if (len(geometry["blocks"]) < BLOCKS or len(target_us) != 4 or
            geometry["fixed_seed_sum_code"] != 56 or
            geometry["permitted_mask_pairs"] != 40):
        raise ValueError("frozen exact domain changed")
    domains = [descriptors(block) for block in geometry["blocks"][:BLOCKS]]
    flags = [[circuit.variable() for _ in domain] for domain in domains]
    onehot_aux = sum(one_hot(circuit, row) for row in flags)
    outputs = [circuit.linear_element(row, [entry["z"] for entry in domain])
               for row, domain in zip(flags, domains)]
    target_flags = [circuit.variable() for _ in range(4)]
    onehot_aux += one_hot(circuit, target_flags)
    duplicate_clauses = 0
    for i in range(BLOCKS):
        for j in range(i + 1, BLOCKS):
            for left, x in enumerate(domains[i]):
                xcols = set(x["columns"])
                for right, y in enumerate(domains[j]):
                    if xcols.isdisjoint(y["columns"]):
                        continue
                    circuit.clauses.append(f"-{flags[i][left]} -{flags[j][right]} 0")
                    duplicate_clauses += 1
    middle = [[circuit.variable() for _ in range(N)] for _ in range(4)]
    for row in middle:
        nonzero_nonone(circuit, row)
    link(circuit, outputs[0], outputs[1], middle[0])
    link(circuit, outputs[2], outputs[3], middle[1])
    link(circuit, outputs[4], outputs[5], middle[2])
    link(circuit, middle[0], middle[1], middle[3])
    target = circuit.linear_element(target_flags, target_us)
    link(circuit, middle[3], middle[2], target)
    return {"descriptor_flags": flags, "descriptors": domains,
            "pair_output_wires": outputs, "target_flag_wires": target_flags,
            "middle_wires": middle, "target_us": target_us,
            "duplicate_column_clauses": duplicate_clauses,
            "onehot_auxiliary_variables": onehot_aux,
            "primary_variables": 6*80+4+4*N,
            "chain": "six exact pair tables and five balanced target links"}
