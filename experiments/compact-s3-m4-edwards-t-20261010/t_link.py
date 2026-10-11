"""Torsion-invariant coordinate and compact binary-Edwards S3 link."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "experiments/compact-s3-m4-20261003"),
                str(ROOT / "ecc2k130/codegen")]
from chain_s3 import product  # noqa: E402


def t_of_x(onb, x):
    """t=x/(x^2+x+1) on y^2+xy=x^3+1, with no pole for odd n."""
    denominator = onb.add(onb.add(onb.sqr(x), x), onb.one())
    assert denominator != 0
    return onb.mul(x, onb.inv(denominator))


def x_roots_of_t(onb, curve, t):
    """Solve t*x^2+(t+1)*x+t=0 over an odd-degree binary field."""
    one = onb.one()
    if t == 0:
        return (0,)
    b = onb.add(one, onb.inv(t))
    if b == 0:
        return (one,)
    inverse_b = onb.inv(b)
    q = onb.sqr(inverse_b)
    if onb.trace(q):
        return ()
    first = onb.mul(b, curve.halfTrace(q))
    second = onb.add(first, b)
    assert first != second and onb.mul(first, second) == one
    assert t_of_x(onb, first) == t_of_x(onb, second) == t
    return first, second


def evaluate_t3(onb, a, b, c):
    """f3=(1+h)c^2+h*c+(a+b)^2, h=ab(a+1)(b+1)."""
    s = onb.add(a, b)
    p = onb.mul(a, b)
    h = onb.mul(p, onb.add(onb.add(p, s), onb.one()))
    return onb.add(onb.add(onb.sqr(c),
                           onb.mul(h, onb.add(onb.sqr(c), c))),
                   onb.sqr(s))


def square_literals(bits, destinations):
    answer = [None] * len(bits)
    for source, dest in enumerate(destinations):
        answer[dest] = bits[source]
    assert all(lit is not None for lit in answer)
    return answer


def xor_vector(formula, *vectors):
    answer = [formula.new() for _ in vectors[0]]
    for index, out in enumerate(answer):
        formula.xor_relation([out, *(vector[index] for vector in vectors)])
    return answer


def t3_link(formula, a, b, c, table, destinations, one_coords):
    """Add f3(a,b,c)=0 with three shared field-product circuits."""
    assert len(a) == len(b) == len(c) == len(destinations)
    n = len(a)
    one = [1 if one_coords >> i & 1 else -1 for i in range(n)]
    s = xor_vector(formula, a, b)
    p = product(formula, a, b, table)
    temp = xor_vector(formula, p, s, one)
    h = product(formula, p, temp, table)
    c_sq = square_literals(c, destinations)
    s_sq = square_literals(s, destinations)
    d = xor_vector(formula, c_sq, c)
    cross = product(formula, h, d, table)
    for i in range(n):
        formula.xor_relation((c_sq[i], cross[i], s_sq[i]))
