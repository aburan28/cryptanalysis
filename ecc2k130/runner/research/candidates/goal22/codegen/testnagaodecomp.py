"""Independent checks of the restricted Nagao/Riemann--Roch frontends.

    python3 testnagaodecomp.py
    python3 testnagaodecomp.py --solver

The default suite needs only the standard library.  --solver also checks
actual CNF/XOR satisfiability with the existing CryptoMiniSat binding.
No type hints, camelCase identifiers, no itertools (project convention).
"""

import random
import sys
import unittest

import cnf as cnfmod
import curves
import decomp
import field
import nagaodecomp as nagao


WITH_SOLVER = '--solver' in sys.argv
if WITH_SOLVER:
    sys.argv.remove('--solver')


def fixture(m=5):
    f = field.Onb(m)
    curve = curves.Curve(f)
    pts = []
    for x in range(1, min(1 << m, 80)):
        p = curve.pointFromX(f.fromCoords(x))
        if p is not None:
            pts.append(p)
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            for k in range(j + 1, len(pts)):
                chosen = [pts[i], pts[j], pts[k]]
                target = curve.add(curve.add(chosen[0], chosen[1]), chosen[2])
                if target is None or target[0] == 0:
                    continue
                cert = nagao.certificateForPoints(f, curve, chosen, target)
                if cert is not None:
                    return f, curve, chosen, target, cert
    raise AssertionError('no restricted fixture found')


def rootsZero(prog, roots, m, cert, target, f):
    vals = nagao.inputValues(m, cert, f.toCoords(target[0]), f.toCoords(target[1]))
    return not any(prog.evaluate(vals, roots))


def solve(c, assumptions=()):
    from pysat.solvers import CryptoMinisat
    solver = CryptoMinisat()
    try:
        for clause in c.clauses:
            solver.add_clause(clause)
        for lits, rhs in c.xors:
            solver.add_xor_clause(lits, rhs)
        solver.conf_budget(100000)
        solver.time_budget(10)
        ok = solver.solve_limited(assumptions=list(assumptions))
        if ok is None:
            raise AssertionError('tiny test exhausted its solver budget')
        if not ok:
            return None
        return {abs(lit): int(lit > 0) for lit in solver.get_model()}
    finally:
        solver.delete()


def pin(vector, value):
    return [lit if (value >> j) & 1 else -lit for j, lit in enumerate(vector)]


def pinCertificate(variables, cert):
    assumptions = pin(variables['a'], cert['a']) + pin(variables['b'], cert['b'])
    for v, value in zip(variables['pvars'], cert['xs']):
        assumptions.extend(pin(v, value))
    for v, value in zip(variables['yvars'], cert['ys']):
        assumptions.extend(pin(v, value))
    return assumptions


