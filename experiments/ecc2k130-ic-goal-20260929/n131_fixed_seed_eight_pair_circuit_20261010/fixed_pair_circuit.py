"""Compact polynomial-basis IR for fixed-seed ECC2K pair outputs."""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "ecc2k130/codegen"))
import build  # noqa: E402
import ir  # noqa: E402


N = 131
TAPS = [1, 2, 13]
MODULUS = (1 << N) | (1 << 13) | (1 << 2) | (1 << 1) | 1
SEED = 212
ROTATIONS = [0, 16, 32, 48, 64, 80, 96, 112]
PIVOT = SEED.bit_length() - 1
SOURCE_BITS = [bit for bit in range(18) if bit != PIVOT]


def gf_mul(a, b):
    out = 0
    while b:
        if b & 1:
            out ^= a
        b >>= 1
        a <<= 1
        if a >> N:
            a ^= MODULUS
    return out


def gf_square(a):
    return gf_mul(a, a)


def gf_half_trace(a):
    value = 0
    term = a
    for _ in range((N + 1) // 2):
        value ^= term
        term = gf_square(gf_square(term))
    if gf_square(value) ^ value != a:
        raise ValueError("source seed lacks Artin-Schreier lift")
    return value


def gf_frobenius(a, exponent):
    for _ in range(exponent):
        a = gf_square(a)
    return a


def coordinate(mask):
    return sum((1 << (bit+1) for bit in range(18) if mask >> bit & 1), 0)


def selector_code(mask):
    if mask >> PIVOT & 1:
        raise ValueError("source mask is not the canonical edge endpoint")
    return sum(((mask >> bit) & 1) << index for index, bit in enumerate(SOURCE_BITS))


def mask_from_code(code):
    if code < 0 or code >= 1 << len(SOURCE_BITS):
        raise ValueError("source code outside 17 bits")
    return sum(((code >> index) & 1) << bit for index, bit in enumerate(SOURCE_BITS))


def product_basis():
    seed_field = coordinate(SEED)
    return [(1 << (2*(bit+1))) ^ (seed_field << (bit+1))
            for bit in SOURCE_BITS]


def product_from_code(code):
    result = 0
    for index, value in enumerate(product_basis()):
        if code >> index & 1:
            result ^= value
    return result


def valid_codes(mask_columns):
    valid = set()
    for mask, column in mask_columns.items():
        other = mask ^ SEED
        if mask < other and other in mask_columns and column != mask_columns[other]:
            valid.add(selector_code(mask))
    return valid


def build_bdd(codes):
    """Return a reduced ordered BDD over 17 code bits, MSB first."""
    unique = {}
    nodes = {}

    def visit(subset, level):
        if not subset:
            return 0
        if len(subset) == 1 << (len(SOURCE_BITS) - level):
            return 1
        if level == len(SOURCE_BITS):
            return 1
        bit = len(SOURCE_BITS) - level - 1
        low = [value for value in subset if not (value >> bit & 1)]
        high = [value for value in subset if value >> bit & 1]
        a, b = visit(low, level+1), visit(high, level+1)
        if a == b:
            return a
        key = (bit, a, b)
        if key not in unique:
            number = len(unique) + 2
            unique[key] = number
            nodes[number] = key
        return unique[key]

    root = visit(sorted(codes), 0)
    return root, nodes


def bdd_accepts(root, nodes, code):
    node = root
    while node >= 2:
        bit, low, high = nodes[node]
        node = high if code >> bit & 1 else low
    return node == 1


def emit_bdd(cnf, root, nodes, selectors):
    """Encode the exact rational, distinct-column source-pair table."""
    literals = {0: cnf.false, 1: cnf.true}
    for node in sorted(nodes):
        bit, low, high = nodes[node]
        a, b = literals[low], literals[high]
        switch = selectors[bit]
        literals[node] = cnf.xorLit(a, cnf.andLit(switch, cnf.xorLit(a, b)))
    cnf.addClause([literals[root]])
    return literals[root]


def xor_vectors(prog, *vectors):
    return [prog.xorList(values) for values in zip(*vectors)]


def pair_ir(prog, slot, one, cutoff=3):
    """Return pair roots and its unrotated reciprocal output coordinate."""
    selectors = [prog.addInput("a%d" % slot, i) for i in range(17)]
    z = [prog.addInput("z%d" % slot, i) for i in range(N)]
    basis = product_basis()
    p = [prog.xorList(selectors[index] for index, value in enumerate(basis)
                      if value >> bit & 1) for bit in range(N)]
    z2 = build.pbSqrIr(prog, z, N, TAPS)
    az = xor_vectors(prog, z2, z)
    product = build.pbMulIr(prog, az, p, N, TAPS, cutoff)
    seed_u2 = gf_square(gf_half_trace(coordinate(SEED)))
    roots = [prog.xorList((product[bit], z2[bit],
                           one if seed_u2 >> bit & 1 else None))
             for bit in range(N)]
    return roots, z


def rotate_ir(prog, value, rotation):
    if rotation == 0:
        return value
    columns = [gf_frobenius(1 << bit, rotation) for bit in range(N)]
    return [prog.xorList(value[index] for index, column in enumerate(columns)
                         if column >> bit & 1) for bit in range(N)]


def reciprocal_s3_ir(prog, u, v, w, one, cutoff=3):
    """Return roots of the exact cleared reciprocal S3 identity."""
    uv = build.pbMulIr(prog, u, v, N, TAPS, cutoff)
    uw = build.pbMulIr(prog, u, w, N, TAPS, cutoff)
    vw = build.pbMulIr(prog, v, w, N, TAPS, cutoff)
    triple = build.pbMulIr(prog, uv, w, N, TAPS, cutoff)
    first = xor_vectors(prog, u, v, w)
    second = xor_vectors(prog, uv, uw, vw, first)
    second[0] = prog.xor(second[0], one)
    term = build.pbMulIr(prog, triple, second, N, TAPS, cutoff)
    square = build.pbSqrIr(prog, xor_vectors(prog, triple, first), N, TAPS)
    return xor_vectors(prog, square, term)


def new_program():
    return ir.Prog()
