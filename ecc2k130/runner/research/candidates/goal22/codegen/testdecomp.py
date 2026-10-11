"""Checks for the SAT decomposition front end.

Three things have to hold before a decomposition result means anything: the CNF
must agree with the IR's own evaluator, the constraint encodings must mean what
they say, and S_3 must vanish on exactly the triples it should.  A silent error
in any of them yields instances that are unsatisfiable, or satisfiable by
garbage, and either way the growth curve the harness measures would be
measuring the wrong thing.

No type hints, camelCase identifiers, no itertools (project convention).
"""

import random
import sys

import build
import cnf as cnfmod
import curves
import decomp
import field
import ir


def solve(c, assumptions=()):
    from pysat.solvers import CryptoMinisat
    s = CryptoMinisat()
    for cl in c.clauses:
        s.add_clause(cl)
    for lits, rhs in c.xors:
        s.add_xor_clause(lits, rhs)
    ok = s.solve(assumptions=list(assumptions))
    m = s.get_model() if ok else None
    s.delete()
    if not ok:
        return None
    val = {}
    for l in m:
        val[abs(l)] = 1 if l > 0 else 0
    return val


def litVal(val, l):
    return val[abs(l)] if l > 0 else 1 - val[abs(l)]


def checkCircuit(report):
    """emitCnf must reproduce Prog.evaluate on the generated multiplier."""
    rng = random.Random(7)
    for n in (4, 8, 12):
        p = ir.Prog()
        a = [p.addInput('a', i) for i in range(n)]
        b = [p.addInput('b', i) for i in range(n)]
        roots = build.polyMulIr(p, a, b, 4)
        for _ in range(8):
            av = [rng.randrange(2) for _ in range(n)]
            bv = [rng.randrange(2) for _ in range(n)]
            vals = {}
            for i in range(n):
                vals[('a', i)] = av[i]
                vals[('b', i)] = bv[i]
            want = [(0 if w is None else w & 1) for w in p.evaluate(vals, roots)]
            c = cnfmod.Cnf()
            lits = {}
            for i in range(n):
                for nm, vv in (('a', av), ('b', bv)):
                    v = c.newVar()
                    lits[(nm, i)] = v
                    c.addClause([v] if vv[i] else [-v])
            outs = p.emitCnf(roots, lits, c)
            val = solve(c)
            got = [litVal(val, l) if l not in (c.true, c.false) else (1 if l == c.true else 0)
                   for l in outs]
            report('emitCnf matches evaluate, n=%d' % n, got == want)
            if got != want:
                return


def checkAtMost(report):
    """Exhaustive: atMost(k) accepts an assignment iff its weight is <= k."""
    for n in (5, 6):
        for k in (0, 1, 2, 3):
            bad = 0
            for mask in range(1 << n):
                c = cnfmod.Cnf()
                v = [c.newVar() for _ in range(n)]
                c.atMost(v, k)
                for i in range(n):
                    c.addClause([v[i]] if (mask >> i) & 1 else [-v[i]])
                got = solve(c) is not None
                want = bin(mask).count('1') <= k
                if got != want:
                    bad += 1
            report('atMost n=%d k=%d exhaustive' % (n, k), bad == 0)


def checkLexLeq(report):
    """Exhaustive: lexLeq accepts iff a <= b as bit vectors, msb first."""
    n = 4
    bad = 0
    for x in range(1 << n):
        for y in range(1 << n):
            c = cnfmod.Cnf()
            a = [c.newVar() for _ in range(n)]
            b = [c.newVar() for _ in range(n)]
            c.lexLeq(a, b)
            for i in range(n):
                c.addClause([a[i]] if (x >> (n - 1 - i)) & 1 else [-a[i]])
                c.addClause([b[i]] if (y >> (n - 1 - i)) & 1 else [-b[i]])
            if (solve(c) is not None) != (x <= y):
                bad += 1
    report('lexLeq exhaustive on %d pairs' % (1 << (2 * n)), bad == 0)