class NagaoArithmeticTests(unittest.TestCase):
    def testSignedTripleCertificatesAndBothCircuits(self):
        checked = 0
        for m in (5, 11):
            f, curve, _, _, _ = fixture(m)
            programs = {name: nagao.buildSystem(m, f.n, min(m, 12), name)
                        for name in nagao.FORMULATIONS}
            pts = []
            for x in range(1, 1 << m):
                p = curve.pointFromX(f.fromCoords(x))
                if p is not None:
                    pts.append(p)
                    if len(pts) == 7:
                        break
            for i in range(len(pts)):
                for j in range(i + 1, len(pts)):
                    for k in range(j + 1, len(pts)):
                        for mask in range(8):
                            chosen = [pts[i], pts[j], pts[k]]
                            chosen = [curve.neg(p) if (mask >> z) & 1 else p
                                      for z, p in enumerate(chosen)]
                            target = curve.add(curve.add(chosen[0], chosen[1]), chosen[2])
                            if target is None:
                                continue
                            xs = [p[0] for p in chosen] + [target[0]]
                            if len(set(xs)) != 4:
                                continue
                            cert = nagao.certificateForPoints(f, curve, chosen, target)
                            self.assertIsNotNone(cert)
                            for name, (prog, roots) in programs.items():
                                self.assertTrue(rootsZero(prog, roots, m, cert, target, f), name)
                                decoded = dict(cert)
                                if name == 'norm':
                                    decoded['ys'] = []
                                witness = nagao.reconstructWitness(f, curve, decoded, target)
                                self.assertIsNotNone(witness)
                                self.assertEqual(witness['points'], chosen)
                            checked += 1
        self.assertGreater(checked, 300)

    def testFullCoefficientCensusAgainstGroupLaw(self):
        # Exhaust all 32*31 monic functions through one target over GF(32).
        # Recover their zeros directly using y=(x^2+a*x+c)/b; no generated
        # equations, Semaev polynomials, or planted decomposition is used.
        f, curve, _, target, _ = fixture()
        programs = {name: nagao.buildSystem(f.m, f.n, f.m, name)
                    for name in nagao.FORMULATIONS}
        nr = curve.neg(target)
        checked = 0
        for ac in range(1 << f.m):
            for bc in range(1, 1 << f.m):
                a, b = f.fromCoords(ac), f.fromCoords(bc)
                c = f.add(f.add(f.sqr(target[0]), f.mul(a, target[0])), f.mul(b, nr[1]))
                binv = f.inv(b)
                pts = []
                for xc in range(1, 1 << f.m):
                    x = f.fromCoords(xc)
                    if x == target[0]:
                        continue
                    y = f.mul(f.add(f.add(f.sqr(x), f.mul(a, x)), c), binv)
                    if curve.onCurve((x, y)):
                        pts.append((x, y))
                self.assertLessEqual(len(pts), 3)
                if len(pts) != 3:
                    continue
                total = curve.add(curve.add(pts[0], pts[1]), pts[2])
                self.assertEqual(total, target)
                decoded = {'xs': [f.toCoords(p[0]) for p in pts],
                           'ys': [f.toCoords(p[1]) for p in pts], 'a': ac, 'b': bc}
                for name, (prog, roots) in programs.items():
                    self.assertTrue(rootsZero(prog, roots, f.m, decoded, target, f), name)
                checked += 1
        self.assertGreater(checked, 10)

    def testArbitraryIncidenceInputsAgainstFieldArithmetic(self):
        f, curve, _, target, _ = fixture()
        prog, roots = nagao.buildSystem(f.m, f.n, f.m, 'incidence')
        rng = random.Random(91823)
        for _ in range(80):
            cert = {'xs': [rng.randrange(1 << f.m) for _ in range(3)],
                    'ys': [rng.randrange(1 << f.m) for _ in range(3)],
                    'a': rng.randrange(1 << f.m), 'b': rng.randrange(1 << f.m)}
            a, b = f.fromCoords(cert['a']), f.fromCoords(cert['b'])
            c = f.add(f.add(f.sqr(target[0]), f.mul(a, target[0])),
                      f.mul(b, curve.neg(target)[1]))
            want = []
            for xc, yc in zip(cert['xs'], cert['ys']):
                x, y = f.fromCoords(xc), f.fromCoords(yc)
                curveValue = f.add(f.add(f.sqr(y), f.mul(x, y)),
                                   f.add(f.mul(f.sqr(x), x), f.one()))
                incidence = f.add(f.add(f.sqr(x), f.mul(a, x)), f.add(c, f.mul(b, y)))
                for value in (curveValue, incidence):
                    coords = f.toCoords(value)
                    want.extend((coords >> j) & 1 for j in range(f.m))
            vals = nagao.inputValues(f.m, cert, f.toCoords(target[0]), f.toCoords(target[1]))
            self.assertEqual(prog.evaluate(vals, roots), want)

    def testNormCoefficientsAgainstIndependentPointwiseNorm(self):
        # A degree <=4 polynomial is fixed by evaluations at five distinct
        # field elements.  Compare generated coefficient residuals with the
        # direct norm (g+b*y)*(g+b*(y+X)), substituting the curve equation.
        f, _, _, target, _ = fixture()
        prog, roots = nagao.buildSystem(f.m, f.n, f.m, 'norm')
        rng = random.Random(734)
        for _ in range(60):
            cert = {'xs': [rng.randrange(1 << f.m) for _ in range(3)],
                    'ys': [], 'a': rng.randrange(1 << f.m), 'b': rng.randrange(1 << f.m)}
            vals = nagao.inputValues(f.m, cert, f.toCoords(target[0]), f.toCoords(target[1]))
            bits = prog.evaluate(vals, roots)
            residual = [f.fromCoords(sum(bits[i * f.m + j] << j for j in range(f.m)))
                        for i in range(4)]
            a, b = f.fromCoords(cert['a']), f.fromCoords(cert['b'])
            c = f.add(f.add(f.sqr(target[0]), f.mul(a, target[0])),
                      f.mul(b, f.add(*target)))
            for zc in range(5):
                z = f.fromCoords(zc)
                g = f.add(f.add(f.sqr(z), f.mul(a, z)), c)
                norm = f.add(f.add(f.sqr(g), f.mul(f.mul(b, z), g)),
                             f.mul(f.sqr(b), f.add(f.mul(f.sqr(z), z), f.one())))
                product = f.one()
                for xc in cert['xs'] + [f.toCoords(target[0])]:
                    product = f.mul(product, f.add(z, f.fromCoords(xc)))
                polynomial = 0
                for coefficient in residual:
                    polynomial = f.add(f.mul(polynomial, z), coefficient)
                self.assertEqual(polynomial, f.add(norm, product))

    def testSignsDegeneraciesAndMalformedWitnesses(self):
        f, curve, points, target, cert = fixture()
        self.assertIsNone(nagao.certificateForPoints(f, curve, points, curve.neg(target)))
        self.assertIsNone(nagao.reconstructWitness(f, curve, cert, curve.neg(target)))
        for form in nagao.FORMULATIONS:
            prog, roots = nagao.buildSystem(f.m, f.n, f.m, form)
            self.assertFalse(rootsZero(prog, roots, f.m, cert, curve.neg(target), f))
        repeated = [points[0], points[0], points[1]]
        repeatTarget = curve.add(curve.dbl(points[0]), points[1])
        self.assertIsNone(nagao.certificateForPoints(f, curve, repeated, repeatTarget))
        badCases = [dict(cert, b=0), dict(cert, xs=[0] + cert['xs'][1:]),
                    dict(cert, xs=[cert['xs'][0]] * 3),
                    dict(cert, xs=[f.toCoords(target[0])] + cert['xs'][1:]),
                    dict(cert, ys=[cert['ys'][0] ^ 1] + cert['ys'][1:]),
                    dict(cert, a=1 << f.m), {}, dict(cert, xs=[])]
        for bad in badCases:
            self.assertIsNone(nagao.reconstructWitness(f, curve, bad, target))
        self.assertIsNone(nagao.reconstructWitness(f, curve, cert, None))
        self.assertIsNone(nagao.certificateForPoints(f, curve, [None] + points[1:], target))

    def testParametersFailBeforeCnfMutation(self):
        f, _, _, target, _ = fixture()
        for args in [(4, 9, 4), (5, 13, 5), (7, 15, 5), (5, 11, 0), (True, 3, 1)]:
            with self.assertRaises(ValueError):
                nagao.buildSystem(*args)
        with self.assertRaises(ValueError):
            nagao.buildSystem(5, 11, 5, 'semaev')
        prog, roots = nagao.buildSystem(5, 11, 5)
        good = [5, 2, f.toCoords(target[0]), f.toCoords(target[1])]
        cases = [dict(index=0, value=4), dict(index=1, value=-1),
                 dict(index=1, value=6), dict(index=2, value=None),
                 dict(index=2, value=32), dict(index=3, value=None)]
        for case in cases:
            args = list(good)
            args[case['index']] = case['value']
            cnf = cnfmod.Cnf()
            before = cnf.stats()
            with self.assertRaises(ValueError):
                nagao.encode(prog, roots, *args, cnf)
            self.assertEqual(cnf.stats(), before)
        for xr, yr in [(0, 0), (f.toCoords(target[0]), f.toCoords(target[1]) ^ 1)]:
            cnf = cnfmod.Cnf()
            with self.assertRaises(ValueError):
                nagao.encode(prog, roots, 5, 2, xr, yr, cnf)
            self.assertEqual(cnf.nVars, 1)
        with self.assertRaises(ValueError):
            nagao.encode(prog, roots, *good, cnfmod.Cnf(), formulation='norm')


