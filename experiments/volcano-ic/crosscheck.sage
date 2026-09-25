# Algebraic cross-checks for the n=19 volcano study.
#
#   sage crosscheck.sage
#
# 1. Frobenius data for y^2 + xy = x^3 + 1 over F_2^19 and F_2^131 (ECC2K-130):
#    trace, group order, [O_K : Z[pi]] and every level of the isogeny class.
# 2. Frobenius-stable F_2-subspaces of F_2^n, from the factorization of x^n - 1.
# 3. Where b sits after Weil descent of S3 and S4. x^(2^k) is linear over F_2,
#    so x1^e1 x2^e2 ... descends to degree wt(e1) + wt(e2) + ... in the bits.
# 4. Formal degree of regularity (topDegreeDreg in ic.sage) on real systems,
#    random bilinear systems and random quadratic systems of the same size.
# 5. Every PolyBoRi solution of the S3 system for random E0 targets and for
#    targets built to have an x = 0 (2-torsion) solution.
#
# Writes results/crosscheck-algebra.json.

import random

load(os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), 'run.sage'))
START = time.time()


def progress(label, value):
    print('[%6.0fs] %s: %s' % (time.time() - START, label, value), flush=True)


def koblitz(n):
    """tau^2 + tau + 2 = 0; t_n = tau^n + taubar^n and f_n = |U_n| = [O_K : Z[tau^n]]."""
    t0, t1, u0, u1 = 2, -1, 0, 1
    for _ in range(n - 1):
        t0, t1 = t1, -t1 - 2 * t0
        u0, u1 = u1, -u1 - 2 * u0
    q = 2 ** n
    t, f = t1, abs(u1)
    assert f ** 2 * 7 == 4 * q - t ** 2
    primes = [ell for ell, _ in factor(f)]
    levels = []
    for c in divisors(f):
        # h(Z + c O_K) = c * prod_{ell | c} (1 - (-7/ell)/ell); O_K^* = {+-1}.
        h = c * prod(1 - kronecker(-7, ell) / ell for ell, _ in factor(c)) if c > 1 else 1
        levels.append({'conductor': str(c), 'class_number': str(h)})
    size = sum(ZZ(l['class_number']) for l in levels)
    return {'n': n, 'trace': str(t), 'order': str(factor(q + 1 - t)),
            'frobenius_conductor': str(factor(f)),
            'primes': [{'ell': str(ell), 'bits': float(log(ell, 2)), 'kronecker_minus7': int(kronecker(-7, ell)),
                        'descendants_one_step_below_E0': str(ell - kronecker(-7, ell)),
                        'frobenius_orbits': str((ell - kronecker(-7, ell)) / n)} for ell in primes],
            'levels': levels, 'isogeny_class_size': str(size), 'isogeny_class_log2': float(log(size, 2))}


def stableSubspaces(n):
    X = polygen(GF(2))
    return {'n': n, 'ord_n_2': int(Mod(2, n).multiplicative_order()),
            'factor_degrees_x^n-1': sorted(int(g.degree()) for g, _ in factor(X ** n - 1))}


def bitDegrees():
    R.<b, xR, x1, x2, x3, Y> = GF(2)[]
    S3 = lambda u, v, w: (u * v) ** 2 + w ** 2 * (u ** 2 + v ** 2) + w * u * v + b
    wt = lambda e: bin(e).count('1')
    out = {}
    for name, S, xs in [('S3', S3(x1, x2, xR), [x1, x2]),
                        ('S4', S3(x1, x2, Y).resultant(S3(x3, xR, Y), Y), [x1, x2, x3])]:
        idx = [R.gens().index(v) for v in xs]
        byDeg = {}
        for mon, c in S.dict().items():
            byDeg.setdefault(sum(wt(mon[i]) for i in idx), []).append(mon)
        top = max(byDeg)
        topPart = sum(R.monomial(*mon) for mon in byDeg[top])
        out[name] = {'bit_degrees': sorted(byDeg), 'top_bit_degree': top, 'top_part': str(topPart.factor()),
                     'bit_degrees_with_b': sorted(d for d, mons in byDeg.items() if any(m[0] > 0 for m in mons))}
    return out


def hilbertCoefficients(fld, polys):
    """Coefficients of the Hilbert series used by topDegreeDreg."""
    P = PolynomialRing(GF(2), 2 * fld.k, 'v')
    v = P.gens()
    gens = [x ** 2 for x in v]
    for f in polys:
        d = f.deg()
        if d > 0:
            gens.append(sum(P.prod(v[i] for i in m.iterindex()) for m in f.terms() if m.deg() == d))
    ser = P.ideal(gens).hilbert_series()
    quo, rem = ser.numerator().quo_rem(ser.denominator())
    assert rem == 0
    return [int(c) for c in quo.list()]


