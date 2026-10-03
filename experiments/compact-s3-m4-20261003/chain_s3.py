"""Compact four-summand S3 chain for the type-II normal-basis Koblitz curve.

The three S3 links use two intermediate x coordinates.  Field products are
encoded as shared AND gates and native XOR rows; S5 is never materialized.
This is a bounded point-decomposition stage, not an IC candidate by itself.
"""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ecc2k130/codegen"))
import field  # noqa: E402


class Formula:
    def __init__(self):
        self.variables = 1
        self.clauses = [[1]]
        self.xors = []
        self.and_cache = {}

    def new(self):
        self.variables += 1
        return self.variables

    def and_gate(self, a, b):
        if a == -1 or b == -1:
            return -1
        if a == 1:
            return b
        if b == 1:
            return a
        if a == b:
            return a
        if a == -b:
            return -1
        key = tuple(sorted((a, b)))
        if key in self.and_cache:
            return self.and_cache[key]
        z = self.new()
        self.clauses.extend(([-z, a], [-z, b], [z, -a, -b]))
        self.and_cache[key] = z
        return z

    def xor_relation(self, lits, rhs=False):
        parity = set()
        for lit in lits:
            if lit == 1:
                rhs = not rhs
                continue
            if lit == -1:
                continue
            if lit < 0:
                rhs = not rhs
                lit = -lit
            if lit in parity:
                parity.remove(lit)
            else:
                parity.add(lit)
        if not parity:
            if rhs:
                self.clauses.append([])
            return
        row = sorted(parity)
        if len(row) == 1:
            self.clauses.append([row[0] if rhs else -row[0]])
        else:
            self.xors.append((row, rhs))

    def at_most(self, lits, k):
        """Sinz sequential counter for a normal-basis weight bound."""
        n = len(lits)
        if k >= n:
            return
        if k == 0:
            self.clauses.extend(([-lit] for lit in lits))
            return
        s = [[self.new() for _ in range(k)] for _ in range(n - 1)]
        self.clauses.append([-lits[0], s[0][0]])
        for j in range(1, k):
            self.clauses.append([-s[0][j]])
        for i in range(1, n - 1):
            self.clauses.extend(([-lits[i], s[i][0]],
                                 [-s[i - 1][0], s[i][0]]))
            for j in range(1, k):
                self.clauses.extend(([-lits[i], -s[i - 1][j - 1], s[i][j]],
                                     [-s[i - 1][j], s[i][j]]))
            self.clauses.append([-lits[i], -s[i - 1][k - 1]])
        self.clauses.append([-lits[n - 1], -s[n - 2][k - 1]])

    def write(self, path):
        with Path(path).open("w") as stream:
            stream.write(f"p cnf {self.variables} {len(self.clauses) + len(self.xors)}\n")
            for row in self.clauses:
                stream.write(" ".join(map(str, row)) + " 0\n")
            for row, rhs in self.xors:
                stream.write(("x" if rhs else "x-") + str(row[0]))
                stream.write(" " + " ".join(map(str, row[1:])) + " 0\n")


def multiplication_table(onb):
    n = onb.m
    basis = [onb.fromCoords(1 << i) for i in range(n)]
    return [[onb.toCoords(onb.mul(a, b)) for b in basis] for a in basis]


def square_destinations(onb):
    result = []
    for i in range(onb.m):
        value = onb.toCoords(onb.sqr(onb.fromCoords(1 << i)))
        assert value.bit_count() == 1
        result.append(value.bit_length() - 1)
    assert sorted(result) == list(range(onb.m))
    return result


def product(formula, a, b, table):
    n = len(a)
    rows = [[] for _ in range(n)]
    for i in range(n):
        for j in range(n):
            gate = formula.and_gate(a[i], b[j])
            if gate == -1:
                continue
            mask = table[i][j]
            while mask:
                bit = mask & -mask
                rows[bit.bit_length() - 1].append(gate)
                mask ^= bit
    out = [formula.new() for _ in range(n)]
    for value, terms in zip(out, rows):
        formula.xor_relation([value, *terms])
    return out


def s3_link(formula, a, b, c, table, square_dest):
    ab = product(formula, a, b, table)
    ac = product(formula, a, c, table)
    bc = product(formula, b, c, table)
    abc = product(formula, ab, c, table)
    for source, dest in enumerate(square_dest):
        # S3(a,b,c) = (ab+ac+bc)^2 + abc + 1.
        formula.xor_relation((ab[source], ac[source], bc[source],
                              abc[dest]), True)


def build(n, weight, target_x):
    onb = field.Onb(n)
    table = multiplication_table(onb)
    destinations = square_destinations(onb)
    formula = Formula()
    leaves = [[formula.new() for _ in range(n)] for _ in range(4)]
    intermediates = [[formula.new() for _ in range(n)] for _ in range(2)]
    for point in leaves:
        formula.at_most(point, weight)
        formula.clauses.append(point[:])  # exclude x=0, the 2-torsion point
    target = [1 if target_x >> i & 1 else -1 for i in range(n)]
    s3_link(formula, leaves[0], leaves[1], intermediates[0],
            table, destinations)
    s3_link(formula, intermediates[0], leaves[2], intermediates[1],
            table, destinations)
    s3_link(formula, intermediates[1], leaves[3], target,
            table, destinations)
    return formula, leaves, intermediates


def evaluate_s3(onb, x, y, z):
    f = onb
    xy = f.mul(x, y)
    xz = f.mul(x, z)
    yz = f.mul(y, z)
    return f.add(f.add(f.sqr(f.add(f.add(xy, xz), yz)),
                       f.mul(xy, z)), f.one())
