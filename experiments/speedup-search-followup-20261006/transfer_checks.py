"""Typed transfer checks for the growing-arity direction: trace-zero and
cover transfers do not move a base-field or wrong-order target.

Two typed rules, each checked on a concrete toy instance where one exists and
labelled "derived" where only the certificate is stated.

1. Trace-zero transfer (checked).  On E/F_q with Frobenius phi, the map
   psi = phi - 1 : E(F_{q^n}) -> T = ker(1 + phi + ... + phi^(n-1)) has kernel
   exactly E(F_q).  So a target that already lies in E(F_q) is sent to O and
   the trace-zero transfer carries no information about its logarithm; a
   target in a subgroup H of order r with gcd(r, #E(F_q)) = 1 is transferred
   injectively and logs are preserved, psi([a]G) = [a] psi(G).  A trace-zero
   relation search is therefore only a transfer for extension-field targets
   whose order is prime to the base-field group order.  The toy below uses
   q = 1009, n = 3 and E: y^2 = x^3 + 2x + 3 with explicit F_{q^3} arithmetic.

2. Cover transfer (derived; concrete instance = Weil restriction via the
   trace).  For a cover pi : C -> E of degree d, pi_* pi^* = [d] on E, so the
   pull-back of E[r] into Jac(C) is injective iff r does not divide d, and a
   log a found on the pulled-back pair is recovered on E as a itself (push
   forward gives [d] applied to both sides, invertible mod r).  Certificate:
   gcd(r, d) = 1 with recovery scalar d^(-1) mod r.  The one concrete
   instance exercised here is the inclusion E(F_q) -> E(F_{q^n}) with the
   trace as push-forward, for which pi_* pi^* = [n]: the check confirms
   Tr(P) = [n]P on E(F_q) and that a base-field target of order r with
   n not dividing r is recovered through the pair (incl, Tr).  No genus-g
   cover of an actual target curve is constructed; the rule is a typed
   certificate, not an attack.

Neither rule yields a thin-product instance: a transfer changes the group a
relation search runs in, not the rank or density of its inner product.
"""

from __future__ import annotations

import json
import math
import os
import random

import sympy as sp

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results", "transfer_checks.json")

Q = 1009
A, B = 2, 3
N_EXT = 3
RNG = random.Random(20261006)


# ---------------------------------------------------------------- F_{q^3} ---


def find_irreducible_cubic() -> list[int]:
    x = sp.Symbol("x")
    for c in range(1, Q):
        for b in range(0, Q):
            f = sp.Poly(x**3 + b * x + c, x, modulus=Q)
            if f.is_irreducible:
                return [c % Q, b % Q, 0, 1]
    raise RuntimeError("no irreducible cubic")


MOD = find_irreducible_cubic()  # low-to-high coefficients, monic degree 3
MOD_LOW = MOD[:3]


def fadd(a, b):
    return [(x + y) % Q for x, y in zip(a, b)]


def fsub(a, b):
    return [(x - y) % Q for x, y in zip(a, b)]


def fmul(a, b):
    prod = [0] * 5
    for i, x in enumerate(a):
        if x:
            for j, y in enumerate(b):
                prod[i + j] = (prod[i + j] + x * y) % Q
    for k in (4, 3):
        c = prod[k]
        if c:
            prod[k] = 0
            for i in range(3):
                prod[k - 3 + i] = (prod[k - 3 + i] - c * MOD_LOW[i]) % Q
    return prod[:3]


def fpow(a, e):
    r = [1, 0, 0]
    while e:
        if e & 1:
            r = fmul(r, a)
        a = fmul(a, a)
        e >>= 1
    return r


def finv(a):
    return fpow(a, Q**3 - 2)


def frob(a):
    return fpow(a, Q)


def embed(c: int):
    return [c % Q, 0, 0]


def is_base(a) -> bool:
    return a[1] == 0 and a[2] == 0


ZERO3 = [0, 0, 0]
ONE3 = [1, 0, 0]

# ----------------------------------------------------------------- curve ---

INF = None


def on_curve(P) -> bool:
    if P is INF:
        return True
    x, y = P
    lhs = fmul(y, y)
    rhs = fadd(fadd(fmul(fmul(x, x), x), fmul(embed(A), x)), embed(B))
    return lhs == rhs


def neg(P):
    return INF if P is INF else (P[0], [(-v) % Q for v in P[1]])


