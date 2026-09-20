"""The symmetrised point-decomposition model of Trimoska–Ionica–Dequen for m = 3,
written in WDSat's ANF format.

S_4(x1, x2, x3, x_R) is symmetric in x1, x2, x3, so it is a polynomial in the
elementary symmetric polynomials

    e1 = x1 + x2 + x3,  e2 = x1 x2 + x1 x3 + x2 x3,  e3 = x1 x2 x3.

With x_i = sum_{j<l} v_ij z^j and no reduction modulo the field polynomial
(3l - 2 <= n), e1 has l coefficients (linear in the v), e2 has 2l - 1
(quadratic) and e3 has 3l - 2 (cubic).  The model has the m*l core variables
v, the 6l - 3 coefficient variables E of e1, e2, e3 defined by those
polynomials, and the n equations of the Weil descent of S_4(e1, e2, e3, x_R)
in the E variables, which have degree at most 3.  Every non-core variable is
determined by the core ones through a single XOR equation, which is what lets
WDSat branch on the core variables only.

This is the model of https://eprint.iacr.org/2019/313, reproduced from the
paper's description; the degrees and sizes match its Table 1.
"""

from __future__ import annotations

from collections import defaultdict

import sumpoly
from descend import Instance, MulTable
from gf2n import Curve, GF2n


def symmetrize_s4() -> dict[tuple[int, int, int, int, int], int]:
    """S_4 as {(a, b, c, e_x4, e_b): 1}, meaning e1^a e2^b e3^c x4^e_x4 b^e_b."""
    S4 = sumpoly.load(4)[4]
    # work in 8-tuples; keep only x1..x4 and b (indices 0..3, B)
    B = sumpoly.B
    rest = {}
    for mono in S4:
        key = (mono[0], mono[1], mono[2], mono[3], mono[B])
        rest[key] = rest.get(key, 0) ^ 1
    rest = {k: 1 for k, c in rest.items() if c}

    def mul(p: dict, q: dict) -> dict:
        out: dict = {}
        for a in p:
            for b in q:
                k = tuple(x + y for x, y in zip(a, b))
                out[k] = out.get(k, 0) ^ 1
        return {k: 1 for k, c in out.items() if c}

    x1 = {(1, 0, 0): 1}
    x2 = {(0, 1, 0): 1}
    x3 = {(0, 0, 1): 1}
    add = lambda p, q: {k: 1 for k in set(p) ^ set(q)}
    e1 = add(add(x1, x2), x3)
    e2 = add(add(mul(x1, x2), mul(x1, x3)), mul(x2, x3))
    e3 = mul(mul(x1, x2), x3)
    epow: dict[tuple[int, int, int], dict] = {}

    def e_mono(a: int, b: int, c: int) -> dict:
        if (a, b, c) not in epow:
            p = {(0, 0, 0): 1}
            for _ in range(a):
                p = mul(p, e1)
            for _ in range(b):
                p = mul(p, e2)
            for _ in range(c):
                p = mul(p, e3)
            epow[(a, b, c)] = p
        return epow[(a, b, c)]

    out: dict[tuple[int, int, int, int, int], int] = {}
    # group by (x4 exponent, b exponent); each group is symmetric in x1..x3
    groups: dict[tuple[int, int], set] = defaultdict(set)
    for i, j, k, x4, eb in rest:
        groups[(x4, eb)].add((i, j, k))
    for (x4, eb), monos in groups.items():
        cur = set(monos)
        while cur:
            i, j, k = max(cur, key=lambda t: tuple(sorted(t, reverse=True)))
            a_, b_, c_ = sorted((i, j, k), reverse=True)
            a, b, c = a_ - b_, b_ - c_, c_
            out[(a, b, c, x4, eb)] = out.get((a, b, c, x4, eb), 0) ^ 1
            cur ^= set(e_mono(a, b, c))
    out = {k: 1 for k, v in out.items() if v}
    return out


