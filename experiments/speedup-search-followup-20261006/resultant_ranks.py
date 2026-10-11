"""Growing-arity elliptic-curve relations: generic resultant ranks and the
generic parameter obstruction.

Generic rank (derived; checked exactly below).  Split a summation
polynomial recursively; the two children have degrees r = 2^(a-1) and
s = 2^(b-1) in the glue variable z.  Flatten Res_z(f, g) as a matrix whose
rows are monomials in the coefficients of f and whose columns are monomials
in the coefficients of g.  Making f monic with roots beta_1..beta_r,
Res_z(f, g) = prod_j g(beta_j) expands into the distinct monomial symmetric
functions m_lambda(beta) with lambda inside an r x s rectangle, which are a
basis, so

    rank = C(r + s, r).

Semaev specialisation (the coefficients are themselves polynomials in the
point coordinates) can only lower this; the specialised rank is measured
below for S4 and S5 on a concrete curve.

Balanced generic ceilings (derived): m=4 (2,2) 6; m=5 (2,4) 15; m=6 (4,4) 70;
m=7 (4,8) 495; m=8 (8,8) 12,870; m=10 (16,16) 601,080,390;
m=14 (64,64) about 2^124.17.

Generic parameter obstruction (derived from the premise).  A one-versus-rest
Semaev flattening has rank 2^(m-2) + 1 (S_m has degree 2^(m-2) in each
variable), so a balanced useful inner dimension is at least that large.  If a
half-tuple list has size N = B^(m/2) and constant-success relation search
needs (2B)^m >~ |H|, then D <= N^(1/18) with D > 2^(m-2) gives 2^m < 4 N^(1/18),
so N^2 = B^m >= |H| / 2^m > |H| / (4 N^(1/18)), i.e.

    N > (|H|/4)^(18/37),      AVW preprocessing >= N^(2 - 0.063/18) > (|H|/4)^0.971...,

far above generic rho at |H|^(1/2).  A pathological specialised rank
collapse would have to be demonstrated, not assumed.

Large rank is not a thin-product regime anyway: lifted factor-base points
support ordinary group-sum hashing, and x-only child polynomials support
intermediate-root hashing after factorisation; both run near list and
root-output size instead of forming almost all cross-list dot products.

What this module does.
  * Computes the generic flattening rank of Res_z(f, g) with fully symbolic
    coefficients for (r, s) in {(1,1), (1,2), (2,2), (1,3), (2,3), (2,4),
    (3,3), (4,4)} and checks it equals C(r+s, r).  The Sylvester matrix has
    single-variable entries, so its determinant is expanded exactly as a
    signed sum of monomials over all permutations (8! = 40320 for (4,4)).
  * Tabulates the balanced ceilings (exact binomials).
  * Measures the specialised Semaev ranks on y^2 = x^3 + 2x + 3:
    S4 = Res(S3, S3) flattened (x1,x2) | (x3,x4); S5 = Res(S3, S4) flattened
    (x1,x2) | (x3,x4,x5); and the one-versus-rest ranks of S3, S4, S5.
    A flattening rank equals the rank of the evaluation matrix
    E[i][j] = S(P_i, Q_j) once the row points P_i and column points Q_j are
    numerous enough that the monomial evaluation matrices have full rank;
    ranks are computed exactly mod p = 2^61 - 1 with more random points than
    monomials on each side, and the S4 value is cross-checked against the
    fully symbolic sympy expansion.  A rank mod p is a lower bound for the
    rank over Q and equals it except on a measure-zero set of primes.
  * Evaluates the parameter obstruction numerically for several m.
"""

from __future__ import annotations

import json
import math
import os
import random
import time
from itertools import permutations

import sympy as sp

from avw_model import MAX_D_EXP, PRE_EXP

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results", "resultant_ranks.json")
P = 2**61 - 1
RNG = random.Random(20261006)


def rank_mod_p(rows: list[list[int]], p: int = P) -> int:
    M = [[v % p for v in r] for r in rows]
    rank = 0
    ncols = len(M[0]) if M else 0
    for c in range(ncols):
        piv = next((i for i in range(rank, len(M)) if M[i][c]), None)
        if piv is None:
            continue
        M[rank], M[piv] = M[piv], M[rank]
        inv = pow(M[rank][c], -1, p)
        M[rank] = [v * inv % p for v in M[rank]]
        for i in range(len(M)):
            if i != rank and M[i][c]:
                f = M[i][c]
                M[i] = [(a - f * b) % p for a, b in zip(M[i], M[rank])]
        rank += 1
    return rank


