"""Exhaustive toy Nagao/Riemann--Roch coefficient search without Semaev.

For y^2+xy=x^3+1 and R=(r,s), f=x^2+a*x+c+b*y has four poles
at O. Pin c=r^2+a*r+b*(r+s), so f(-R)=0. Its norm is
A^2+x*A*b+(x^3+1)*b^2. Divide by X+r to obtain monic cubic H.
The additive polynomial L_V has precisely V as its simple roots; H|L_V
therefore certifies three distinct x-roots in V before root extraction.

This prototype restricts b!=0, H(0)!=0 and H(r)!=0. It covers distinct
nonzero factor abscissae, all different from the target abscissa. Infinity,
repeated abscissae and larger fields are deliberately outside the contract.
It enumerates every a,b and is a correctness experiment, not a speedup claim.
The independently derived annihilator adaptation has no novelty claim.

Primary sources: Nagao-style norm construction in Joux--Vitse, section 3.1,
https://link.springer.com/content/pdf/10.1007/978-3-642-29011-4_3
and the RR/elimination relationship in Vitse, DLP 2014, slide 10,
https://www-fourier.univ-grenoble-alpes.fr/~viva/research/talks/Vitse_talk_DLP14.pdf

Operation accounting counts every field add/mul/square called by setup,
search, root extraction and verification. Inversions expand to primitive
operations; inversion and curve-call totals are nonadditive diagnostics.
Coordinate conversion, comparisons, allocation and Python control overhead
are not field operations. No conversion to rho or DLP cost is asserted.
No type hints, camelCase identifiers, no itertools (project convention).
"""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

import curves
import field


class CountedField(field.Onb):
    def __init__(self, degree):
        super().__init__(degree)
        self.phase = 'setup'
        self.counts = {}

    def bump(self, name, count=1):
        row = self.counts.setdefault(self.phase, {
            'additions': 0, 'multiplications': 0, 'squarings': 0,
            'inversionCalls': 0, 'curveAdditionCalls': 0,
            'curveDoublingCalls': 0})
        row[name] += count

    def add(self, a, b):
        self.bump('additions')
        return super().add(a, b)

    def mul(self, a, b):
        self.bump('multiplications')
        return super().mul(a, b)

    def sqr(self, a):
        self.bump('squarings')
        return field.Onb.frob(self, a, 1)

    def frob(self, a, count):
        self.bump('squarings', count)
        return field.Onb.frob(self, a, count)

    def inv(self, a):
        if a == 0:
            raise ZeroDivisionError('cannot invert zero')
        self.bump('inversionCalls')
        return super().inv(a)

    def trace(self, a):
        acc = 0
        value = a
        for _ in range(self.m):
            acc = self.add(acc, value)
            value = self.sqr(value)
        return 1 if acc else 0

    def report(self):
        out = {}
        for phase, counts in self.counts.items():
            out[phase] = dict(counts)
            out[phase]['fieldOperations'] = sum(counts[name] for name in
                ('additions', 'multiplications', 'squarings'))
        totals = {'additions': 0, 'multiplications': 0, 'squarings': 0,
                  'inversionCalls': 0, 'curveAdditionCalls': 0,
                  'curveDoublingCalls': 0, 'fieldOperations': 0}
        for counts in out.values():
            for name, count in counts.items():
                totals[name] += count
        return {'phases': out, 'totals': totals}


class CountedCurve(curves.Curve):
    def add(self, p, q):
        self.f.bump('curveAdditionCalls')
        return super().add(p, q)

    def dbl(self, p):
        self.f.bump('curveDoublingCalls')
        return super().dbl(p)


def polyTrim(coefficients):
    result = list(coefficients)
    while result and result[-1] == 0:
        result.pop()
    return result


def polyEval(onb, coefficients, value):
    result = 0
    for coefficient in reversed(coefficients):
        result = onb.add(onb.mul(result, value), coefficient)
    return result


