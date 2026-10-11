"""Exact independent checks for the restricted RR annihilator formulation."""

import unittest

import curves
import nagaoannihilator as nagao


class NagaoAnnihilatorTests(unittest.TestCase):
    def testSubspacePolynomialAllFieldElements(self):
        for degree in (3, 5):
            onb = nagao.CountedField(degree)
            for dimension in range(degree + 1):
                coefficients = nagao.subspacePolynomial(onb, dimension)
                self.assertEqual(len(coefficients), dimension + 1)
                for coords in range(1 << degree):
                    value = nagao.linearizedEval(onb, coefficients, onb.fromCoords(coords))
                    self.assertEqual(value == 0, coords < (1 << dimension))

    def testAnnihilatorRejectsRepeatedRoots(self):
        onb = nagao.CountedField(5)
        coefficients = nagao.subspacePolynomial(onb, 3)
        # H=X^3 has a repeated root in V but cannot divide squarefree L_V.
        self.assertTrue(nagao.annihilatorRemainder(onb, coefficients,
            [0, 0, 0, onb.one()]))
        # H=X(X+u)(X+v) has exactly three distinct roots in V.
        u, v = onb.fromCoords(1), onb.fromCoords(2)
        modulus = [0, onb.mul(u, v), onb.add(u, v), onb.one()]
        self.assertEqual(nagao.annihilatorRemainder(onb, coefficients, modulus), [])

    def testNormMatchesIndependentCurveEvaluation(self):
        onb = nagao.CountedField(5)
        curve = nagao.CountedCurve(onb)
        points = nagao.affinePoints(onb, curve,
            [onb.fromCoords(index) for index in range(32)])
        for target in points[::7]:
            for aCoords, bCoords in ((0, 1), (3, 7), (31, 13)):
                a, b = onb.fromCoords(aCoords), onb.fromCoords(bCoords)
                residual, c = nagao.residualNorm(onb, target, a, b)
                for point in points:
                    x, y = point
                    valueA = onb.add(onb.add(onb.sqr(x), onb.mul(a, x)), c)
                    first = onb.add(valueA, onb.mul(b, y))
                    second = onb.add(valueA, onb.mul(b, onb.add(x, y)))
                    actual = onb.mul(first, second)
                    expected = onb.mul(onb.add(x, target[0]),
                        nagao.polyEval(onb, residual, x))
                    self.assertEqual(actual, expected)

    def testAllTargetSolutionSetsAndAccounting(self):
        for degree, dimension in ((3, 2), (5, 2), (5, 3)):
            result = nagao.runExperiment(degree, dimension)
            self.assertTrue(result['allSolutionSetsEqual'])
            self.assertEqual(result['targetCount'], curves.curveOrder(degree) - 1)
            self.assertTrue(any(row['target'][0] == 0 for row in result['targets']))
            for row in result['targets']:
                self.assertEqual(row['candidates'], (1 << degree) * ((1 << degree) - 1))
                self.assertEqual(row['admitted'], row['verifiedSolutions'])
                self.assertTrue(all(certificate['certificateCount'] == 1
                    for certificate in row['solutionCertificates']))
            if degree == 5 and dimension == 3:
                self.assertGreater(result['verifiedSolutions'], 0)
                self.assertGreater(result['nagaoOperations']['phases']['verification']['fieldOperations'], 0)
            for name in ('nagaoOperations', 'oracleOperations'):
                report = result[name]
                for category, total in report['totals'].items():
                    self.assertEqual(total, sum(phase[category] for phase in report['phases'].values()))
                self.assertEqual(report['totals']['fieldOperations'],
                    sum(report['totals'][category] for category in
                        ('additions', 'multiplications', 'squarings')))

    def testScopeValidation(self):
        with self.assertRaises(ValueError):
            nagao.runExperiment(131, 3)
        with self.assertRaises(ValueError):
            nagao.runExperiment(5, 6)
        with self.assertRaises(ValueError):
            nagao.runExperiment(5, 3, [[0, 0]])
        with self.assertRaises(ZeroDivisionError):
            nagao.CountedField(5).inv(0)


if __name__ == '__main__':
    unittest.main()