# --------------------------------------------------------------------------
# Generic ranks: exact Leibniz expansion of the Sylvester matrix.
# --------------------------------------------------------------------------


def sylvester_symbolic(r: int, s: int) -> list[list[tuple[str, int] | None]]:
    """(r+s) x (r+s) Sylvester matrix of f (deg r) and g (deg s); entry = ('a', i) / ('b', j) / None."""
    n = r + s
    M: list[list[tuple[str, int] | None]] = [[None] * n for _ in range(n)]
    for row in range(s):  # s shifted copies of f
        for i in range(r + 1):
            M[row][row + i] = ("a", r - i)
    for row in range(r):  # r shifted copies of g
        for j in range(s + 1):
            M[s + row][row + j] = ("b", s - j)
    return M


def perm_sign(perm: tuple[int, ...]) -> int:
    sign, seen = 1, [False] * len(perm)
    for i in range(len(perm)):
        if seen[i]:
            continue
        j, cyc = i, 0
        while not seen[j]:
            seen[j] = True
            j = perm[j]
            cyc += 1
        if cyc % 2 == 0:
            sign = -sign
    return sign


def generic_rank(r: int, s: int) -> dict:
    t0 = time.perf_counter()
    M = sylvester_symbolic(r, s)
    n = r + s
    poly: dict[tuple[tuple[int, ...], tuple[int, ...]], int] = {}
    for perm in permutations(range(n)):
        ea, eb = [0] * (r + 1), [0] * (s + 1)
        ok = True
        for i in range(n):
            e = M[i][perm[i]]
            if e is None:
                ok = False
                break
            (ea if e[0] == "a" else eb)[e[1]] += 1
        if not ok:
            continue
        key = (tuple(ea), tuple(eb))
        poly[key] = poly.get(key, 0) + perm_sign(perm)
    poly = {k: v for k, v in poly.items() if v}
    rows = sorted({k[0] for k in poly})
    cols = sorted({k[1] for k in poly})
    ri = {k: i for i, k in enumerate(rows)}
    ci = {k: i for i, k in enumerate(cols)}
    mat = [[0] * len(cols) for _ in rows]
    for (ka, kb), v in poly.items():
        mat[ri[ka]][ci[kb]] = v
    rank = rank_mod_p(mat)
    expected = math.comb(r + s, r)
    return {
        "r": r,
        "s": s,
        "rank": rank,
        "rows": len(rows),
        "cols": len(cols),
        "terms": len(poly),
        "C(r+s,r)": expected,
        "seconds": round(time.perf_counter() - t0, 2),
        "status": "checked" if rank == expected else "MISMATCH",
    }


def balanced_ceilings() -> list[dict]:
    out = []
    for m in (4, 5, 6, 7, 8, 10, 14):
        a = (m - 2) // 2 + 1
        b = m - a
        r, s = 2 ** (a - 1), 2 ** (b - 1)
        c = math.comb(r + s, r)
        out.append({"m": m, "r": r, "s": s, "generic_rank_ceiling": c, "log2": round(math.log2(c), 2)})
    return out


# --------------------------------------------------------------------------
# Semaev specialised ranks: exact evaluation matrices mod p.
# --------------------------------------------------------------------------

A_COEF, B_COEF = 2, 3


def s3_coeffs(u: int, v: int) -> list[int]:
    """S3(u, v, X) as [c0, c1, c2] in X, mod p, for y^2 = x^3 + A x + B."""
    c2 = (u - v) ** 2
    c1 = -2 * ((u + v) * (u * v + A_COEF) + 2 * B_COEF)
    c0 = (u * v - A_COEF) ** 2 - 4 * B_COEF * (u + v)
    return [c0 % P, c1 % P, c2 % P]