def polyRem(onb, coefficients, modulus):
    """Monic polynomial remainder; all arithmetic uses the counted field."""
    if not modulus or modulus[-1] != onb.one():
        raise ValueError('modulus must be monic')
    result = polyTrim(coefficients)
    degree = len(modulus) - 1
    while len(result) > degree:
        top = result[-1]
        offset = len(result) - len(modulus)
        # Cancel the leading term by assignment; do not charge a fake multiply.
        result.pop()
        for index in range(degree):
            result[offset + index] = onb.add(
                result[offset + index], onb.mul(top, modulus[index]))
        result = polyTrim(result)
    return result


def polySquareMod(onb, coefficients, modulus):
    if not coefficients:
        return []
    result = [0] * (2 * len(coefficients) - 1)
    for index, coefficient in enumerate(coefficients):
        result[2 * index] = onb.sqr(coefficient)
    return polyRem(onb, result, modulus)


def linearizedEval(onb, coefficients, value):
    result = 0
    power = value
    for index, coefficient in enumerate(coefficients):
        result = onb.add(result, onb.mul(coefficient, power))
        if index + 1 < len(coefficients):
            power = onb.sqr(power)
    return result


def subspacePolynomial(onb, dimension):
    """Sparse coefficients l_j of L_V(T)=sum l_j*T^(2^j)."""
    if not 0 <= dimension <= onb.m:
        raise ValueError('subspace dimension must be between zero and degree')
    coefficients = [onb.one()]
    for index in range(dimension):
        value = linearizedEval(onb, coefficients, onb.fromCoords(1 << index))
        if value == 0:
            raise ArithmeticError('basis vector unexpectedly in previous span')
        updated = [0] * (len(coefficients) + 1)
        for power, coefficient in enumerate(coefficients):
            updated[power + 1] = onb.sqr(coefficient)
        for power, coefficient in enumerate(coefficients):
            updated[power] = onb.add(updated[power], onb.mul(value, coefficient))
        coefficients = updated
    return coefficients


def annihilatorRemainder(onb, linearized, modulus):
    """Compute L_V mod H using modular Frobenius, without expanding L_V."""
    degree = len(modulus) - 1
    result = [0] * degree
    power = polyRem(onb, [0, onb.one()], modulus)
    for index, coefficient in enumerate(linearized):
        for powerIndex, powerCoefficient in enumerate(power):
            result[powerIndex] = onb.add(result[powerIndex],
                onb.mul(coefficient, powerCoefficient))
        if index + 1 < len(linearized):
            power = polySquareMod(onb, power, modulus)
    return polyTrim(result)


def residualNorm(onb, target, a, b):
    """Return (H,c) in ascending coefficient order with f(-R)=0."""
    if target is None or b == 0:
        raise ValueError('finite target and nonzero y coefficient required')
    r, s = target
    c = onb.add(onb.add(onb.sqr(r), onb.mul(a, r)),
                onb.mul(b, onb.add(r, s)))
    bSquared = onb.sqr(b)
    norm = [onb.add(onb.sqr(c), bSquared), onb.mul(b, c),
            onb.add(onb.sqr(a), onb.mul(a, b)),
            onb.add(b, bSquared), onb.one()]
    quotient = [0, 0, 0, onb.one()]
    for index in (2, 1, 0):
        quotient[index] = onb.add(norm[index + 1],
                                   onb.mul(r, quotient[index + 1]))
    if onb.add(norm[0], onb.mul(r, quotient[0])) != 0:
        raise ArithmeticError('norm does not vanish at the pinned target')
    return quotient, c


def affinePoints(onb, curve, values):
    points = []
    for x in values:
        if x == 0:
            point = (0, onb.one())
        else:
            point = curve.pointFromX(x)
        if point is None:
            continue
        if not curve.onCurve(point):
            raise ArithmeticError('point recovery failed')
        points.append(point)
        negative = curve.neg(point)
        if negative != point:
            points.append(negative)
    return sorted(points, key=lambda p: (onb.toCoords(p[0]), onb.toCoords(p[1])))


def canonicalTriple(onb, points):
    return tuple(sorted((onb.toCoords(x), onb.toCoords(y)) for x, y in points))


def verifyTriple(curve, target, points):
    if not all(curve.onCurve(point) for point in points):
        return False
    return curve.add(curve.add(points[0], points[1]), points[2]) == target