@unittest.skipUnless(WITH_SOLVER, 'use --solver for CryptoMiniSat CNF/XOR checks')
class NagaoSolverTests(unittest.TestCase):
    def testFixedWitnessRoundTripBothFrontends(self):
        f, curve, _, target, cert = fixture()
        for form in nagao.FORMULATIONS:
            prog, roots = nagao.buildSystem(f.m, f.n, f.m, form)
            c = cnfmod.Cnf()
            variables = nagao.encode(prog, roots, f.m, 2, f.toCoords(target[0]),
                                     f.toCoords(target[1]), c, form)
            model = solve(c, pinCertificate(variables, cert))
            self.assertIsNotNone(model, form)
            decoded = nagao.decode(model, variables, c)
            self.assertIsNotNone(nagao.reconstructWitness(f, curve, decoded, target))
            for key in ('xs', 'a', 'b'):
                self.assertEqual(decoded[key], cert[key])

    def testRestrictedDomainAndWrongSignedCertificateAreUnsat(self):
        f, curve, _, target, cert = fixture()
        for form in nagao.FORMULATIONS:
            prog, roots = nagao.buildSystem(f.m, f.n, f.m, form)
            c = cnfmod.Cnf()
            variables = nagao.encode(prog, roots, f.m, f.m, f.toCoords(target[0]),
                                     f.toCoords(target[1]), c, form)
            self.assertIsNone(solve(c, pin(variables['b'], 0)))
            for i, values in enumerate([(0, None), (cert['xs'][0], cert['xs'][0]),
                                        (f.toCoords(target[0]), None)]):
                assumptions = pin(variables['pvars'][0], values[0])
                if values[1] is not None:
                    assumptions += pin(variables['pvars'][1], values[1])
                self.assertIsNone(solve(c, assumptions), (form, i))
            opposite = curve.neg(target)
            d = cnfmod.Cnf()
            v = nagao.encode(prog, roots, f.m, f.m, f.toCoords(opposite[0]),
                             f.toCoords(opposite[1]), d, form)
            self.assertIsNone(solve(d, pinCertificate(v, cert)))

    def testSharedDomainTruthTableAndOrdering(self):
        # The domain helper is independent of the field and is deliberately
        # shared by the root's Semaev comparator.  Enumerate all 8^3 inputs.
        c = cnfmod.Cnf()
        pvars = [[c.newVar() for _ in range(3)] for _ in range(3)]
        nagao.addRestrictedDomain(c, pvars, 6)
        from pysat.solvers import CryptoMinisat
        solver = CryptoMinisat()
        try:
            for clause in c.clauses:
                solver.add_clause(clause)
            for lits, rhs in c.xors:
                solver.add_xor_clause(lits, rhs)
            for a in range(8):
                for b in range(8):
                    for d in range(8):
                        assumptions = pin(pvars[0], a) + pin(pvars[1], b) + pin(pvars[2], d)
                        want = 0 < a < b < d and 6 not in (a, b, d)
                        self.assertEqual(solver.solve(assumptions=assumptions), want, (a, b, d))
        finally:
            solver.delete()

    def testUnplantedTargetDecisionsAgainstCompleteSignedEnumeration(self):
        f = field.Onb(5)
        curve = curves.Curve(f)
        base = []
        for x in range(1, 1 << f.m):
            if bin(x).count('1') > 1:
                continue
            p = curve.pointFromX(f.fromCoords(x))
            if p is not None:
                base.append(p)
        groundTruth = set()
        for i in range(len(base)):
            for j in range(i + 1, len(base)):
                for k in range(j + 1, len(base)):
                    for mask in range(8):
                        pts = [base[i], base[j], base[k]]
                        pts = [curve.neg(p) if (mask >> z) & 1 else p for z, p in enumerate(pts)]
                        target = curve.add(curve.add(pts[0], pts[1]), pts[2])
                        if target is not None and target[0] not in [p[0] for p in pts]:
                            groundTruth.add(target)
        counts = {True: 0, False: 0}
        # Both signs of each finite nonzero target, plus two-torsion target.
        targets = [(0, f.one())]
        for x in range(1, 1 << f.m):
            p = curve.pointFromX(f.fromCoords(x))
            if p is not None:
                targets.extend([p, curve.neg(p)])
        for form in nagao.FORMULATIONS:
            prog, roots = nagao.buildSystem(f.m, f.n, f.m, form)
            for target in targets:
                c = cnfmod.Cnf()
                variables = nagao.encode(prog, roots, f.m, 1, f.toCoords(target[0]),
                                         f.toCoords(target[1]), c, form)
                model = solve(c)
                expected = target in groundTruth
                self.assertEqual(model is not None, expected, (form, target))
                counts[expected] += 1
                if model is not None:
                    decoded = nagao.decode(model, variables, c)
                    self.assertIsNotNone(nagao.reconstructWitness(f, curve, decoded, target))
                    self.assertTrue(all(bin(x).count('1') <= 1 for x in decoded['xs']))
        self.assertGreater(counts[True], 0)
        self.assertGreater(counts[False], 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
