"""Unpinned N41 public target circuit using three existential quartics."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
NORM = ROOT / "n41_quartic_joint_public_20261010" / "norm_result.json"
COEFFICIENTS = ROOT / "n41_single_branch_joint_sat_20261011" / "coefficient_result.json"


class Field:
    n = 41
    modulus = (1 << 41) | (1 << 3) | 1

    def mul(self, a, b):
        out = 0
        while b:
            if b & 1:
                out ^= a
            b >>= 1
            a <<= 1
            if a >> self.n:
                a ^= self.modulus
        return out

    def square(self, a):
        return self.mul(a, a)

    def frob(self, a, turns):
        for _ in range(turns):
            a = self.square(a)
        return a

    def inv(self, a):
        assert a
        exponent = (1 << self.n) - 2
        out = 1
        while exponent:
            if exponent & 1:
                out = self.mul(out, a)
            a = self.square(a)
            exponent >>= 1
        return out


def forbid(mask, wires):
    return [(-wire if mask >> bit & 1 else wire)
            for bit, wire in enumerate(wires)]


def clause(circuit, literals):
    circuit.clauses.append(" ".join(map(str, literals)) + " 0")


def nonzero(circuit, wires):
    clause(circuit, wires)


def add_many(circuit, values):
    if not values:
        return circuit.constant(0)
    return [circuit.xor(row) for row in zip(*values)]


def s3(circuit, left, right, output):
    product = circuit.mul(circuit.mul(left, right), output)
    total = add_many(circuit, (left, right, output))
    circuit.require_zero(add_many(circuit, (circuit.square(total),
                                            product, circuit.square(product))))


def source_columns(path):
    lines = Path(path).read_text().splitlines()
    target_x, target_y, order, blocks = map(int, lines[0].split())
    assert blocks == 6 and order == 549756390943
    row = 1
    columns = []
    for index in range(6):
        rotation, size = map(int, lines[row].split())
        row += 1
        assert rotation == 5 * index and size == 64
        mapping = {}
        for line in lines[row:row + size]:
            _, _, mask, sign, column = map(int, line.split())
            assert sign in (0, 1)
            if mask in mapping:
                assert mapping[mask] == column
            mapping[mask] = column
        assert len(mapping) == 32
        columns.extend((mapping, mapping))
        row += size
    assert row == len(lines)
    assert len(set().union(*(set(row.values()) for row in columns))) == 26
    return (target_x, target_y), columns


def product_pair(circuit, field, left_mask, right_mask, rotation):
    # Raw source reciprocal coordinates are sums of t^1,...,t^6.
    source_basis = [1 << (j + 1) for j in range(6)]
    seed = [circuit.xor((a, b)) for a, b in zip(left_mask, right_mask)]
    a = circuit.linear_element(seed, [field.frob(x, rotation) for x in source_basis])
    product_gates, product_basis = [], []
    for i, left in enumerate(left_mask):
        for j, right in enumerate(right_mask):
            product_gates.append(circuit.and_(left, right))
            product_basis.append(field.frob(field.mul(source_basis[i], source_basis[j]),
                                            rotation))
    product = circuit.linear_element(product_gates, product_basis)
    return seed, a, product


def compile_quartic(circuit, values, norm, coefficient_order=(2, 0, 1),
                    product_order=(0, 1)):
    # The exact coefficient record factors A and B by powers of P and Q.
    # Compile those factored coefficients jointly and share their subexpressions.
    records = json.loads(COEFFICIENTS.read_text())["records"]
    assert sorted(coefficient_order) == [0, 1, 2]
    assert sorted(product_order) == [0, 1]
    one = circuit.constant(1)
    factor_cache = {}
    factor_power_cache = {}
    coefficient_cache = {}
    power_cache = {(axis, 1): value for axis, value in enumerate(values)}
    multiplications = 0
    squares = 0

    def power(axis, exponent):
        nonlocal multiplications, squares
        key = (axis, exponent)
        if key not in power_cache:
            half = power(axis, exponent // 2)
            value = circuit.square(half)
            squares += 1
            if exponent & 1:
                value = circuit.mul(value, values[axis])
                multiplications += 1
            power_cache[key] = value
        return power_cache[key]

    def multiply(left, right):
        nonlocal multiplications
        if left[1]:
            return right
        if right[1]:
            return left
        multiplications += 1
        return circuit.mul(left[0], right[0]), False

    def factor(terms, depth):
        key = (terms, depth)
        if key in factor_cache:
            return factor_cache[key]
        if depth == len(coefficient_order):
            assert terms == frozenset({(0, 0, 0)})
            result = (one, True)
        else:
            axis = coefficient_order[depth]
            groups = {}
            for term in terms:
                exponent = term[axis]
                reduced = term[:axis] + (0,) + term[axis + 1:]
                groups.setdefault(exponent, set()).add(reduced)
            exponents = sorted(groups, reverse=True)
            current = exponents[0]
            result = factor(frozenset(groups[current]), depth + 1)
            for exponent in exponents[1:]:
                result = multiply(result, (power(axis, current - exponent), False))
                lower = factor(frozenset(groups[exponent]), depth + 1)
                result = (add_many(circuit, (result[0], lower[0])), False)
                current = exponent
            if current:
                result = multiply(result, (power(axis, current), False))
        factor_cache[key] = result
        return result

    def factor_power(terms, exponent):
        nonlocal squares
        key = (terms, exponent)
        if key not in factor_power_cache:
            if exponent == 1:
                result = factor(terms, 0)
            else:
                half = factor_power(terms, exponent // 2)
                result = (circuit.square(half[0]), False)
                squares += 1
                if exponent & 1:
                    result = multiply(result, factor(terms, 0))
            factor_power_cache[key] = result
        return factor_power_cache[key]

    def coefficient(entry):
        signature = tuple(sorted((int(item["multiplicity"]),
                                  tuple(sorted(tuple(row[:3]) for row in item["terms"])))
                                 for item in entry["factors"]))
        if signature not in coefficient_cache:
            result = (one, True)
            for multiplicity, terms in signature:
                result = multiply(result, factor_power(frozenset(terms), multiplicity))
            coefficient_cache[signature] = result
        return coefficient_cache[signature]

    def bivariate(entries, depth):
        if depth == 2:
            assert len(entries) == 1 and entries[0][0] == (0, 0)
            return coefficient(entries[0][1])
        axis = product_order[depth]
        groups = {}
        for exponents, entry in entries:
            reduced = exponents[:axis] + (0,) + exponents[axis + 1:]
            groups.setdefault(exponents[axis], []).append((reduced, entry))
        exponents = sorted(groups, reverse=True)
        current = exponents[0]
        result = bivariate(groups[current], depth + 1)
        for exponent in exponents[1:]:
            result = multiply(result, (power(axis + 3, current - exponent), False))
            lower = bivariate(groups[exponent], depth + 1)
            result = (add_many(circuit, (result[0], lower[0])), False)
            current = exponent
        if current:
            result = multiply(result, (power(axis + 3, current), False))
        return result

    def polynomial(name):
        entries = [(tuple(row["P_Q_exponents"]), row) for row in records[name]]
        return bivariate(entries, 0)[0]

    A, B = polynomial("A"), polynomial("B")
    return A, B, multiplications, squares


def build(circuit, field, columns, target_reciprocals):
    norm = json.loads(NORM.read_text())
    assert circuit.n == 41 and len(columns) == 12 and len(target_reciprocals) == 2
    masks = [[circuit.variable() for _ in range(6)] for _ in range(12)]
    output_z = [[circuit.variable() for _ in range(41)] for _ in range(3)]
    branch_w = [[circuit.variable() for _ in range(41)] for _ in range(3)]
    intermediate = [circuit.variable() for _ in range(41)]
    target_flag = circuit.variable()
    primary_variables = [*sum(masks, []), *sum(output_z, []),
                         *sum(branch_w, []), *intermediate, target_flag]
    for wires, table in zip(masks, columns):
        for code in range(64):
            if code not in table:
                clause(circuit, forbid(code, wires))
    column_forbids = 0
    for i in range(12):
        for j in range(i + 1, 12):
            for left, col_left in columns[i].items():
                for right, col_right in columns[j].items():
                    if col_left == col_right or (j == i + 1 and i % 2 == 0 and left >= right):
                        clause(circuit, forbid(left, masks[i]) + forbid(right, masks[j]))
                        column_forbids += 1
    pairs = [product_pair(circuit, field, masks[2*i], masks[2*i + 1], 5*i)
             for i in range(6)]
    for i, j in ((2, 3), (4, 5)):
        for bit in range(6):
            circuit.require_zero([circuit.xor((pairs[i][0][bit], pairs[j][0][bit]))])
    for bit in range(3, 6):
        circuit.require_zero([circuit.xor((pairs[2][0][bit], pairs[4][0][bit]))])
    quartic_field_muls = 0
    quartic_squares = 0
    for block in range(3):
        _, a, P = pairs[2 * block]
        _, b, Q = pairs[2 * block + 1]
        z, w = output_z[block], branch_w[block]
        s = circuit.add(a, b)
        circuit.require_zero(add_many(circuit, (circuit.square(w), w, z, s)))
        A, B, muls, squares = compile_quartic(circuit, (a, s, z, P, Q), norm)
        circuit.require_zero(circuit.add(A, circuit.mul(w, B)))
        quartic_field_muls += muls + 1
        quartic_squares += squares
        nonzero(circuit, z)
    target = circuit.linear_element([target_flag],
                                    [target_reciprocals[0] ^ target_reciprocals[1]],
                                    target_reciprocals[0])
    s3(circuit, output_z[0], output_z[1], intermediate)
    s3(circuit, intermediate, output_z[2], target)
    nonzero(circuit, intermediate)
    return {"masks": masks, "output_z": output_z, "branch_w": branch_w,
            "intermediate": intermediate, "target_flag": target_flag,
            "primary_variables": primary_variables,
            "quartic_field_multiplications": quartic_field_muls,
            "quartic_field_squares": quartic_squares,
            "column_and_order_forbids": column_forbids}