def searchTarget(onb, curve, target, values, linearized):
    """Search RR coefficients first; inspect factor roots only after admission."""
    solutions = {}
    candidates = zeroRootRejected = targetRootRejected = admitted = 0
    for aCoords in range(1 << onb.m):
        a = onb.fromCoords(aCoords)
        for bCoords in range(1, 1 << onb.m):
            b = onb.fromCoords(bCoords)
            candidates += 1
            onb.phase = 'candidateConstruction'
            residual, c = residualNorm(onb, target, a, b)
            if residual[0] == 0:
                zeroRootRejected += 1
                continue
            if polyEval(onb, residual, target[0]) == 0:
                targetRootRejected += 1
                continue
            onb.phase = 'membership'
            if annihilatorRemainder(onb, linearized, residual):
                continue
            admitted += 1
            onb.phase = 'rootExtraction'
            roots = [x for x in values if polyEval(onb, residual, x) == 0]
            if len(roots) != 3 or 0 in roots or target[0] in roots:
                raise ArithmeticError('annihilator admitted invalid root support')
            inverseB = onb.inv(b)
            points = []
            for x in roots:
                y = onb.mul(onb.add(onb.add(onb.sqr(x), onb.mul(a, x)), c), inverseB)
                points.append((x, y))
            onb.phase = 'verification'
            if not verifyTriple(curve, target, points):
                raise ArithmeticError('RR certificate failed direct verification')
            canonical = canonicalTriple(onb, points)
            solutions[canonical] = solutions.get(canonical, 0) + 1
    return {'solutions': solutions, 'candidates': candidates, 'admitted': admitted,
            'zeroRootRejected': zeroRootRejected,
            'targetRootRejected': targetRootRejected}


def oracleTarget(onb, curve, target, base):
    """Independent enumeration over the identical restricted point domain."""
    solutions = set()
    triples = 0
    for first in range(len(base)):
        p = base[first]
        if p[0] == 0 or p[0] == target[0]:
            continue
        for second in range(first + 1, len(base)):
            q = base[second]
            if q[0] == 0 or q[0] in (p[0], target[0]):
                continue
            for third in range(second + 1, len(base)):
                t = base[third]
                if t[0] == 0 or t[0] in (p[0], q[0], target[0]):
                    continue
                triples += 1
                onb.phase = 'oracleSearch'
                if curve.add(curve.add(p, q), t) != target:
                    continue
                onb.phase = 'oracleVerification'
                if not verifyTriple(curve, target, (p, q, t)):
                    raise ArithmeticError('oracle relation failed verification')
                solutions.add(canonicalTriple(onb, (p, q, t)))
    return {'solutions': solutions, 'triples': triples}