def det_mod_p(M: list[list[int]]) -> int:
    M = [r[:] for r in M]
    n = len(M)
    det = 1
    for c in range(n):
        piv = next((i for i in range(c, n) if M[i][c]), None)
        if piv is None:
            return 0
        if piv != c:
            M[c], M[piv] = M[piv], M[c]
            det = -det
        det = det * M[c][c] % P
        inv = pow(M[c][c], -1, P)
        for i in range(c + 1, n):
            if M[i][c]:
                f = M[i][c] * inv % P
                M[i] = [(a - f * b) % P for a, b in zip(M[i], M[c])]
    return det % P


def resultant_numeric(f: list[int], g: list[int]) -> int:
    """Res_X(f, g) for coefficient lists (low to high) mod p via the Sylvester determinant."""
    r, s = len(f) - 1, len(g) - 1
    n = r + s
    M = [[0] * n for _ in range(n)]
    for row in range(s):
        for i in range(r + 1):
            M[row][row + i] = f[r - i]
    for row in range(r):
        for j in range(s + 1):
            M[s + row][row + j] = g[s - j]
    return det_mod_p(M)


def s4_coeffs(x3: int, x4: int, x5: int) -> list[int]:
    """S4(x3, x4, x5, X) as a degree-4 polynomial in X, mod p, by interpolation."""
    f = s3_coeffs(x3, x4)
    xs = list(range(5))
    ys = [resultant_numeric(f, s3_coeffs(x5, x)) for x in xs]
    return lagrange_coeffs(xs, ys)


def lagrange_coeffs(xs: list[int], ys: list[int]) -> list[int]:
    n = len(xs)
    coeffs = [0] * n
    for i in range(n):
        num = [1]
        denom = 1
        for j in range(n):
            if j == i:
                continue
            num = poly_mul(num, [(-xs[j]) % P, 1])
            denom = denom * (xs[i] - xs[j]) % P
        scale = ys[i] * pow(denom, -1, P) % P
        for k in range(n):
            coeffs[k] = (coeffs[k] + scale * num[k]) % P
    return coeffs


def poly_mul(a: list[int], b: list[int]) -> list[int]:
    out = [0] * (len(a) + len(b) - 1)
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            out[i + j] = (out[i + j] + x * y) % P
    return out


def S3_eval(x1, x2, x3):
    c = s3_coeffs(x1, x2)
    return (c[0] + c[1] * x3 + c[2] * x3 * x3) % P


def S4_eval(x1, x2, x3, x4):
    return resultant_numeric(s3_coeffs(x1, x2), s3_coeffs(x3, x4))


def S5_eval(x1, x2, x3, x4, x5):
    return resultant_numeric(s3_coeffs(x1, x2), s4_coeffs(x3, x4, x5))


def evaluation_rank(func, left_arity: int, right_arity: int, left_deg: int, right_deg: int, slack: int = 8) -> dict:
    """Rank of E[i][j] = func(P_i, Q_j) with more random points than monomials on each side."""
    n_rows = (left_deg + 1) ** left_arity + slack
    n_cols = (right_deg + 1) ** right_arity + slack
    Ps = [[RNG.randrange(P) for _ in range(left_arity)] for _ in range(n_rows)]
    Qs = [[RNG.randrange(P) for _ in range(right_arity)] for _ in range(n_cols)]
    t0 = time.perf_counter()
    E = [[func(*p, *q) for q in Qs] for p in Ps]
    rank = rank_mod_p(E)
    return {"rank": rank, "eval_rows": n_rows, "eval_cols": n_cols, "monomial_rows": (left_deg + 1) ** left_arity, "monomial_cols": (right_deg + 1) ** right_arity, "seconds": round(time.perf_counter() - t0, 1)}