def add(P, R):
    if P is INF:
        return R
    if R is INF:
        return P
    x1, y1 = P
    x2, y2 = R
    if x1 == x2:
        if fadd(y1, y2) == ZERO3:
            return INF
        num = fadd(fmul(embed(3), fmul(x1, x1)), embed(A))
        den = fmul(embed(2), y1)
    else:
        num = fsub(y2, y1)
        den = fsub(x2, x1)
    lam = fmul(num, finv(den))
    x3 = fsub(fsub(fmul(lam, lam), x1), x2)
    y3 = fsub(fmul(lam, fsub(x1, x3)), y1)
    return (x3, y3)


def mul(k: int, P):
    R = INF
    while k:
        if k & 1:
            R = add(R, P)
        P = add(P, P)
        k >>= 1
    return R


def point_frob(P):
    return INF if P is INF else (frob(P[0]), frob(P[1]))


def psi(P):
    return add(point_frob(P), neg(P))


def trace(P):
    T, S = INF, P
    for _ in range(N_EXT):
        T = add(T, S)
        S = point_frob(S)
    return T


def is_base_point(P) -> bool:
    return P is INF or (is_base(P[0]) and is_base(P[1]))


# ----------------------------------------------------------- group orders ---


def base_order() -> int:
    cnt = 1
    for x in range(Q):
        rhs = (x**3 + A * x + B) % Q
        if rhs == 0:
            cnt += 1
        elif pow(rhs, (Q - 1) // 2, Q) == 1:
            cnt += 2
    return cnt


def ext_order(n_base: int) -> int:
    t = Q + 1 - n_base
    # alpha^3 + beta^3 = t^3 - 3 q t for the Frobenius eigenvalues alpha, beta
    return Q**3 + 1 - (t**3 - 3 * Q * t)


def sqrt_ext(a):
    """Square root in F_{q^3} (q^3 = 3 mod 4 iff q = 3 mod 4); generic Tonelli for safety."""
    if a == ZERO3:
        return ZERO3
    p3 = Q**3
    if fpow(a, (p3 - 1) // 2) != ONE3:
        return None
    if p3 % 4 == 3:
        return fpow(a, (p3 + 1) // 4)
    # Tonelli-Shanks
    s, qq = 0, p3 - 1
    while qq % 2 == 0:
        qq //= 2
        s += 1
    z = None
    while z is None:
        cand = [RNG.randrange(Q) for _ in range(3)]
        if cand != ZERO3 and fpow(cand, (p3 - 1) // 2) != ONE3:
            z = cand
    m, c, t, r = s, fpow(z, qq), fpow(a, qq), fpow(a, (qq + 1) // 2)
    while t != ONE3:
        i, tt = 0, t
        while tt != ONE3:
            tt = fmul(tt, tt)
            i += 1
        b = fpow(c, 1 << (m - i - 1))
        m, c, t, r = i, fmul(b, b), fmul(t, fmul(b, b)), fmul(r, b)
    return r


def random_ext_point():
    while True:
        x = [RNG.randrange(Q) for _ in range(3)]
        rhs = fadd(fadd(fmul(fmul(x, x), x), fmul(embed(A), x)), embed(B))
        y = sqrt_ext(rhs)
        if y is not None:
            return (x, y)


def random_base_point():
    while True:
        x = RNG.randrange(Q)
        rhs = (x**3 + A * x + B) % Q
        if pow(rhs, (Q - 1) // 2, Q) == 1:
            y = pow(rhs, (Q + 1) // 4, Q) if Q % 4 == 3 else int(sp.sqrt_mod(rhs, Q))
            return (embed(x), embed(y))


def bsgs_log(G, Qp, r: int) -> int:
    m = math.isqrt(r) + 1
    table = {}
    cur = INF
    for j in range(m):
        key = None if cur is INF else (tuple(cur[0]), tuple(cur[1]))
        table.setdefault(key, j)
        cur = add(cur, G)
    step = neg(mul(m, G))
    gamma = Qp
    for i in range(m):
        key = None if gamma is INF else (tuple(gamma[0]), tuple(gamma[1]))
        if key in table:
            return (i * m + table[key]) % r
        gamma = add(gamma, step)
    raise RuntimeError("log not found")


def main() -> None:
    n1 = base_order()
    n3 = ext_order(n1)
    assert n3 % n1 == 0
    cof_t = n3 // n1  # order of the trace-zero subgroup when gcd(n1, n3/n1) is handled below
    fac3 = sp.factorint(n3)
    # H: prime order r | n3 with r coprime to n1 (so H meets E(F_q) trivially)
    r = max(p for p in fac3 if n1 % p != 0)
    cof_H = n3 // r
    G = INF
    while G is INF:
        G = mul(cof_H, random_ext_point())
    assert on_curve(G) and mul(r, G) is INF and not is_base_point(G)

    # (1a) psi kills base-field targets, Tr lands in E(F_q), psi lands in trace zero.
    base_killed = []
    for _ in range(10):
        Pb = random_base_point()
        assert on_curve(Pb) and is_base_point(Pb)
        base_killed.append(psi(Pb) is INF)
    tr_base, psi_tracezero = [], []
    for _ in range(10):
        Pe = random_ext_point()
        tr_base.append(is_base_point(trace(Pe)))
        psi_tracezero.append(trace(psi(Pe)) is INF)

    # (1b) psi is injective on H and preserves logs: psi([a]G) = [a] psi(G), log recovered.
    psiG = psi(G)
    assert psiG is not INF and mul(r, psiG) is INF
    log_pres = []
    for _ in range(5):
        a = RNG.randrange(1, r)
        Qa = mul(a, G)
        lhs = psi(Qa)
        rhs = mul(a, psiG)
        rec = bsgs_log(psiG, lhs, r)
        log_pres.append({"a": a, "psi_linear": lhs == rhs, "log_recovered_on_T": rec == a})

    # (2) Cover certificate: (incl, Tr) with pi_* pi^* = [n]; base-field target of prime order
    #     r1 | n1 with n not dividing r1 recovered via n^(-1) mod r1.
    fac1 = sp.factorint(n1)
    r1 = max(p for p in fac1)
    Gb = INF
    while Gb is INF:
        Gb = mul(n1 // r1, random_base_point())
    tr_is_n = all(trace(mul(k, Gb)) == mul(N_EXT * k, Gb) for k in range(1, 6))
    a1 = RNG.randrange(1, r1)
    Qb = mul(a1, Gb)
    # Work in the extension on the pulled-back pair, then push forward with Tr.
    pushed_G, pushed_Q = trace(Gb), trace(Qb)  # = [n]Gb, [n]Qb
    a_pushed = bsgs_log(pushed_G, pushed_Q, r1)
    cover_cert = {
        "pi": "inclusion E(F_q) -> E(F_{q^3}), pi_* = trace",
        "d": N_EXT,
        "r": int(r1),
        "gcd(r,d)": math.gcd(int(r1), N_EXT),
        "recovery_scalar_d_inv_mod_r": pow(N_EXT, -1, int(r1)) if r1 % N_EXT else None,
        "trace_equals_[n]_on_base_points": tr_is_n,
        "log_recovered_after_push_forward": a_pushed == a1,
        "status": "checked (Weil-restriction instance); genus-g cover of a target curve not constructed",
    }
    typed_rule = [
        {"r": 5, "d": 2, "injective_pullback": math.gcd(5, 2) == 1, "recovery_scalar": pow(2, -1, 5)},
        {"r": 2, "d": 2, "injective_pullback": math.gcd(2, 2) == 1, "recovery_scalar": None},
        {"r": 7, "d": 3, "injective_pullback": math.gcd(7, 3) == 1, "recovery_scalar": pow(3, -1, 7)},
        {"r": 3, "d": 6, "injective_pullback": math.gcd(3, 6) == 1, "recovery_scalar": None},
    ]

    res = {
        "field": {"q": Q, "n": N_EXT, "modulus_low_to_high": MOD, "curve": f"y^2 = x^3 + {A}x + {B}"},
        "orders": {"#E(F_q)": n1, "#E(F_q^3)": n3, "#E(F_q^3)/#E(F_q)": cof_t, "factor_#E(F_q^3)": {str(k): v for k, v in fac3.items()}, "factor_#E(F_q)": {str(k): v for k, v in fac1.items()}},
        "trace_zero": {
            "H_order_r": int(r),
            "gcd(r,#E(F_q))": math.gcd(int(r), n1),
            "psi_kills_10_base_field_points": all(base_killed),
            "trace_of_10_extension_points_in_base_field": all(tr_base),
            "psi_image_has_trace_zero_10_points": all(psi_tracezero),
            "psi_linear_and_log_preserved_on_H": log_pres,
            "status": "checked",
            "consequence": "a base-field target is annihilated; only extension-field targets of order prime to #E(F_q) transfer",
        },
        "cover": {"certificate_instance": cover_cert, "typed_rule_r_not_dividing_d": typed_rule, "status": "derived rule; one Weil-restriction instance checked"},
        "thin_product_relevance": "none: a transfer changes the group of the relation search, not the rank or density of the inner product",
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fh:
        json.dump(res, fh, indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
