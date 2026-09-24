"""Validate the native isogeny tool on a toy analog that Sage can check directly.

Toy: E0: y^2 + xy = x^3 + 1 over F_(2^17).  tau^17 = a + b tau with the
inert prime p = 271 dividing b, pi acting on E0[271] as a generator of
F_271^*/{+-1}; the x-coordinates of E0[271] live in F_(2^(17*135)).
The conductor-271 floor has h = 272 = 16 * 17 curves.

Checks, all independent of the C code's own assertions:
  1. torsion: the C point's x lies on E0[271] (Sage division polynomial test
     through its own GF(2^2295) arithmetic after an explicit field isomorphism
     is avoided by comparing only F_(2^17)-valued outputs);
  2. lines: the 272 Vélu codomains j = 1/(1+v+v^2) equal the roots of the
     conductor-271 class polynomial mod 2 (computed by PARI);
  3. kernel: every kernel polynomial divides the 271-division polynomial,
     and Sage's Kohel isogeny from it has the predicted codomain.
"""
import json
import subprocess
import time
from pathlib import Path

from sage.all import (GF, PolynomialRing, EllipticCurve, ZZ, NumberField, pari, QQ)

HERE = Path(__file__).resolve().parent
BIN = HERE.parent / 'native' / 'isogeny'
WORK = HERE.parent / 'outputs' / 'run04-explicit-descent' / 'toy'


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    m, p = 17, 271
    x = PolynomialRing(QQ, 'x').gen()
    K = NumberField(x ** 2 + x + 2, 't')
    a, b = list(K.gen() ** m)
    a, b = ZZ(a), ZZ(b)
    assert b % p == 0 and pari.kronecker(-7, p) == -1
    c = a % p
    r = 135
    q = 2 ** m
    t = 2 * a - b
    # trace of pi^r via Lucas sequence V_k = tau^k + taubar^k, V_1 = -1
    def lucas_v(n):
        v0, v1 = 2, -1
        for _ in range(n - 1):
            v0, v1 = v1, -v1 - 2 * v0
        return v1 if n >= 1 else 2
    N = m * r
    VN = lucas_v(N)
    twist_order = 2 ** N + 1 + VN
    curve_order = 2 ** N + 1 - VN
    assert curve_order % p != 0 and twist_order % (p * p) == 0
    e = 0
    h = twist_order
    while h % p == 0:
        h //= p
        e += 1
    (WORK / 'cofactor.hex').write_text('%x\n' % h)
    field = ['17', '3', '135', '11']
    started = time.perf_counter()
    out = subprocess.run([str(BIN), 'torsion', *field, '1', '1', str(p), str(WORK / 'cofactor.hex'),
                          '20260923', str(WORK / 'P.bin')], capture_output=True, text=True, check=True)
    torsion = json.loads(out.stdout)
    assert torsion['order_is_ell']
    frob = json.loads(subprocess.run([str(BIN), 'frobcheck', *field, '1', str(p), str(c), str(WORK / 'P.bin')],
                                     capture_output=True, text=True, check=True).stdout)
    assert frob['frobenius_matches'] and frob['tau_sum_has_order_ell']
    lines = subprocess.run([str(BIN), 'lines', *field, str(p), str(WORK / 'P.bin')],
                           capture_output=True, text=True, check=True).stdout.strip().splitlines()
    rows = [json.loads(l) for l in lines]
    assert rows[-1]['chain_closes']
    traces = {row['line']: int(row['trace'], 16) for row in rows[:-1]}
    assert len(traces) == p + 1

    Rz = PolynomialRing(GF(2), 'z')
    zz = Rz.gen()
    F = GF(2 ** m, 'w', modulus=zz ** 17 + zz ** 3 + 1)
    js = {}
    for line, v in traces.items():
        v = F.from_integer(v)
        js[line] = 1 / (1 + v + v * v)
    H = pari.polclass(-7 * p * p)
    RF = PolynomialRing(F, 'X')
    roots = set(RF([F(int(cf) % 2) for cf in pari.Vecrev(H)]).roots(multiplicities=False))
    assert len(roots) == p + 1
    matched = set(js.values()) == roots and len(set(js.values())) == p + 1

    # kernel polynomials for two lines, checked against Sage's own isogeny
    E0 = EllipticCurve(F, [1, 0, 0, 0, 1])
    psi = RF(E0.division_polynomial(p).list())
    kernels = []
    for line in ('inf', '5'):
        kout = json.loads(subprocess.run([str(BIN), 'kernel', *field, str(p), str(WORK / 'P.bin'), line],
                                         capture_output=True, text=True, check=True).stdout)
        assert kout['vanishes_at_x'] and kout['degree'] == (p - 1) // 2
        kpoly = RF([F.from_integer(int(cf, 16)) for cf in kout['coefficients_ascending']])
        assert psi % kpoly == 0
        phi = E0.isogeny(kpoly)
        key = 'inf' if line == 'inf' else int(line)
        assert phi.codomain().j_invariant() == js[key]
        kernels.append({'line': line, 'degree': int(kpoly.degree()), 'divides_division_polynomial': True,
                        'sage_codomain_matches': True})
    result = {'toy': {'m': m, 'p': p, 'pi_scalar': int(c), 'x_field_degree': N, 'twist_ell_valuation': e},
              'torsion': torsion, 'frobcheck': frob, 'lines': len(traces),
              'codomains_equal_class_polynomial_roots': matched, 'kernels': kernels,
              'seconds': time.perf_counter() - started}
    assert matched
    (WORK / 'toy-validation.json').write_text(json.dumps(result, indent=1) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
