# Point decomposition for index calculus on the Koblitz curve y^2+xy = x^3+1.
#
# Given a target R, find factor base points with R = P_1 + ... + P_k.  The
# system is built from Semaev's third summation polynomial, chained rather than
# resolved: S_{k+1} has degree 2^{k-1} per variable and is useless past k=3, so
# introduce the intermediate sums instead and constrain each link with
#
#     S_3(u,v,w) = (uv + uw + vw)^2 + uvw + b = 0
#
# which vanishes exactly when some points with those x-coordinates sum to O.
# For k points that is k-1 copies of S_3 over k-2 intermediate unknowns.
#
# Two things make this cheap in the ONB the rest of the repo already uses.
# Squaring is sigma^1, a permutation of coordinates, so the square in S_3 costs
# nothing -- in a polynomial basis it would be m^2 XORs per link.  And the
# multiplication is the generated Karatsuba circuit, so a link costs four times
# the circuit's bit-operation count rather than m^3 AND terms.
#
# The factor base is {P : HW(x(P)) <= w} in the normal basis.  Weight is
# invariant under the Frobenius because sigma permutes coordinates, so the
# factor base is Frobenius stable for every m -- unlike a stable *subspace*,
# which is a binary cyclic code of length m and therefore does not exist for
# m = 131 or 163, where 2 is primitive mod m and the only cyclic codes are
# trivial.  A weight bound is not a low-degree algebraic condition, so a
# Groebner descent cannot use it; a cardinality constraint costs O(mw) clauses.
#
# Note on symmetry: applying sigma to a decomposition of R gives a decomposition
# of sigma(R), not of R, and the relation it yields is lambda times the original
# and so linearly dependent.  There is no Frobenius symmetry to break inside one
# instance.  The Frobenius pays elsewhere: factor base columns are orbits, so a
# run needs |F|/m relations rather than |F|.  What is breakable here is the k!
# orderings of the same multiset of points.
#
# No type hints, camelCase identifiers, no itertools (project convention).

import build
import ir


def sigmaPerm(m, nring, k):
    """Where coordinate i lands under the k-th Frobenius power.

    This is sigmaDest from include/fieldbs.h; squaring is k=1."""
    e = pow(2, k, nring)
    perm = []
    for i in range(m):
        t = ((i + 1) * e) % nring
        perm.append((t if t <= m else nring - t) - 1)
    return perm


def applyPerm(vals, perm):
    out = [None] * len(vals)
    for i in range(len(vals)):
        out[perm[i]] = vals[i]
    return out


def onbMul(prog, a, b, m, leaf):
    """One ONB multiplication as IR: basis change in, Karatsuba, change out.

    Hash-consing in Prog shares the basis change of an operand that appears in
    more than one product, which in S_3 is every operand."""
    pa = build.multPrepIr(prog, a, m)
    pb = build.multPrepIr(prog, b, m)
    return build.toOnbIr(prog, build.polyMulIr(prog, pa, pb, leaf), m)


def s3Ir(prog, u, v, w, m, leaf, sqp, oneVec):
    """Roots of S_3(u,v,w); all m must be zero for the link to hold."""
    uv = onbMul(prog, u, v, m, leaf)
    uw = onbMul(prog, u, w, m, leaf)
    vw = onbMul(prog, v, w, m, leaf)
    s = []
    for i in range(m):
        s.append(prog.xorList([uv[i], uw[i], vw[i]]))
    sq = applyPerm(s, sqp)                       # the square: no gates
    uvw = onbMul(prog, uv, w, m, leaf)
    out = []
    for i in range(m):
        out.append(prog.xorList([sq[i], uvw[i], oneVec[i]]))
    return out


def buildSystem(m, nring, points, leaf):
    """IR for the chained decomposition of `points` factor base points.

    Inputs are 'p<i>' for the points, 't<j>' for the intermediate sums, 'r' for
    the target and 'one' for the curve constant.  Returns (prog, roots)."""
    prog = ir.Prog()
    sqp = sigmaPerm(m, nring, 1)
    p = []
    for i in range(points):
        p.append([prog.addInput('p%d' % i, j) for j in range(m)])
    t = []
    for j in range(points - 2):
        t.append([prog.addInput('t%d' % j, k) for k in range(m)])
    r = [prog.addInput('r', j) for j in range(m)]
    one = [prog.addInput('one', j) for j in range(m)]

    chain = list(t) + [r]                        # what each link produces
    roots = []
    left = p[0]
    for i in range(points - 1):
        out = chain[i]
        roots.extend(s3Ir(prog, left, p[i + 1], out, m, leaf, sqp, one))
        left = out
    return prog, roots


def encode(prog, roots, m, points, weight, xrBits, cnf, orderPoints=True):
    """Tseitin the system into `cnf` and add the factor base constraints.

    Returns the point variables, so a model can be decoded back to x-coords."""
    lits = {}
    pvars = []
    for i in range(points):
        v = [cnf.newVar() for _ in range(m)]
        pvars.append(v)
        for j in range(m):
            lits[('p%d' % i, j)] = v[j]
        cnf.atMost(v, weight)
    for j in range(points - 2):
        for k in range(m):
            lits[('t%d' % j, k)] = cnf.newVar()
    for j in range(m):
        lits[('r', j)] = cnf.true if (xrBits >> j) & 1 else cnf.false
        lits[('one', j)] = cnf.true              # 1 is all-ones in a normal basis
    for lit in prog.emitCnf(roots, lits, cnf):
        cnf.assertZero(lit)
    if orderPoints:
        # the k points are a multiset, so pin one ordering of the k! that
        # describe the same decomposition
        for i in range(points - 1):
            cnf.lexLeq(pvars[i], pvars[i + 1])
    return pvars
