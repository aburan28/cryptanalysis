"""Restricted Riemann--Roch point decomposition on y^2 + xy = x^3 + 1.

For three affine summands use the monic function

    f = x^2 + a*x + c + b*y in L(4*O),
    c = xr^2 + a*xr + b*(xr + yr).

Thus f(-R)=0.  Four distinct zeros exhaust its degree-four zero divisor,
so f(P_i)=0 for three curve points implies sum(P_i)=R.  ``incidence``
keeps their y coordinates.  ``norm`` eliminates them using

    Norm(f) = X^4 + (b+b^2)X^3 + (a^2+a*b)X^2
                  + b*c*X + c^2+b^2.

Match these coefficients with product(X+x_i)*(X+xr), retaining a and b
as unknowns.  Neither frontend constructs a summation polynomial.

This first chart requires b != 0 and distinct factor abscissas, also
different from xr.  Factor abscissas are nonzero, matching the existing
indexcalc.factorBase, whose pointFromX omits the two-torsion point.
Repeated zeros and points at infinity need further charts or confluent
conditions; UNSAT here means only UNSAT within this restricted domain.

No type hints, camelCase identifiers, no itertools (project convention).
"""

import curves
import decomp
import field
import ir


FORMULATIONS = ('incidence', 'norm')


def _integer(value, name, low, high=None):
    if type(value) is not int or value < low or (high is not None and value > high):
        raise ValueError('%s is outside its supported integer range' % name)


def _validateField(m, nring=None):
    _integer(m, 'm', 3)
    if m % 2 == 0:
        raise ValueError('m must be odd for the existing curve/half-trace model')
    if nring is not None and (type(nring) is not int or nring != 2 * m + 1):
        raise ValueError('nring must equal 2*m+1')
    return field.Onb(m)


def _validateFormulation(formulation):
    if formulation not in FORMULATIONS:
        raise ValueError('formulation must be incidence or norm')


def _add(prog, *vectors):
    return [prog.xorList([v[i] for v in vectors]) for i in range(len(vectors[0]))]


def buildSystem(m, nring, leaf, formulation='incidence'):
    """Return (IR program, zero roots) for the restricted three-point chart.

    Inputs p0..p2 are factor x coordinates; y0..y2 exist only for
    incidence.  a,b are function coefficients, r,s are target x,y, and
    one is the field unit.  Every vector uses the existing ONB bit order.
    ``m`` is the field degree, not the number of summands (fixed at 3).
    """
    _validateField(m, nring)
    _integer(leaf, 'leaf', 1)
    _validateFormulation(formulation)
    prog = ir.Prog()
    prog.nagaoParameters = (m, nring, leaf, formulation)
    inp = lambda name: [prog.addInput(name, j) for j in range(m)]
    xs = [inp('p%d' % i) for i in range(3)]
    ys = [inp('y%d' % i) for i in range(3)] if formulation == 'incidence' else []
    a, b, xr, yr, one = [inp(name) for name in ('a', 'b', 'r', 's', 'one')]
    sqp = decomp.sigmaPerm(m, nring, 1)
    sq = lambda v: decomp.applyPerm(v, sqp)
    mul = lambda v, w: decomp.onbMul(prog, v, w, m, leaf)
    c = _add(prog, sq(xr), mul(a, xr), mul(b, _add(prog, xr, yr)))
    roots = []
    if formulation == 'incidence':
        for x, y in zip(xs, ys):
            # Squaring is linear in ONB; both equations are Boolean quadratic.
            roots.extend(_add(prog, sq(y), mul(x, y), mul(sq(x), x), one))
            roots.extend(_add(prog, sq(x), mul(a, x), c, mul(b, y)))
    else:
        # Product of the two monic quadratics avoids a general resultant.
        u = _add(prog, xs[0], xs[1])
        v = mul(xs[0], xs[1])
        w = _add(prog, xs[2], xr)
        z = mul(xs[2], xr)
        elementary = [
            _add(prog, u, w),
            _add(prog, v, z, mul(u, w)),
            _add(prog, mul(u, z), mul(v, w)),
            mul(v, z),
        ]
        norm = [
            _add(prog, b, sq(b)),
            _add(prog, sq(a), mul(a, b)),
            mul(b, c),
            _add(prog, sq(c), sq(b)),
        ]
        for left, right in zip(elementary, norm):
            roots.extend(_add(prog, left, right))
    return prog, roots