def checkS3(report):
    """S_3 vanishes on x-coordinates of points summing to O, and not otherwise."""
    for m in (11, 23):
        onb = field.Onb(m)
        cur = curves.Curve(onb)
        rng = random.Random(m)
        perm = decomp.sigmaPerm(m, onb.n, 1)
        permOk = True
        for _ in range(100):
            cc = rng.getrandbits(m)
            want = onb.toCoords(onb.sqr(onb.fromCoords(cc)))
            got = 0
            for i in range(m):
                if (cc >> i) & 1:
                    got |= 1 << perm[i]
            if got != want:
                permOk = False
        report('squaring is the sigma^1 permutation, m=%d' % m, permOk)

        prog, roots = decomp.buildSystem(m, onb.n, 2, min(12, m))

        def zero(x1, x2, x3):
            vals = {}
            for j in range(m):
                vals[('p0', j)] = (onb.toCoords(x1) >> j) & 1
                vals[('p1', j)] = (onb.toCoords(x2) >> j) & 1
                vals[('r', j)] = (onb.toCoords(x3) >> j) & 1
                vals[('one', j)] = 1
            return all((0 if w is None else w & 1) == 0
                       for w in prog.evaluate(vals, roots))

        good = wrong = accepted = 0
        for _ in range(25):
            P = Q = None
            while P is None:
                P = cur.pointFromX(onb.fromCoords(rng.getrandbits(m)))
            while Q is None:
                Q = cur.pointFromX(onb.fromCoords(rng.getrandbits(m)))
            S = cur.add(P, Q)
            if S is None:
                continue
            if zero(P[0], Q[0], S[0]):
                good += 1
            else:
                wrong += 1
            if zero(P[0], Q[0], onb.fromCoords(rng.getrandbits(m))):
                accepted += 1
        report('S_3 vanishes on %d true triples, m=%d' % (good, m), wrong == 0)
        report('S_3 rejects random third coordinates, m=%d' % m, accepted == 0)


def checkFactorBase(report):
    """The orbit count is the number of relations a run needs, so it has to be
    right.  Weight and being an x-coordinate are both preserved by the
    Frobenius, so every orbit lies wholly inside the factor base or wholly
    outside; check that, and that the orbits partition it."""
    import indexcalc
    from math import comb
    for m, w in ((11, 3), (23, 2)):
        onb = field.Onb(m)
        cur = curves.Curve(onb)
        base, orbits = indexcalc.factorBase(onb, cur, w)
        total = 0
        wholly = True
        for c in orbits:
            for d in orbits[c]:
                total += 1
                if d not in base or bin(d).count('1') != bin(c).count('1'):
                    wholly = False
        report('m=%d w=%d orbits partition the factor base (%d pts, %d orbits)'
               % (m, w, len(base), len(orbits)), total == len(base) and wholly)
        cand = sum(comb(m, k) for k in range(w + 1))
        report('m=%d w=%d factor base is a subset of the weight<=w candidates'
               % (m, w), len(base) <= cand)


def checkEndToEnd(report):
    """A target built from factor base points must decompose back to them."""
    import indexcalc
    r = indexcalc.runTrials(11, 3, 3, 3, seed=5, leaf=12, verbose=False, timeout=120)
    report('m=11 decomposition solved %d/3, %d spurious, %d unsat'
           % (r['solved'], r['spurious'], r['unsat']),
           r['solved'] == 3 and r['unsat'] == 0)


def main():
    fails = []

    def report(name, ok):
        print('  %-58s %s' % (name, 'ok' if ok else 'FAILED'))
        if not ok:
            fails.append(name)

    print('decomposition front end')
    checkCircuit(report)
    checkAtMost(report)
    checkLexLeq(report)
    checkS3(report)
    checkFactorBase(report)
    checkEndToEnd(report)
    if fails:
        print('%d failure(s)' % len(fails))
        return 1
    print('all decomposition checks passed (0 failures)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
