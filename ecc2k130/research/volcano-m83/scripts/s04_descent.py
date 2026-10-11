"""Run-04/05: explicit degree-6473 descent from E0 and public-point transport.

Stages (each skips work whose receipt already exists):

  frob     native frobcheck on the E0 torsion point: pi acts on E0[6473] as
           the scalar 2514, and x(P + tau P) = x_P + 1/x_P has order 6473.
  lines    all 6474 kernel lines <P + v tau P>, <tau P>; Velu codomain
           j = 1/(1 + v + v^2) with v = Tr_(F_Q/F_q) x(generator); match to
           the class-polynomial inventory.
  select   choose the explicit-map descendants from the yield census.
  kernels  kernel polynomial (degree 3236) of each selected line by
           Berlekamp-Massey on Tr(x^i); Sage isogeny from it; codomain check;
           transport of the header's public P, Q; subgroup and scalar checks;
           map cost.  No discrete logarithm is computed.

    sage -python s04_descent.py frob|lines|select|kernels
"""
import argparse
import hashlib
import json
import math
import os
import subprocess
import time
from pathlib import Path

from sage.all import PolynomialRing

import m83
import run02_attribution as r2

OUT = m83.OUT / 'run04-explicit-descent'
BIN = m83.ROOT / 'native' / 'isogeny'
FIELD_ARGS = ['83', '7,4,2', '3236', '887']
ELLF = m83.F1


def run(args, **kw):
    return subprocess.run([str(BIN)] + args, capture_output=True, text=True, check=True, **kw)


def stage_frob():
    path = OUT / 'E0-frobcheck.json'
    if path.exists():
        return json.loads(path.read_text())
    out = json.loads(run(['frobcheck', *FIELD_ARGS, '1', str(ELLF), str(m83.FROB_ON_F1),
                          str(OUT / 'E0-P.bin')]).stdout)
    assert out['frobenius_matches'] and out['tau_sum_has_order_ell']
    path.write_text(json.dumps(out, indent=1) + '\n')
    return out


def stage_lines():
    path = OUT / 'line-codomains.json'
    if path.exists():
        return json.loads(path.read_text())
    started = time.perf_counter()
    proc = run(['lines', *FIELD_ARGS, str(ELLF), str(OUT / 'E0-P.bin')], env=dict(os.environ, TOWER_THREADS='3'))
    rows = [json.loads(l) for l in proc.stdout.strip().splitlines()]
    tail = rows.pop()
    assert tail['chain_closes']
    inventory = {c['j']: c['curve_id'] for c in m83.load_inventory() if c['curve_id'] != 'E0'}
    lines = []
    for row in rows:
        v = m83.dec(int(row['trace'], 16))
        bprime = 1 + v + v * v
        j = m83.enc(1 / bprime)
        lines.append({'line': row['line'], 'trace': row['trace'], 'j': str(j),
                      'curve_id': inventory.get(str(j))})
    ids = [l['curve_id'] for l in lines]
    assert len(lines) == ELLF + 1
    assert None not in ids and len(set(ids)) == m83.FLOOR_SIZE
    # tau acts on lines; the codomain of tau(L) is the Frobenius conjugate.
    result = {'kernel_lines': len(lines), 'horizontal_maps_to_j1': sum(l['j'] == '1' for l in lines),
              'distinct_codomains': len(set(ids)), 'all_inventory_curves_matched': True,
              'chain_closes': True, 'native_seconds': tail['seconds'],
              'wall_seconds': time.perf_counter() - started, 'lines': lines}
    path.write_text(json.dumps(result, indent=1) + '\n')
    return result


