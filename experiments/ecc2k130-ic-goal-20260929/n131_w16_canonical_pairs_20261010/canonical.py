"""Exact unsigned mask ordering for the five symmetric W16 source pairs."""


def add_pair_order(circuit, masks):
    if len(masks) % 2 or any(len(row) != len(masks[0]) for row in masks):
        raise ValueError("invalid pair masks")
    width = len(masks[0])
    witnesses = []
    for pair in range(len(masks) // 2):
        left, right = masks[2 * pair:2 * pair + 2]
        prior_equal = None
        steps = []
        for bit in range(width - 1, -1, -1):
            # If all higher bits agree, (left=1,right=0) is forbidden.
            clause = [] if prior_equal is None else [-prior_equal]
            clause.extend((-left[bit], right[bit]))
            circuit.clauses.append(" ".join(map(str, clause)) + " 0")
            if bit == 0:
                break
            difference = circuit.xor((left[bit], right[bit]))
            equal = circuit.variable()
            if prior_equal is None:
                # equal <=> !difference.
                circuit.clauses.append(f"-{equal} -{difference} 0")
                circuit.clauses.append(f"{equal} {difference} 0")
            else:
                # equal <=> prior_equal & !difference.
                circuit.clauses.append(f"-{equal} {prior_equal} 0")
                circuit.clauses.append(f"-{equal} -{difference} 0")
                circuit.clauses.append(f"-{prior_equal} {difference} {equal} 0")
            steps.append((bit, difference, equal))
            prior_equal = equal
        witnesses.append(steps)
    return witnesses


def assignment(masks, witnesses):
    initial = {}
    for pair, steps in enumerate(witnesses):
        a, b = masks[2 * pair:2 * pair + 2]
        equal_prefix = 1
        for bit, difference, equal in steps:
            delta = ((a >> bit) ^ (b >> bit)) & 1
            equal_prefix &= 1 ^ delta
            initial[difference] = delta
            initial[equal] = equal_prefix
    return initial


def canonical_masks(masks):
    if len(masks) % 2:
        raise ValueError("odd mask count")
    result = list(masks)
    for i in range(0, len(result), 2):
        if result[i] > result[i + 1]:
            result[i], result[i + 1] = result[i + 1], result[i]
    return result
