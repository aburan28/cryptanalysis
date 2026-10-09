#!/usr/bin/env python3
"""Exact degree-seven map identity and independent secp256k1 point replay."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
FIXTURE = ROOT / "experiments/prime-j0-secp256k1-native/tau6-comb13-bench-fixture.json"
P = 2**256 - 2**32 - 977
ORDER = int("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141", 16)
BETA = int("7ae96a2b657c07106e64479eac3434e99cf0497512f58995c1396c28719501ee", 16)
C_MOD = (8 + 12 * BETA) % P
A_MOD = (2 - BETA) % P
ZERO = (0, 0)
ONE = (1, 0)
BETA_FORMAL = (0, 1)


def radd(x, y):
    return x[0] + y[0], x[1] + y[1]


def rneg(x):
    return -x[0], -x[1]


def rsub(x, y):
    return radd(x, rneg(y))


def rmul(x, y):
    a, b = x
    c, d = y
    return a * c - b * d, a * d + b * c - b * d


def rscale(x, n):
    return x[0] * n, x[1] * n


def padd(x, y):
    out = [radd(x[i] if i < len(x) else ZERO,
                y[i] if i < len(y) else ZERO)
           for i in range(max(len(x), len(y)))]
    while len(out) > 1 and out[-1] == ZERO:
        out.pop()
    return out


def pneg(x):
    return [rneg(value) for value in x]


def psub(x, y):
    return padd(x, pneg(y))


def pmul(x, y):
    out = [ZERO] * (len(x) + len(y) - 1)
    for i, a in enumerate(x):
        for j, b in enumerate(y):
            out[i + j] = radd(out[i + j], rmul(a, b))
    return out


def ppow(x, exponent):
    out = [ONE]
    for _ in range(exponent):
        out = pmul(out, x)
    return out


def pscale(x, scalar):
    return [rscale(value, scalar) for value in x]


def derivative(x):
    return [rscale(x[i], i) for i in range(1, len(x))]


def formal_proof():
    beta = BETA_FORMAL
    c = radd((8, 0), rscale(beta, 12))
    a = rsub((2, 0), beta)
    seven = (7, 0)
    assert rmul(rsub(ONE, rscale(beta, 4)), c) == rscale(radd((8, 0), rscale(beta, 4)), 7)
    c2 = rmul(c, c)
    c3 = rmul(c2, c)
    d = [rneg(c), ONE]
    n = [radd(rscale(c2, 7), rscale(c, 168)),
         radd(rscale(c, 28), (84, 0)), ONE]
    h = [rneg(radd(rscale(c3, 7), rscale(c2, 168))),
         rneg(radd(rscale(c2, 147), rscale(c, 1176))),
         rneg(radd(rscale(c, 63), (168, 0))), ONE]
    t = [ZERO, ONE]
    derivative_identity = padd(pmul(n, d), pscale(pmul(t, psub(pmul(derivative(n), d),
                                                           pscale(n, 2))), 3))
    assert derivative_identity == h
    left = psub(pmul([seven, ONE], ppow(h, 2)), pmul(t, ppow(n, 3)))
    right = pscale(ppow(d, 6), 7)
    multiplier = rmul(rmul(a, a), rmul(a, a))
    multiplier = rmul(multiplier, rmul(a, a))
    right = [rmul(value, multiplier) for value in right]
    assert left == right
    return {"derivative_identity": True, "curve_identity": True,
            "kernel_x_cubic": [c[0], c[1]], "polynomial_degree": len(left) - 1}


def inv(value):
    return pow(value % P, -1, P)


def add(p, q):
    if p is None:
        return q
    if q is None:
        return p
    x, y = p
    u, v = q
    if x == u and (y + v) % P == 0:
        return None
    slope = (3 * x * x * inv(2 * y) if p == q else (v - y) * inv(u - x)) % P
    result_x = (slope * slope - x - u) % P
    return result_x, (slope * (x - result_x) - y) % P


def omega(p):
    return None if p is None else (BETA * p[0] % P, p[1])


def alpha_reference(p):
    if p is None:
        return None
    op = omega(p)
    return add(add(p, p), (op[0], -op[1] % P))


def alpha_map(p, scale):
    if p is None:
        return None
    x, y = p
    z = scale % P
    assert z
    xj = x * z * z % P
    yj = y * z * z * z % P
    t = pow(xj, 3, P)
    u = pow(z, 6, P)
    c = C_MOD * u % P
    s = 7 * u % P
    d = (t - c) % P
    n = (t * t + (28 * c + 12 * s) * t + 7 * c * c + 24 * s * c) % P
    h = (t**3 - (63 * c + 24 * s) * t * t
         - (147 * c * c + 168 * s * c) * t
         - 7 * c**3 - 24 * s * c * c) % P
    xo = xj * n % P
    yo = yj * h % P
    zo = A_MOD * z * d % P
    assert zo, "nonidentity subgroup input landed in degree-seven kernel"
    zi = inv(zo)
    return xo * zi * zi % P, yo * zi * zi * zi % P


def alpha_map_optimized(p, scale):
    """Jacobian schedule: 7 general products, 5 squares, constant actions."""
    if p is None:
        return None
    x, y = p
    z = scale % P
    assert z
    xj = x * z * z % P
    yj = y * z * z * z % P
    z2 = z * z % P
    z4 = z2 * z2 % P
    u = z4 * z2 % P
    t = (yj * yj - 7 * u) % P
    assert t == pow(xj, 3, P)
    tu = t * u % P
    t2 = t * t % P
    u2 = u * u % P
    c = C_MOD
    a1 = (28 * c + 84) % P
    a0 = (7 * c * c + 168 * c) % P
    d = (t - c * u) % P
    n = (t2 + a1 * tu + a0 * u2) % P
    linear = ((a1 + 2 * c) * t + (a1 * c + 2 * a0) * u) % P
    h = (n * d - 3 * tu * linear) % P
    xo = xj * n % P
    yo = yj * h % P
    zo = A_MOD * (z * d % P) % P
    assert zo
    zi = inv(zo)
    return xo * zi * zi % P, yo * zi * zi * zi % P


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    proof = formal_proof()
    assert pow(BETA, 3, P) == 1 and BETA != 1
    assert ORDER % 7 != 0
    fixture = json.loads(FIXTURE.read_text())
    cases = fixture["cases"]
    assert len(cases) == 129
    checks = 0
    digest = hashlib.sha256()
    for index, case in enumerate(cases):
        point = (None if case["expected_identity"] else
                 (int(case["expected_x_hex"], 16), int(case["expected_y_hex"], 16)))
        if point is not None:
            assert (point[1] * point[1] - point[0]**3 - 7) % P == 0
        reference = alpha_reference(point)
        for scale in ((1, 2, 3, 7) if index < 32 else (1,)):
            candidate = alpha_map(point, scale)
            assert candidate == reference, (index, scale)
            assert alpha_map_optimized(point, scale) == candidate, (index, scale, "optimized")
            checks += 1
            digest.update(("identity" if candidate is None else
                           f"{candidate[0]:064x}:{candidate[1]:064x}").encode())
    result = {"schema": 1, "status": "passed", "formal_proof": proof,
              "fixture_cases": len(cases), "projective_checks": checks,
              "output_sha256": digest.hexdigest(),
              "source_sha256": sha(Path(__file__)), "fixture_sha256": sha(FIXTURE),
              "protocol_sha256": sha(HERE / "PROTOCOL.md"),
              "optimized_projective_schedule": {"field_multiplications": 7,
                                                 "field_squarings": 5,
                                                 "constant_actions_separate": True},
              "cpu_speedup_claim": None, "academic_priority_claim": None}
    output = HERE / "map-result.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "projective_checks": checks,
                      "output_sha256": digest.hexdigest()}, sort_keys=True))


if __name__ == "__main__":
    main()
