import random
import importlib.util
import unittest

import audit
import solver_cost as cost


def evaluate(circuit, inputs):
    values = {0: False, 1: True, **inputs}
    ands = {out: pair for pair, out in circuit.and_cache.items()}
    xors = {out: rule for rule, out in circuit.xor_cache.items()}
    for variable in range(2, circuit.variables + 1):
        if variable in values:
            continue
        if variable in ands:
            a, b = ands[variable]
            values[variable] = values[a] and values[b]
        else:
            terms, parity = xors[variable]
            result = parity
            for term in terms:
                result ^= values[term]
            values[variable] = result
    return values


class CircuitTests(unittest.TestCase):
    def test_products_against_independent_field_arithmetic(self):
        circuit = cost.Circuit(13, 0x201b)
        a = [circuit.var() for _ in range(13)]
        b = [circuit.var() for _ in range(13)]
        product = circuit.multiply(a, b)
        square = circuit.square(a)
        rng = random.Random(912401)
        for _ in range(128):
            x, y = rng.randrange(8192), rng.randrange(8192)
            assignment = {v: bool(x >> j & 1) for j, v in enumerate(a)}
            assignment.update({v: bool(y >> j & 1) for j, v in enumerate(b)})
            values = evaluate(circuit, assignment)
            got = sum(int(values[v]) << j for j, v in enumerate(product))
            got_square = sum(int(values[v]) << j for j, v in enumerate(square))
            self.assertEqual(got, audit.engine.ref.mul(x, y, 0x201b))
            self.assertEqual(got_square, audit.engine.ref.mul(x, x, 0x201b))
            for clause in circuit.clauses:
                self.assertTrue(any(values[abs(v)] == (v > 0) for v in clause))
            for variables, parity in circuit.xors:
                self.assertEqual(sum(values[v] for v in variables) % 2, parity)

    def test_s3_on_independent_group_sums(self):
        data = cost.fixture(87006)
        prime = data["prime"]
        degree, modulus = 13, 0x201b
        for a, b in [(1, 2), (3, 7), (19, 19), (53, prime - 52)]:
            p = audit.engine.ref.scalar_mul(data["generator"], a, degree, modulus)
            q = audit.engine.ref.scalar_mul(data["generator"], b, degree, modulus)
            r = audit.engine.ref.add(p, q, degree, modulus)
            self.assertIsNotNone(r)
            circuit = cost.Circuit(degree, modulus)
            vectors = [[(point[0] >> j) & 1 for j in range(degree)] for point in (p, q, r)]
            circuit.s3(*vectors)
            self.assertNotIn([-1], circuit.clauses)

    def test_fixture_base_is_independently_lifted(self):
        for seed in audit.SEEDS:
            data = cost.fixture(seed)
            subspace = audit.subspace([data["normal"][4 * j] for j in range(3)])
            expected = sorted(p for x in subspace for p in audit.engine.audit.lift(x, 13, 0x201b)
                              if audit.engine.ref.scalar_mul(p, data["prime"], 13, 0x201b) is None)
            self.assertEqual(data["base"], expected)

    def test_full_width_is_rejected(self):
        with self.assertRaises(ValueError):
            cost.Circuit(131, (1 << 131) | 0x2007)

    @unittest.skipUnless(importlib.util.find_spec("pycryptosat"), "CryptoMiniSat Python binding unavailable")
    def test_complete_circuit_accepts_independently_constructed_witness(self):
        data = cost.fixture(87006)
        coordinate = data["allowed"][0]
        x = 0
        for j in range(3):
            if coordinate >> j & 1:
                x ^= data["normal"][4 * j]
        first = next(p for p in data["base"] if p[0] == x)
        for shifted in (False, True):
            circuit, leaves, target_vars = cost.template(data, shifted)
            points = [first]
            for _ in range(3):
                points.append(audit.engine.audit.frobenius(points[-1], 0x201b) if shifted else first)
            sums = [audit.engine.ref.add(points[0], points[1], 13, 0x201b)]
            sums.append(audit.engine.ref.add(sums[-1], points[2], 13, 0x201b))
            target = audit.engine.ref.add(sums[-1], points[3], 13, 0x201b)
            self.assertTrue(all(p is not None for p in sums + [target]))
            gates = set(circuit.and_cache.values()) | set(circuit.xor_cache.values())
            explicit = set(target_vars) | {v for block in leaves for v in block}
            intermediates = [v for v in range(2, circuit.variables + 1)
                             if v not in gates and v not in explicit]
            self.assertEqual(len(intermediates), 26)
            assumptions = [v if coordinate >> j & 1 else -v
                           for block in leaves for j, v in enumerate(block)]
            assumptions += [v if target[0] >> j & 1 else -v for j, v in enumerate(target_vars)]
            assumptions += [v if sums[i][0] >> j & 1 else -v
                            for i in range(2) for j, v in enumerate(intermediates[13*i:13*(i+1)])]
            sat, _ = circuit.solver().solve(assumptions=assumptions)
            self.assertIs(sat, True)


if __name__ == "__main__":
    unittest.main()