def build_model(inst: Instance) -> tuple[list[str], dict]:
    """WDSat ANF lines for the symmetrised model of a planted m = 3 instance, plus size info."""
    assert inst.m == 3
    F = GF2n(inst.n, inst.mod)
    E = Curve(F, inst.b)
    l, n = inst.l, inst.n
    assert 3 * l - 2 <= n, "e3 must not wrap around the field polynomial"
    sizes = [l, 2 * l - 1, 3 * l - 2]
    base = [3 * l, 4 * l, 6 * l - 1]  # first variable index (0-based) of E1, E2, E3
    nvars = 6 * l - 3 + 3 * l

    lines: list[str] = []
    nonlinear: set[tuple[int, ...]] = set()

    def var(idx: int) -> str:
        return str(idx + 1)

    def v(i: int, j: int) -> int:
        return i * l + j

    # definitions: E1_k = sum_i v_ik ; E2_k = sum_{i<j} sum_{a+b=k} v_ia v_jb ; E3_k = sum_{a+b+c=k} v_0a v_1b v_2c
    for k in range(l):
        lines.append(
            "x T "
            + var(base[0] + k)
            + " "
            + " ".join(var(v(i, k)) for i in range(3))
            + " 0"
        )
    for k in range(2 * l - 1):
        terms = []
        for i in range(3):
            for j in range(i + 1, 3):
                for a in range(l):
                    b = k - a
                    if 0 <= b < l:
                        mono = tuple(sorted((v(i, a), v(j, b))))
                        nonlinear.add(mono)
                        terms.append(".2 " + " ".join(var(t) for t in mono))
        lines.append("x T " + var(base[1] + k) + " " + " ".join(terms) + " 0")
    for k in range(3 * l - 2):
        terms = []
        for a in range(l):
            for b in range(l):
                c = k - a - b
                if 0 <= c < l:
                    mono = tuple(sorted((v(0, a), v(1, b), v(2, c))))
                    nonlinear.add(mono)
                    terms.append(".3 " + " ".join(var(t) for t in mono))
        lines.append("x T " + var(base[2] + k) + " " + " ".join(terms) + " 0")

    # main equations: descend S4(e1, e2, e3, xR) in the E variables
    sym = symmetrize_s4()
    coef: dict[tuple[int, int, int], int] = {}
    for a, b, c, ex4, eb in sym:
        val = F.mul(F.pow(inst.xR, ex4), F.pow(E.b, eb))
        coef[(a, b, c)] = coef.get((a, b, c), 0) ^ val
    coef = {k: c for k, c in coef.items() if c}

    def block(e: int, size: int, offset: int) -> dict[int, int]:
        """Descent of e^e for e = sum_{k<size} E_k z^k, as {mask over global variable indices: coeff}."""
        poly = {0: 1}
        k = 0
        ee = e
        while ee:
            if ee & 1:
                lin = [(1 << (offset + j), F.frob(1 << j, k)) for j in range(size)]
                nxt: dict[int, int] = {}
                for mask, cc in poly.items():
                    for vm, zc in lin:
                        nm = mask | vm
                        nxt[nm] = nxt.get(nm, 0) ^ F.mul(cc, zc)
                poly = {mk: cc for mk, cc in nxt.items() if cc}
            ee >>= 1
            k += 1
        return poly

    maxe = [max(k[i] for k in coef) for i in range(3)]
    blocks = [
        {e: block(e, sizes[i], base[i]) for e in range(maxe[i] + 1)} for i in range(3)
    ]
    tables = [
        {
            e: {mk: MulTable(F, cc) for mk, cc in blk.items()}
            for e, blk in blocks[i].items()
        }
        for i in range(3)
    ]
    A: dict[tuple[int, tuple[int, ...]], int] = {(0, k): c for k, c in coef.items()}
    for i in range(3):
        nxt: dict[tuple[int, tuple[int, ...]], int] = {}
        for (mask, rest), val in A.items():
            e, rest2 = rest[0], rest[1:]
            for bm, tab in tables[i][e].items():
                key = (mask | bm, rest2)
                nxt[key] = nxt.get(key, 0) ^ tab(val)
        A = {k: c for k, c in nxt.items() if c}
    anf = {mask: val for (mask, _), val in A.items()}

    eqs: list[set[int]] = [set() for _ in range(n)]
    for mask, cc in anf.items():
        t = 0
        while cc:
            if cc & 1:
                eqs[t].add(mask)
            cc >>= 1
            t += 1
    maxdeg = 3
    for eq in eqs:
        terms = [] if 0 in eq else ["T"]
        for mk in sorted(eq):
            if mk == 0:
                continue
            lits = [j for j in range(nvars) if (mk >> j) & 1]
            if len(lits) == 1:
                terms.append(var(lits[0]))
            else:
                nonlinear.add(tuple(lits))
                maxdeg = max(maxdeg, len(lits))
                terms.append(f".{len(lits)} " + " ".join(var(t) for t in lits))
        lines.append("x " + " ".join(terms) + " 0")

    header = f"p cnf {nvars} {len(lines)}"
    info = {
        "nvars": nvars,
        "core": 3 * l,
        "definitions": 6 * l - 3,
        "nonlinear": len(nonlinear),
        "maxdeg": maxdeg,
        "max_terms": max(ln.count(" .") + ln.count(" ") for ln in lines),
        "or_clauses": sum(len(m) + 1 for m in nonlinear),
        "anf_monomials": len(anf),
    }
    return [header, *lines], info


def check_model(inst: Instance) -> bool:
    """Evaluate the model at the planted core assignment: every line must hold."""
    lines, info = build_model(inst)
    nvars = int(lines[0].split()[2])
    l = inst.l
    assign = [0] * nvars
    for j in range(3 * l):
        assign[j] = (inst.planted >> j) & 1
    # the first 6l-3 lines define one new variable each, in order; the rest must hold
    for idx, ln in enumerate(lines[1:]):
        toks = ln.split()[1:-1]
        val = 0
        i = 0
        terms = []
        while i < len(toks):
            if toks[i] == "T":
                val ^= 1
                i += 1
            elif toks[i].startswith("."):
                d = int(toks[i][1:])
                terms.append([int(t) - 1 for t in toks[i + 1 : i + 1 + d]])
                i += 1 + d
            else:
                terms.append([int(toks[i]) - 1])
                i += 1
        defined = None
        if idx < info["definitions"]:
            defined = terms.pop(0)[0]
        for t in terms:
            prod = 1
            for j in t:
                prod &= assign[j]
            val ^= prod
        # an 'x' line is a clause that must be TRUE
        if defined is not None:
            assign[defined] = val ^ 1
        elif val != 1:
            return False
    return True


if __name__ == "__main__":
    import sys
    import time

    from descend import make_instance

    n, l = int(sys.argv[1]), int(sys.argv[2])
    t0 = time.time()
    inst = make_instance(n, 3, l, seed=1)
    lines, info = build_model(inst)
    print(
        info,
        f"built in {time.time() - t0:.1f}s",
        "planted OK" if check_model(inst) else "PLANTED FAILS",
    )