def addRestrictedDomain(c, pvars, xrBits, orderPoints=True):
    """Add the same nonzero/distinct-abscissa domain to either frontend.

    Call this on the Semaev comparator too.  Order, when requested, is
    numeric increasing ONB coordinates (pvars themselves are little-endian).
    This helper does not add weight bounds or enforce curve membership.
    """
    if len(pvars) != 3 or not pvars[0]:
        raise ValueError('the restricted chart needs three nonempty x vectors')
    m = len(pvars[0])
    if any(len(v) != m for v in pvars):
        raise ValueError('factor x vectors must have the same width')
    _integer(xrBits, 'xrBits', 0, (1 << m) - 1)
    for v in pvars:
        c.addClause(v)  # exclude the x=0 factor point, like factorBase
        c.addClause([-v[j] if (xrBits >> j) & 1 else v[j] for j in range(m)])
    for i in range(3):
        for j in range(i + 1, 3):
            c.addClause([c.xorLit(a, b) for a, b in zip(pvars[i], pvars[j])])
    if orderPoints:
        for i in range(2):
            c.lexLeq(list(reversed(pvars[i])), list(reversed(pvars[i + 1])))


def encode(prog, roots, m, weight, xrBits, yrBits, c,
           formulation='incidence', orderPoints=True):
    """Emit CNF/XOR and return pvars, yvars, a, b literal vectors.

    Invalid field/target/weight inputs fail before c is modified.  Infinity
    is unsupported; pass both finite target coordinates as m-bit integers.
    """
    onb = _validateField(m)
    _validateFormulation(formulation)
    _integer(weight, 'weight', 0, m)
    _integer(xrBits, 'xrBits', 0, (1 << m) - 1)
    _integer(yrBits, 'yrBits', 0, (1 << m) - 1)
    params = getattr(prog, 'nagaoParameters', None)
    if params is None or params[0] != m or params[3] != formulation:
        raise ValueError('program parameters do not match the requested encoding')
    target = (onb.fromCoords(xrBits), onb.fromCoords(yrBits))
    if not curves.Curve(onb).onCurve(target):
        raise ValueError('target is not on y^2+xy=x^3+1')
    lits = {}

    def variables(name):
        result = [c.newVar() for _ in range(m)]
        for j, lit in enumerate(result):
            lits[(name, j)] = lit
        return result

    pvars = [variables('p%d' % i) for i in range(3)]
    yvars = [variables('y%d' % i) for i in range(3)] if formulation == 'incidence' else []
    a, b = variables('a'), variables('b')
    for v in pvars:
        c.atMost(v, weight)
    for j in range(m):
        lits[('r', j)] = c.true if (xrBits >> j) & 1 else c.false
        lits[('s', j)] = c.true if (yrBits >> j) & 1 else c.false
        lits[('one', j)] = c.true
    for lit in prog.emitCnf(roots, lits, c):
        c.assertZero(lit)
    c.addClause(b)  # the chart with a unique y lift from f=0
    addRestrictedDomain(c, pvars, xrBits, orderPoints)
    return {'pvars': pvars, 'yvars': yvars, 'a': a, 'b': b}


def decode(model, variables, c):
    """Decode a solver's {positive variable id: 0/1} model to ONB integers."""
    def bits(vector):
        result = 0
        for j, lit in enumerate(vector):
            if lit == c.true:
                value = 1
            elif lit == c.false:
                value = 0
            else:
                value = model.get(abs(lit))
                if value not in (0, 1):
                    raise ValueError('model is missing a Boolean input value')
                if lit < 0:
                    value = 1 - value
            result |= value << j
        return result
    return {'xs': [bits(v) for v in variables['pvars']],
            'ys': [bits(v) for v in variables['yvars']],
            'a': bits(variables['a']), 'b': bits(variables['b'])}


