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
from gf2n import GF2n


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


_PREPARED: dict[tuple, dict] = {}


def prepare(n: int, mod: int, b: int, l: int) -> dict:
    """Everything in the model that does not depend on the target point R.

    The definitions of the E variables depend only on l, and the descended
    main equations are sum_{(a,b,c)} coef_abc(x_R) * D_abc where the twelve
    D_abc (the descents of e1^a e2^b e3^c) depend only on (n, l).  A
    relation-collection loop therefore prepares once per factor base and pays
    twelve field powers and about 12 * |D| field multiplications per target,
    instead of redoing the descent.
    """
    key = (n, mod, b, l)
    if key in _PREPARED:
        return _PREPARED[key]
    F = GF2n(n, mod)
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
                    bb = k - a
                    if 0 <= bb < l:
                        mono = tuple(sorted((v(i, a), v(j, bb))))
                        nonlinear.add(mono)
                        terms.append(".2 " + " ".join(var(t) for t in mono))
        lines.append("x T " + var(base[1] + k) + " " + " ".join(terms) + " 0")
    for k in range(3 * l - 2):
        terms = []
        for a in range(l):
            for bb in range(l):
                c = k - a - bb
                if 0 <= c < l:
                    mono = tuple(sorted((v(0, a), v(1, bb), v(2, c))))
                    nonlinear.add(mono)
                    terms.append(".3 " + " ".join(var(t) for t in mono))
        lines.append("x T " + var(base[2] + k) + " " + " ".join(terms) + " 0")

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

    sym = symmetrize_s4()
    exps = sorted({(a, bb, c) for a, bb, c, _, _ in sym})
    blocks = [{} for _ in range(3)]
    for i in range(3):
        for e in {t[i] for t in exps}:
            blocks[i][e] = block(e, sizes[i], base[i])
    pieces: dict[tuple[int, int, int], dict[int, int]] = {}
    for a, bb, c in exps:
        d: dict[int, int] = {}
        for m1, c1 in blocks[0][a].items():
            for m2, c2 in blocks[1][bb].items():
                c12 = F.mul(c1, c2)
                for m3, c3 in blocks[2][c].items():
                    d[m1 | m2 | m3] = F.mul(c12, c3)  # disjoint blocks: no collisions
        pieces[(a, bb, c)] = d

    prepared = {
        "F": F,
        "b": b,
        "l": l,
        "n": n,
        "nvars": nvars,
        "definitions": lines,
        "nonlinear_defs": nonlinear,
        "sym": sym,
        "pieces": pieces,
    }
    _PREPARED[key] = prepared
    return prepared


def build_model(inst: Instance) -> tuple[list[str], dict]:
    """WDSat ANF lines for the symmetrised model of a planted m = 3 instance, plus size info."""
    assert inst.m == 3
    prep = prepare(inst.n, inst.mod, inst.b, inst.l)
    F = prep["F"]
    l, n = inst.l, inst.n
    nvars = prep["nvars"]
    lines: list[str] = list(prep["definitions"])
    nonlinear: set[tuple[int, ...]] = set(prep["nonlinear_defs"])

    def var(idx: int) -> str:
        return str(idx + 1)

    # main equations: sum over the twelve pieces with the target-dependent coefficients
    coef: dict[tuple[int, int, int], int] = {}
    for a, bb, c, ex4, eb in prep["sym"]:
        val = F.mul(F.pow(inst.xR, ex4), F.pow(inst.b, eb))
        coef[(a, bb, c)] = coef.get((a, bb, c), 0) ^ val
    anf: dict[int, int] = {}
    for key, cc in coef.items():
        if not cc:
            continue
        tab = MulTable(F, cc)
        for mask, val in prep["pieces"][key].items():
            anf[mask] = anf.get(mask, 0) ^ tab(val)
    anf = {mk: val for mk, val in anf.items() if val}

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