def runExperiment(fieldDegree=5, subspaceDimension=3, targetCoords=None):
    if fieldDegree not in (3, 5):
        raise ValueError('exhaustive prototype is restricted to field degrees 3 and 5')
    if not 0 <= subspaceDimension <= fieldDegree:
        raise ValueError('invalid subspace dimension')
    onb = CountedField(fieldDegree)
    curve = CountedCurve(onb)
    values = [onb.fromCoords(index) for index in range(1 << subspaceDimension)]
    linearized = subspacePolynomial(onb, subspaceDimension)
    if targetCoords is None:
        targets = affinePoints(onb, curve,
            [onb.fromCoords(index) for index in range(1 << fieldDegree)])
    else:
        targets = []
        for x, y in targetCoords:
            if not (0 <= x < 1 << fieldDegree and 0 <= y < 1 << fieldDegree):
                raise ValueError('target coordinates are outside the field')
            point = (onb.fromCoords(x), onb.fromCoords(y))
            if not curve.onCurve(point):
                raise ValueError('target is not on the curve')
            targets.append(point)
    oracleField = CountedField(fieldDegree)
    oracleCurve = CountedCurve(oracleField)
    base = affinePoints(oracleField, oracleCurve,
        [oracleField.fromCoords(index) for index in range(1, 1 << subspaceDimension)])
    rows = []
    for target in targets:
        actual = searchTarget(onb, curve, target, values, linearized)
        expected = oracleTarget(oracleField, oracleCurve, target, base)
        actualSolutions = set(actual['solutions'])
        if actualSolutions != expected['solutions']:
            raise ArithmeticError('full RR solution set differs from oracle')
        row = {name: actual[name] for name in actual if name != 'solutions'}
        row.update({'target': [onb.toCoords(target[0]), onb.toCoords(target[1])],
            'oracleTriples': expected['triples'],
            'verifiedSolutions': len(actualSolutions), 'equalToOracle': True,
            'solutionCertificates': [
                {'points': [list(point) for point in solution],
                 'certificateCount': actual['solutions'][solution]}
                for solution in sorted(actualSolutions)]})
        rows.append(row)
    return {'schema': 'nagao-annihilator-toy-v1', 'fieldDegree': fieldDegree,
        'subspaceDimension': subspaceDimension, 'decompositionSize': 3,
        'curve': 'y^2+xy=x^3+1', 'coordinateEncoding': 'type-II ONB coordinate bits',
        'scope': 'distinct nonzero factor x, all different from finite target x',
        'search': 'exhaustive RR a,b coefficients; no Semaev; no SAT or Groebner',
        'status': 'correctness prototype; no performance or novelty claim',
        'reference': 'complete group-law enumeration of the identical restricted domain',
        'allAffineTargets': targetCoords is None,
        'targetCount': len(targets), 'factorBasePoints': len(base),
        'verifiedSolutions': sum(row['verifiedSolutions'] for row in rows),
        'targetHits': sum(row['verifiedSolutions'] > 0 for row in rows),
        'allSolutionSetsEqual': all(row['equalToOracle'] for row in rows),
        'annihilatorCoefficients': [onb.toCoords(c) for c in linearized],
        'operationAccounting': {
            'unit': 'field API primitives; additive mul/sqr counts are separate categories',
            'total': 'additions+multiplications+squarings',
            'inversions': 'expanded into counted multiplications; inversionCalls is diagnostic',
            'curveCalls': 'expanded into field primitives; curve call counts are diagnostic',
            'excludes': 'coordinate conversion, comparisons, allocations and Python overhead',
            'targetEnumeration': 'charged to RR setup once',
            'factorBaseEnumeration': 'charged to oracle setup once'},
        'nagaoOperations': onb.report(), 'oracleOperations': oracleField.report(),
        'targets': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--field-degree', dest='fieldDegree', type=int, default=5, choices=(3, 5))
    parser.add_argument('--subspace-dimension', dest='subspaceDimension', type=int, default=3)
    parser.add_argument('--out', type=Path,
                        help='write an immutable JSON artifact to a new path')
    arguments = parser.parse_args()
    if arguments.out is not None and arguments.out.exists():
        parser.error('output already exists; choose a new evidence path')
    output = runExperiment(arguments.fieldDegree, arguments.subspaceDimension)
    code = Path(__file__).resolve().parent
    root = code.parents[1]
    contract = root / 'research/nagao_relations/experiments/nagao_relation_contract.json'
    output['provenance'] = {
        'command': [sys.executable] + sys.argv,
        'python': platform.python_version(), 'platform': platform.platform(),
        'git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
        'git_status': subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True),
        'contract_sha256': hashlib.sha256(contract.read_bytes()).hexdigest(),
        'source_sha256': {name: hashlib.sha256((code / name).read_bytes()).hexdigest()
                          for name in ('nagaoannihilator.py', 'field.py', 'curves.py')}
    }
    if arguments.out is None:
        print(json.dumps(output, indent=2, sort_keys=True))
    else:
        arguments.out.parent.mkdir(parents=True, exist_ok=True)
        with arguments.out.open('x') as handle:
            json.dump(output, handle, indent=2, sort_keys=True)
            handle.write('\n')
        print(json.dumps({key: output[key] for key in
              ('targetCount', 'verifiedSolutions', 'targetHits', 'allSolutionSetsEqual')}))


if __name__ == '__main__':
    main()