def stage_select():
    path = OUT / 'selection.json'
    if path.exists():
        return json.loads(path.read_text())
    census = r2.load_census()
    e0 = {k: census[('E0', k, 'polynomial')] for k in (4, 5, 6)}
    desc = sorted({c for (c, k, p) in census if c != 'E0'})
    cov = lambda cid, k: census[(cid, k, 'polynomial')]['prime_subgroup_distinct_targets']
    size = lambda cid, k: census[(cid, k, 'polynomial')]['x_count']
    k5 = [c for c in desc if size(c, 5) == e0[5]['x_count']]
    k56 = [c for c in k5 if size(c, 6) == e0[6]['x_count']]
    k456 = [c for c in k56 if size(c, 4) == e0[4]['x_count']]
    best = lambda pool: max(pool, key=lambda c: (cov(c, 5), c))
    picks = []
    for pool, rule in ((k5, 'E0 x-count at k=5, maximum k=5 coverage (ECC2K-130 B067 analog)'),
                       (k56, 'E0 x-count at k=5 and k=6, maximum k=5 coverage (A090 analog)'),
                       (k456, 'E0 x-count at k=4, 5 and 6, maximum k=5 coverage (B021 analog)')):
        pool = [c for c in pool if c not in [p['curve_id'] for p in picks]]
        if pool:
            c = best(pool)
            picks.append({'curve_id': c, 'rule': rule, 'pool_size': len(pool),
                          **{'k%d_x' % k: size(c, k) for k in (4, 5, 6)},
                          **{'k%d_coverage_vs_E0' % k: cov(c, k) / e0[k]['prime_subgroup_distinct_targets']
                             for k in (4, 5, 6)}})
    result = {'E0': {'k%d_x' % k: e0[k]['x_count'] for k in (4, 5, 6)}, 'selected': picks}
    path.write_text(json.dumps(result, indent=1) + '\n')
    return result


def point_record(P):
    return None if P.is_zero() else {'x': str(m83.enc(P[0])), 'y': str(m83.enc(P[1]))}


def chain_cost(line):
    if line in ('inf', 0, '0'):
        return 0
    v = int(line)
    return min(v, ELLF - v)