def reconstructWitness(onb, curve, decoded, target):
    """Independently reconstruct and verify all curve points and their sum.

    Returns {'points': [...], 'a': ..., 'b': ..., 'c': ..., 'verified': True}
    using field.py's internal field elements, or None.  The independent
    arithmetic never evaluates the generated IR.  Weight is checked by the
    caller against its frozen factor base; this helper checks the chart,
    certificate, curve membership, and the exact signed target.
    """
    if target is None or not curve.onCurve(target):
        return None
    try:
        xs = decoded['xs']
        ys = decoded.get('ys', [])
        if len(xs) != 3 or len(ys) not in (0, 3):
            return None
        for value in list(xs) + list(ys) + [decoded['a'], decoded['b']]:
            _integer(value, 'decoded coordinate', 0, (1 << onb.m) - 1)
        xr = onb.toCoords(target[0])
        if 0 in xs or len(set(list(xs) + [xr])) != 4 or decoded['b'] == 0:
            return None
        a = onb.fromCoords(decoded['a'])
        b = onb.fromCoords(decoded['b'])
        negTarget = curve.neg(target)
        c = onb.add(onb.add(onb.sqr(target[0]), onb.mul(a, target[0])),
                    onb.mul(b, negTarget[1]))
        binv = onb.inv(b)
        points = []
        total = None
        for i, xc in enumerate(xs):
            x = onb.fromCoords(xc)
            numerator = onb.add(onb.add(onb.sqr(x), onb.mul(a, x)), c)
            y = onb.mul(numerator, binv)
            if ys and onb.fromCoords(ys[i]) != y:
                return None
            point = (x, y)
            if not curve.onCurve(point):
                return None
            points.append(point)
            total = curve.add(total, point)
        if total != target:
            return None
        return {'points': points, 'a': a, 'b': b, 'c': c, 'verified': True}
    except (KeyError, TypeError, ValueError):
        return None


def certificateForPoints(onb, curve, points, target):
    """Independent interpolation certificate for a proposed signed triple.

    Returns the same ONB-coordinate dictionary as decode(), or None.
    This is a ground-truth/test utility, not a decomposition solver.
    """
    if len(points) != 3 or target is None or any(p is None for p in points):
        return None
    if not curve.onCurve(target) or any(not curve.onCurve(p) for p in points):
        return None
    xs = [onb.toCoords(p[0]) for p in points]
    if 0 in xs or len(set(xs + [onb.toCoords(target[0])])) != 4:
        return None
    total = None
    for point in points:
        total = curve.add(total, point)
    if total != target:
        return None
    negTarget = curve.neg(target)
    dx = [onb.add(p[0], target[0]) for p in points[:2]]
    dy = [onb.add(p[1], negTarget[1]) for p in points[:2]]
    det = onb.add(onb.mul(dx[0], dy[1]), onb.mul(dx[1], dy[0]))
    if det == 0:
        return None
    invdet = onb.inv(det)
    a = onb.mul(onb.add(onb.mul(onb.sqr(dx[0]), dy[1]),
                        onb.mul(onb.sqr(dx[1]), dy[0])), invdet)
    b = onb.mul(onb.add(onb.mul(dx[0], onb.sqr(dx[1])),
                        onb.mul(dx[1], onb.sqr(dx[0]))), invdet)
    decoded = {'xs': xs, 'ys': [onb.toCoords(p[1]) for p in points],
               'a': onb.toCoords(a), 'b': onb.toCoords(b)}
    return decoded if reconstructWitness(onb, curve, decoded, target) else None


def inputValues(m, decoded, xrBits, yrBits):
    """Build scalar IR input bits from a coordinate-form certificate."""
    vectors = {'a': decoded['a'], 'b': decoded['b'],
               'r': xrBits, 's': yrBits, 'one': (1 << m) - 1}
    for i, x in enumerate(decoded['xs']):
        vectors['p%d' % i] = x
    for i, y in enumerate(decoded.get('ys', [])):
        vectors['y%d' % i] = y
    return {(name, j): (value >> j) & 1
            for name, value in vectors.items() for j in range(m)}
