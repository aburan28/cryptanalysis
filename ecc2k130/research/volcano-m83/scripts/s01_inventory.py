"""Complete conductor-6473 floor inventory from the gamma_2 ring class polynomial.

Input: outputs/inventory/H83-mod2-ascending.txt, the reduction mod 2 of
polclass(-7*6473^2, 5) written by s01_polclass.gp (gamma_2 = j^(1/3)).
Cubing is a bijection on F_(2^83)^* (3 does not divide 2^83 - 1), so each
root r gives the j-invariant r^3.

    sage -python s01_inventory.py [--coefficients H83-gamma2-coefficients.txt]

The optional integer coefficient file (~300 MB, not kept in git) is re-reduced
mod 2 and hashed as an independent check of the stored reduction.
"""
import argparse
import hashlib
import json
import random
import time

from sage.all import GF, PolynomialRing, ZZ, pari, set_random_seed

import m83

started = time.perf_counter()


def stage(name, **data):
    print(json.dumps({'stage': name, 'seconds': round(time.perf_counter() - started, 3), **data}), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--coefficients')
    args = ap.parse_args()
    out = m83.OUT / 'inventory'
    text = (out / 'H83-mod2-ascending.txt').read_text().strip()
    bits = [int(c) for c in text.strip('[]').split(',')]
    R = PolynomialRing(GF(2), 'X')
    H2 = R(bits)
    assert H2.degree() == m83.FLOOR_SIZE and H2.is_monic()
    assert H2.gcd(H2.derivative()) == 1
    stored_sha = hashlib.sha256((out / 'H83-mod2-ascending.txt').read_bytes()).hexdigest()
    check = None
    if args.coefficients:
        h = hashlib.sha256()
        parity = []
        with open(args.coefficients, 'rb') as f:
            for line in f:
                h.update(line)
                parity.append(int(line.strip()[-1:], 16) & 1)
        assert parity == bits, 'integer coefficient file disagrees with the stored reduction'
        check = {'integer_coefficients_sha256': h.hexdigest(), 'lines': len(parity),
                 'reduction_matches': True}
    stage('class_polynomial_mod_2', degree=int(H2.degree()), check=check)

    factors = list(H2.factor())
    degrees = sorted(int(p.degree()) for p, e in factors)
    assert all(e == 1 for p, e in factors) and degrees == [m83.ORBIT] * m83.N_ORBITS
    stage('factorization', factors=len(factors), degree=m83.ORBIT)

    F = m83.FIELD
    RF = PolynomialRing(F, 'X')
    orbits = []
    seen = set()
    for p, _ in factors:
        roots = RF(p).roots(multiplicities=False)
        assert len(roots) == m83.ORBIT
        js = [r ** 3 for r in roots]
        encs = sorted(m83.enc(j) for j in js)
        assert len(set(encs)) == m83.ORBIT
        j0 = m83.dec(encs[0])
        orbit = [j0]
        for _ in range(m83.ORBIT - 1):
            orbit.append(orbit[-1] ** 2)
        assert sorted(m83.enc(j) for j in orbit) == encs and orbit[-1] ** 2 == j0
        assert j0 not in (F.zero(), F.one())
        assert not seen.intersection(encs)
        seen.update(encs)
        minpoly = j0.minpoly()
        orbits.append({'j_canonical': str(encs[0]), 'b_canonical': str(m83.enc(1 / j0)),
                       'gamma2_factor_nonzero_exponents': [k for k, c in enumerate(p.list()) if c],
                       'j_minpoly_nonzero_exponents': [k for k, c in enumerate(minpoly.list()) if c]})
    orbits.sort(key=lambda row: int(row['j_canonical']))
    for i, row in enumerate(orbits):
        row['orbit'] = i
    assert len(seen) == m83.FLOOR_SIZE and 1 not in seen
    stage('roots', distinct_j=len(seen))

    # Group order certificate: a point with [4 ell]R = O and [4]R != O has
    # order divisible by the prime ell, and 4*ell is the only multiple of ell
    # in the Hasse interval (ell > 4 sqrt(q)).
    set_random_seed(20260923)
    certified = 0
    for row in orbits:
        j = m83.dec(row['j_canonical'])
        for shift in range(m83.ORBIT):
            E = m83.curve(1 / j)
            while True:
                R = E.random_point()
                if not (4 * R).is_zero():
                    break
            assert (m83.N * R).is_zero()
            certified += 1
            j = j * j
    stage('order_certificates', curves=certified)
    t0 = time.perf_counter()
    pari_counts = [int(m83.curve(1 / m83.dec(row['j_canonical'])).cardinality(algorithm='pari'))
                   for row in orbits]
    assert all(c == m83.N for c in pari_counts)
    pari_seconds = time.perf_counter() - t0
    stage('pari_cardinality', orbits=len(pari_counts), seconds=pari_seconds)

    # Ideal-class orders: the prime above 2 must have order 83 (Frobenius orbit
    # length); record small split primes for the horizontal graph.
    D = m83.D_FLOOR
    cl = pari.quadclassunit(D)
    assert int(cl[0]) == m83.FLOOR_SIZE and len(cl[1]) == 1
    def form_order(p):
        f = pari.qfbprimeform(D, p)
        one = pari.qfbpow(f, 0)
        n = m83.FLOOR_SIZE
        for r in (2, 3, 13, 83):
            while n % r == 0 and pari.qfbpow(f, n // r) == one:
                n //= r
        return n
    split = [p for p in range(3, 60) if ZZ(p).is_prime() and p != 7 and pari.kronecker(D, p) == 1]
    class_orders = {str(p): form_order(p) for p in [2] + split}
    assert class_orders['2'] == m83.ORBIT
    stage('class_group', structure=[int(c) for c in cl[1]], orders=class_orders)

    result = {
        'scope': 'public curve construction and point counting; no index-calculus timing',
        'discriminant': D, 'conductor': m83.F1, 'class_number': m83.FLOOR_SIZE,
        'class_group_structure': [int(c) for c in cl[1]],
        'ideal_class_orders': class_orders,
        'class_polynomial': 'PARI polclass(D, 5): gamma_2 = j^(1/3), CRT method',
        'class_polynomial_mod2_sha256': stored_sha,
        'class_polynomial_integer_check': check,
        'field_modulus_nonzero_exponents': [0, 2, 4, 7, 83],
        'encoding': 'integer bit i is the coefficient of z^i modulo the field modulus',
        'mod_2_factor_degrees': [m83.ORBIT] * m83.N_ORBITS,
        'orbits': orbits,
        'curve_naming': 'O<orbit>-<shift>: j = j_canonical^(2^shift), b = 1/j, y^2 + xy = x^3 + b',
        'group_order': str(m83.N),
        'order_certificates': certified,
        'pari_cardinality_one_per_orbit': len(pari_counts),
        'pari_cardinality_seconds': pari_seconds,
        'all_checks_passed': True,
        'construction_seconds': time.perf_counter() - started,
    }
    (out / 'inventory.json').write_text(json.dumps(result, indent=1) + '\n')
    stage('complete', orbits=len(orbits), curves=certified)


if __name__ == '__main__':
    main()