def s4_symbolic_crosscheck() -> dict:
    x1, x2, x3, x4, X = sp.symbols("x1 x2 x3 x4 X")

    def S3(u, v, w):
        return (u - v) ** 2 * w**2 - 2 * ((u + v) * (u * v + A_COEF) + 2 * B_COEF) * w + ((u * v - A_COEF) ** 2 - 4 * B_COEF * (u + v))

    t0 = time.perf_counter()
    S4 = sp.Poly(sp.expand(sp.resultant(S3(x1, x2, X), S3(x3, x4, X), X)), x1, x2, x3, x4)
    gens = S4.gens

    def flat(left, right):
        li = [gens.index(v) for v in left]
        ri = [gens.index(v) for v in right]
        rows, cols, ent = {}, {}, {}
        for mono, coeff in S4.terms():
            lk = tuple(mono[i] for i in li)
            rk = tuple(mono[i] for i in ri)
            rows.setdefault(lk, len(rows))
            cols.setdefault(rk, len(cols))
            ent[(rows[lk], cols[rk])] = ent.get((rows[lk], cols[rk]), 0) + int(coeff)
        M = [[0] * len(cols) for _ in rows]
        for (i, j), v in ent.items():
            M[i][j] = v
        return rank_mod_p(M)

    # Point-evaluation consistency: the symbolic S4 agrees with the numeric resultant.
    pts = [[RNG.randrange(P) for _ in range(4)] for _ in range(20)]
    agree = all(int(S4.eval(dict(zip((x1, x2, x3, x4), pt)))) % P == S4_eval(*pt) for pt in pts)
    return {
        "degree_in_each_variable": S4.degree(x1),
        "terms": len(S4.terms()),
        "balanced_rank_symbolic": flat((x1, x2), (x3, x4)),
        "one_vs_rest_rank_symbolic": flat((x1,), (x2, x3, x4)),
        "numeric_resultant_agrees_at_20_points": agree,
        "seconds": round(time.perf_counter() - t0, 2),
    }


def semaev_specialised() -> dict:
    out = {"curve": f"y^2 = x^3 + {A_COEF}x + {B_COEF}; all ranks exact mod 2^61-1 (lower bounds for the rank over Q)"}
    out["S3_one_vs_rest"] = {**evaluation_rank(S3_eval, 1, 2, 2, 2), "predicted_2^(m-2)+1": 3}
    out["S4_balanced_(x1,x2)|(x3,x4)"] = {**evaluation_rank(S4_eval, 2, 2, 4, 4), "generic_ceiling_C(4,2)": 6}
    out["S4_one_vs_rest"] = {**evaluation_rank(S4_eval, 1, 3, 4, 4), "predicted_2^(m-2)+1": 5}
    out["S4_symbolic_crosscheck"] = s4_symbolic_crosscheck()
    out["S5_balanced_(x1,x2)|(x3,x4,x5)"] = {**evaluation_rank(S5_eval, 2, 3, 8, 8), "generic_ceiling_C(6,2)": 15}
    out["S5_one_vs_rest"] = {**evaluation_rank(S5_eval, 1, 4, 8, 8), "predicted_2^(m-2)+1": 9}
    return out


def parameter_obstruction() -> list[dict]:
    rows = []
    e = 18.0 / 37.0
    for m in (4, 6, 8, 10):
        rows.append(
            {
                "m": m,
                "one_vs_rest_rank_2^(m-2)+1": 2 ** (m - 2) + 1,
                "N_lower_bound_exp_of_|H|/4": round(e, 5),
                "avw_preprocessing_exp_of_|H|/4": round((2.0 - PRE_EXP * MAX_D_EXP) * e, 5),
                "generic_rho_exp": 0.5,
            }
        )
    return rows


def main() -> None:
    generic = []
    for r, s in ((1, 1), (1, 2), (2, 2), (1, 3), (2, 3), (2, 4), (3, 3), (4, 4)):
        g = generic_rank(r, s)
        generic.append(g)
        print(f"generic (r,s)=({r},{s}): rank {g['rank']} = C({r+s},{r}) = {g['C(r+s,r)']}  rows {g['rows']} cols {g['cols']} [{g['status']}, {g['seconds']}s]", flush=True)
    ceilings = balanced_ceilings()
    for c in ceilings:
        print(f"m={c['m']}: ({c['r']},{c['s']}) ceiling {c['generic_rank_ceiling']} (2^{c['log2']})")
    spec = semaev_specialised()
    print(json.dumps(spec, indent=1))
    res = {
        "generic_ranks_exact": generic,
        "balanced_ceilings": ceilings,
        "semaev_specialised_measured": spec,
        "parameter_obstruction_derived": parameter_obstruction(),
        "hashing_note": "lifted factor-base points: group-sum hashing; x-only children: intermediate-root hashing after factorisation; both ~ list + output size, not cross-list dot products",
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fh:
        json.dump(res, fh, indent=1)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
