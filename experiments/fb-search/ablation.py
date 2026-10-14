#!/usr/bin/env python3
"""Why is the residual system's solving degree so low?  Structure ablations.

For the prefix base V = {deg < l} in a polynomial-basis field (n prime, 2l - 1 <= n), no product in the
residual system reduces, so the system is a polynomial identity over F_2[T]:

    A(T)^2 + A(T) D(t; T) + P(t; T) = 0,   deg A < l,  D(t) = u0 + sum_k t_k f_k,  P affine in t,

with 2l - 1 live coefficient equations in the l bits of A and the d bits of t (residual.py builds it;
the coordinates >= 2l - 1 vanish identically after the projection).  Each variant below replaces one
ingredient by random data of the same shape and measures the MXL refutation degree (smxl.c), on
targets where the real system is refuted:

  S   the real system;
  A1  random affine part P (u0, f_k and the convolution kept);
  A2  random u0, f_k (polynomials of degree < l) and random P: the convolution x_i t_k -> f_k T^i kept;
  A3  as A2, and the Frobenius term A^2 replaced by a random linear map of A;
  A4  generic bilinear: every x_i t_k coefficient an independent random polynomial of degree <= 2l - 2;
  A5  as A3, but the random map equals squaring on span{u0, f_k}: this restores the summand-swap symmetry
      A -> A + D of the real system (L(A + D) + (A + D) D = L(A) + A D exactly when L(D) = D^2);
  A6  control for A5: the random map equals squaring on a random subspace of the same dimension d + 1.

    python3 ablation.py --n 41 --l 16 17 --targets 6
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from residual import FactorBase, HalfTraceSolver, ToyCurve, boolean_equations, residual_systems, smxl  # noqa: E402
from toycurve import canonical  # noqa: E402

VARIANTS = ("S", "A1", "A2", "A3", "A4", "A5", "A6")
LAST_D: list = []  # (u0, f_k) of the last variant built, for fall_relations
LAST_RELATIONS: list = []  # the degree-<=2 polynomial-multiple relations of the last fall_relations call


def variant_mono(rs: dict, l: int, kind: str, rng: random.Random) -> dict[int, int]:
    """The monomial -> F_2^(2l-1) coefficient map of one variant (prefix base: v_i = T^i)."""
    d = rs["d"]
    top = (1 << (2 * l - 1)) - 1
    rnd_low = lambda: rng.getrandbits(l)          # noqa: E731  a polynomial of degree < l
    rnd_top = lambda: rng.getrandbits(2 * l - 1)  # noqa: E731  a polynomial of degree <= 2l - 2
    if kind == "S":
        LAST_D[:] = [rs["u0"], list(rs["fs"])]
        return {m: c & top for m, c in rs["mono"].items() if c & top}
    u0, fs = rs["u0"], list(rs["fs"])
    if kind in ("A2", "A3", "A5", "A6"):
        u0, fs = rnd_low(), [rnd_low() for _ in range(d)]
    LAST_D[:] = [u0, fs]
    mono: dict[int, int] = {0: rnd_top()}
    for k in range(d):
        mono[1 << (l + k)] = rnd_top()
    lin_x = [rnd_top() for _ in range(l)] if kind == "A3" else None
    if kind == "A5":
        lin_x = _swap_symmetric_map(l, [u0] + fs, rng)
    if kind == "A6":
        lin_x = _swap_symmetric_map(l, [rnd_low() for _ in range(d + 1)], rng)
    for i in range(l):
        if kind == "A4":
            mono[1 << i] = rnd_top()
        else:
            frob = lin_x[i] if kind in ("A3", "A5", "A6") else (1 << (2 * i))
            mono[1 << i] = frob ^ _polymul(u0, 1 << i)
        for k in range(d):
            mono[(1 << i) | (1 << (l + k))] = rnd_top() if kind == "A4" else _polymul(fs[k], 1 << i)
    if kind == "S":
        return mono
    return {m: c & top for m, c in mono.items() if c & top}


def _sq(a: int) -> int:
    """The square of a polynomial over F_2 (spread the bits)."""
    r, i = 0, 0
    while a:
        if a & 1:
            r |= 1 << (2 * i)
        a >>= 1
        i += 1
    return r


def _swap_symmetric_map(l: int, span: list[int], rng: random.Random) -> list[int]:
    """Images L(T^i) of a random F_2-linear map L on {deg < l} with L(f) = f^2 on span.  With span = D's
    span, L(A) + A D + P keeps the summand-swap symmetry A -> A + D and nothing else of the squaring."""
    basis: list[int] = []
    piv: dict[int, int] = {}
    images: dict[int, int] = {}
    def reduce(v: int, img: int) -> tuple[int, int]:
        while v:
            h = v.bit_length() - 1
            if h not in piv:
                break
            pv, pimg = piv[h]
            v ^= pv
            img ^= pimg
        return v, img
    for f in span + [1 << i for i in range(l)]:
        img = _sq(f) if f in span else rng.getrandbits(2 * l - 1)
        v, im = reduce(f, img)
        if v:
            piv[v.bit_length() - 1] = (v, im)
    # express each T^i in the (echelon) basis and read off L(T^i)
    out = []
    for i in range(l):
        v, img = 1 << i, 0
        while v:
            h = v.bit_length() - 1
            pv, pimg = piv[h]
            v ^= pv
            img ^= pimg
        out.append(img)
    return out


def _polymul(a: int, b: int) -> int:
    r = 0
    while b:
        if b & 1:
            r ^= a
        a <<= 1
        b >>= 1
    return r


def measure(args) -> None:
    out = open(args.out, "a") if args.out else None
    C = ToyCurve(args.n)
    for l in args.l:
        assert 2 * l - 1 <= args.n, "the prefix product must not reduce"
        fb = FactorBase(C, "prefix", l, 1)
        sv = HalfTraceSolver(fb)
        rng = random.Random(f"ablation|{args.n}|{l}")
        got = 0
        tries = 0
        while got < args.targets and tries < 200 * args.targets:
            tries += 1
            _, R = C.random_subgroup_point(rng)
            if sv.decompose(R):
                continue
            for rs in residual_systems(sv, R[0]):
                if rs["d"] < 2:
                    continue
                N = l + rs["d"]
                row = {"schema": "fb-search-ablation/1", "kind": "stage", "n": args.n, "l": l, "d": rs["d"], "N": N,
                       "eps": rs["eps"], "target_x": R[0], "degree": {}}
                for kind in args.variants:
                    eqs = boolean_equations(2 * l - 1, variant_mono(rs, l, kind, random.Random(f"{kind}|{R[0]}|{rs['eps']}")))
                    r = smxl(N, eqs, d_max=args.d_max, max_cols=args.max_cols)
                    row["degree"][kind] = r["degree"] if r["status"] == "refuted" else f">={r['degree']}" \
                        if r["status"] == "budget" else r["status"]
                    row.setdefault("cols", {})[kind] = r["cols"]
                print(f"n{args.n} l{l} d{rs['d']} eps{rs['eps']}: " + " ".join(f"{k}={row['degree'][k]}" for k in args.variants),
                      flush=True)
                if out:
                    out.write(canonical(row) + "\n")
                    out.flush()
                got += 1
                break


def _pmul(a: set[int], b: set[int]) -> set[int]:
    """Product of two multilinear Boolean polynomials (sets of monomial masks; x^2 = x)."""
    out: set[int] = set()
    for m in a:
        for k in b:
            out ^= {m | k}
    return out


def fall_relations(rs: dict, l: int, kind: str, rng: random.Random) -> dict:
    """The polynomial-multiple falls: E(T) = A^2 + A D + P (coefficient equations E_k).  A(T) E(T) and
    D(t; T) E(T) are combinations sum_i a_i E_(k-i) and sum_j d_j(t) E_(k-j) of degree-3 terms, but squaring
    is F_2-linear (A^2 = sum a_i T^(2i)), so they reduce to degree <= 2.  Returns their maximal degree and how
    many independent quadratic relations they add to span{E_k} (the degree-2 equations)."""
    mono = variant_mono(rs, l, kind, rng)
    d = rs["d"]
    E = [set() for _ in range(2 * l - 1)]
    for m, c in mono.items():
        for k in range(2 * l - 1):
            if (c >> k) & 1:
                E[k] ^= {m}
    A = [{1 << i} for i in range(l)]
    u0, fs = LAST_D
    D = []
    for j in range(l):
        dj = {0} if (u0 >> j) & 1 else set()
        for k in range(d):
            if (fs[k] >> j) & 1:
                dj ^= {1 << (l + k)}
        D.append(dj)
    rels = []
    for mult in (A, D):
        for mdeg in range(3 * l - 2):
            g: set[int] = set()
            for i, ai in enumerate(mult):
                k = mdeg - i
                if 0 <= k < 2 * l - 1 and ai and E[k]:
                    g ^= _pmul(ai, E[k])
            if g:
                rels.append(g)
    maxdeg = max((bin(m).count("1") for g in rels for m in g), default=0)
    cols: dict[int, int] = {}

    def vec(p: set[int]) -> int:
        v = 0
        for m in p:
            if m not in cols:
                cols[m] = len(cols)
            v |= 1 << cols[m]
        return v

    def rank(vs: list[int]) -> int:
        piv: dict[int, int] = {}
        for v in vs:
            while v:
                h = v.bit_length() - 1
                if h in piv:
                    v ^= piv[h]
                else:
                    piv[h] = v
                    break
        return len(piv)

    LAST_RELATIONS[:] = [sorted(g) for g in rels if g and all(bin(m).count("1") <= 2 for m in g)]
    eq_vecs = [vec(e) for e in E if e]
    r_e = rank(eq_vecs)
    r_all = rank(eq_vecs + [vec(g) for g in rels if all(bin(m).count("1") <= 2 for m in g)])
    return {"max_degree": maxdeg, "rank_E": r_e, "new_quadratics": r_all - r_e, "relations": len(rels)}


def summarize(path: Path) -> None:
    rows = [json.loads(line) for line in path.open() if line.strip()]
    print("| n | l | d | targets | " + " | ".join(f"degree {k}" for k in VARIANTS) + " |")
    print("|---|---|---|---|" + "---|" * len(VARIANTS))
    for key in sorted({(r["n"], r["l"], r["d"]) for r in rows}):
        g = [r for r in rows if (r["n"], r["l"], r["d"]) == key]
        targets = {(r["target_x"], r["eps"]) for r in g}
        cells = []
        for k in VARIANTS:
            seen: dict[tuple, str] = {}
            for r in g:
                if k in r["degree"]:
                    seen[(r["target_x"], r["eps"])] = str(r["degree"][k])
            c = Counter(seen.values())
            cells.append(", ".join(f"{v}: {c[v]}" for v in sorted(c)) or "-")
        print(f"| {key[0]} | {key[1]} | {key[2]} | {len(targets)} | " + " | ".join(cells) + " |")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=41)
    ap.add_argument("--l", type=int, nargs="+", default=[16, 17])
    ap.add_argument("--targets", type=int, default=6)
    ap.add_argument("--d-max", type=int, default=6)
    ap.add_argument("--max-cols", type=int, default=400_000)
    ap.add_argument("--out", default="")
    ap.add_argument("--summarize", default="")
    ap.add_argument("--variants", nargs="+", default=list(VARIANTS), choices=VARIANTS)
    args = ap.parse_args()
    if args.summarize:
        summarize(Path(args.summarize))
    else:
        measure(args)


if __name__ == "__main__":
    main()