def semiRegularDreg(n, m):
    """First non-positive coefficient of (1 + t)^n / (1 + t^2)^m: the Boolean
    semi-regular degree of regularity for m quadratic equations in n variables."""
    t = PowerSeriesRing(ZZ, 't', default_prec=n + 2).gen()
    s = ((1 + t) ** n / (1 + t ** 2) ** m).list()
    return next(d for d, c in enumerate(s) if c <= 0)


def dregControls(fld, cur, P, real=3, bilinearCount=2, quadraticCount=1):
    """Dense random systems are far slower than the sparse real ones (about
    1 min per bilinear and 8 min per quadratic system on an M-series core)."""
    rng = random.Random('crosscheck-dreg')
    B, u, w = fld.B, fld.u, fld.w
    bit = lambda: rng.randrange(2)
    lin = lambda: sum(bit() * x for x in u + w) + bit()
    def bilinear():
        return [sum(bit() * u[i] * w[j] for i in range(fld.k) for j in range(fld.k)) + lin() for _ in range(fld.n)]
    def quadratic():
        g = list(u) + list(w)
        return [sum(bit() * g[i] * g[j] for i in range(len(g)) for j in range(i + 1, len(g))) + lin() for _ in range(fld.n)]
    out = {'e0_systems': []}
    for _ in range(real):
        R = rng.randrange(1, int(cur.p)) * P
        polys = [f for f in fld.system(R[0], cur.b) if f != 0]
        h = hilbertCoefficients(fld, polys)
        out['e0_systems'].append({'dreg': int(topDegreeDreg(fld, polys)), 'h10': h[10] if len(h) > 10 else 0})
    progress('dreg: E0 systems', out['e0_systems'])
    out['random_bilinear'] = []
    for _ in range(bilinearCount):
        out['random_bilinear'].append(int(topDegreeDreg(fld, bilinear())))
        progress('dreg: random bilinear', out['random_bilinear'])
    out['random_quadratic'] = []
    for _ in range(quadraticCount):
        out['random_quadratic'].append(int(topDegreeDreg(fld, quadratic())))
        progress('dreg: random quadratic', out['random_quadratic'])
    # Square-free monomials in the x1 bits (or x2 bits) alone of degree 10: the floor on h(10).
    out['pure_monomial_floor_h10'] = 2
    out['semi_regular_dreg_n20_m19'] = semiRegularDreg(2 * fld.k, fld.n)
    return out


def classify(fld, cur, R, tg=None):
    polys = [f for f in fld.system(R[0], cur.b) if f != 0]
    I = ideal(polys)
    sols = I.variety() if I.groebner_basis() != [1] else []
    out = {'genuine': 0, 'x_is_zero': 0, 'other': 0}
    for s in sols:
        x1 = fld.fromBits([s[g] for g in fld.u])
        x2 = fld.fromBits([s[g] for g in fld.w])
        if x1 == 0 or x2 == 0:
            out['x_is_zero'] += 1
        elif x1 in cur.fb and x2 in cur.fb and any(s1 * cur.fb[x1] + s2 * cur.fb[x2] == R
                                                   for s1 in (1, -1) for s2 in (1, -1)):
            out['genuine'] += 1
        else:
            out['other'] += 1
    return out


def spurious(fld, cur, P, randomTargets=200, built=5):
    rng = random.Random('crosscheck-spurious')
    total = {'genuine': 0, 'x_is_zero': 0, 'other': 0}
    for _ in range(randomTargets):
        for k, v in classify(fld, cur, rng.randrange(1, int(cur.p)) * P).items():
            total[k] += v
    # x(P + T2) = sqrt(b) / x(P): for P in the factor base with tag 2, R = P + T2
    # is in the prime subgroup and (0, x(P)), (x(P), 0) solve its S3 system.
    tg = tags(cur)
    T2 = cur.E.lift_x(cur.fld.F(0))
    builtRows = []
    for x in [x for x in cur.xs if tg[x] == 2][:built]:
        R = cur.fb[x] + T2
        assert cur.p * R == 0
        builtRows.append(classify(fld, cur, R))
    return {'random_targets': randomTargets, 'random': total, 'built_targets': builtRows}


def main():
    out = {'koblitz': [koblitz(19), koblitz(131)],
           'frobenius_stable_subspaces': [stableSubspaces(19), stableSubspaces(131)],
           'weil_descent_bit_degrees': bitDegrees()}
    progress('conductors, subspaces, bit-degrees', 'done')
    fld = Field(N_BITS, MODULUS, K)
    cur = Curve(fld, 0, fld.F(1), ORDER, COFACTOR)
    P = generator(cur, 'E0')
    out['s3_solutions_polybori'] = spurious(fld, cur, P)
    progress('PolyBoRi S3 solutions', out['s3_solutions_polybori']['random'])
    out['dreg_controls'] = dregControls(fld, cur, P)
    with open(os.path.join(HERE, 'results', 'crosscheck-algebra.json'), 'w') as fh:
        json.dump(out, fh, indent=2, default=plain)
    print(json.dumps(out, indent=2, default=plain))


main()