def stage_kernels():
    """Kernel polynomials of the selected descendants.

    E0 is defined over F_2, so if L has kernel polynomial K and codomain j,
    tau(L) has kernel polynomial K^sigma (coefficients squared) and codomain
    j^2.  For each selected curve O<o>-<s> the native tool therefore computes
    the line of orbit o that is cheapest to reach from P (chain length
    min(v, 6473 - v)), and the result is conjugated by sigma^(s - s_line).
    """
    all_lines = stage_lines()['lines']
    lines = {l['curve_id']: l for l in all_lines}
    picks = [p['curve_id'] for p in stage_select()['selected']]
    P, Qp = m83.public_points()
    E0 = m83.curve(1)
    R = PolynomialRing(m83.FIELD, 'x')
    results = []
    for cid in picks:
        path = OUT / ('%s-explicit-map.json' % cid)
        if path.exists():
            results.append(json.loads(path.read_text()))
            continue
        orbit, shift = int(cid[1:3]), int(cid[4:])
        same_orbit = [l for l in all_lines if l['curve_id'].startswith('O%02d-' % orbit)]
        base = min(same_orbit, key=lambda l: (chain_cost(l['line']), l['curve_id']))
        base_shift = int(base['curve_id'][4:])
        conj = (shift - base_shift) % m83.M
        line = str(base['line'])
        t0 = time.perf_counter()
        kout = json.loads(run(['kernel', *FIELD_ARGS, str(ELLF), str(OUT / 'E0-P.bin'), line],
                              env=dict(os.environ, TOWER_THREADS='3')).stdout)
        native = time.perf_counter() - t0
        assert kout['vanishes_at_x'] and kout['degree'] == (ELLF - 1) // 2
        coeffs = [m83.dec(int(c, 16)) for c in kout['coefficients_ascending']]
        coeffs = [c ** (2 ** conj) for c in coeffs]
        kpoly = R(coeffs)
        assert kpoly.is_monic() and kpoly.degree() == (ELLF - 1) // 2
        # Characteristic-2 Velu from the kernel polynomial psi (odd degree 6473):
        #   x(phi(P)) = x + u^2 + u,  u = x psi'(x) / psi(x)
        # (x(P+Q) + x(P-Q) = x_P x_Q / (x_P + x_Q)^2 summed over the kernel, psi'' = 0),
        # onto y^2 + xy = x^3 + v x + (1 + v), v = sum of the roots of psi; y -> y + v
        # normalizes it to y^2 + xy = x^3 + b' with b' = 1 + v + v^2.
        t0 = time.perf_counter()
        dpsi = kpoly.derivative()
        v = kpoly[kpoly.degree() - 1]
        bprime = 1 + v + v * v
        target_j = m83.dec(lines[cid]['j'])
        assert 1 / bprime == target_j
        target = m83.curve(bprime)
        build = time.perf_counter() - t0

        def phix(pt):
            x = pt[0]
            u = x * dpsi(x) / kpoly(x)
            return u * u + u + x

        def lift(xx):
            return target.lift_x(xx, all=True)
        t0 = time.perf_counter()
        xP = phix(P)
        per_point = time.perf_counter() - t0
        mP = min(lift(xP), key=lambda R_: m83.enc(R_[1]))
        xQ = phix(Qp)
        xPQ = phix(P + Qp)
        cands = [R_ for R_ in lift(xQ) if (mP + R_)[0] == xPQ]
        assert len(cands) == 1
        mQ = cands[0]
        assert not mP.is_zero() and not mQ.is_zero()
        assert (m83.ELL * mP).is_zero() and (m83.ELL * mQ).is_zero()
        for s in (2, 3, ELLF):
            assert phix(s * P) == (s * mP)[0] and phix(s * Qp) == (s * mQ)[0]
        rng_pts = []
        for _ in range(4):
            R1, R2 = E0.random_point(), E0.random_point()
            if R1.is_zero() or R2.is_zero() or (R1 + R2).is_zero():
                continue
            i1, i2 = lift(phix(R1)), lift(phix(R2))
            assert i1 and i2
            assert any((a + b_)[0] == phix(R1 + R2) for a in i1 for b_ in i2)
            rng_pts.append(True)
        coeffs = [str(m83.enc(c)) for c in kpoly.list()]
        row = {'curve_id': cid, 'line': str(lines[cid]['line']), 'computed_line': line,
               'computed_line_curve': base['curve_id'], 'chain_steps': chain_cost(base['line']),
               'frobenius_conjugation_power': conj,
               'degree': ELLF, 'kernel_polynomial_degree': int(kpoly.degree()),
               'kernel_polynomial_sha256': hashlib.sha256(json.dumps(coeffs, separators=(',', ':')).encode()).hexdigest(),
               'kernel_polynomial_coefficients': coeffs,
               'target_j': lines[cid]['j'], 'target_b': str(m83.enc(1 / target_j)),
               'mapped_P': point_record(mP), 'mapped_Q': point_record(mQ),
               'images_killed_by_ell': True, 'gcd_6473_ell': math.gcd(ELLF, m83.ELL),
               'scalar_commutation_checked': [2, 3, ELLF],
               'native_kernel_seconds': native, 'native_kernel_detail': {k: kout[k] for k in
                                                                         ('chain_seconds', 'sequence_seconds', 'total_seconds')},
               'codomain_setup_seconds': build, 'first_point_map_seconds': per_point,
               'evaluation': 'characteristic-2 Velu from the kernel polynomial; sign of phi(Q) fixed by '
                             'x(phi(P) + phi(Q)) = x(phi(P + Q)); additivity checked on %d random point pairs' % len(rng_pts),
               'no_discrete_log_computed': True}
        path.write_text(json.dumps(row, indent=1) + '\n')
        results.append(row)
        print(json.dumps({k: row[k] for k in ('curve_id', 'line', 'native_kernel_seconds',
                                               'codomain_setup_seconds', 'first_point_map_seconds')}), flush=True)
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('stage', choices=['frob', 'lines', 'select', 'kernels', 'all'])
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.stage in ('frob', 'all'):
        print(json.dumps(stage_frob()))
    if args.stage in ('lines', 'all'):
        r = stage_lines()
        print(json.dumps({k: v for k, v in r.items() if k != 'lines'}))
    if args.stage in ('select', 'all'):
        print(json.dumps(stage_select(), indent=1))
    if args.stage in ('kernels', 'all'):
        stage_kernels()


if __name__ == '__main__':
    main()
