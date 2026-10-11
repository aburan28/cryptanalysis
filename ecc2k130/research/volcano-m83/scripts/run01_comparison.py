"""Run-01: bounded all-curve comparison on E0 and all 6474 conductor-6473 curves.

Port of the ECC2K-130 run-01 protocol to F_(2^83).  For each curve and
profile (k=4 polynomial, k=4 random, k=5 polynomial):

  * factor base: nonzero x in a fixed k-dimensional F_2-subspace that lift to
    rational points, both signs, with the Z/4 tag of [ELL]P;
  * exact image: all sums of three distinct-x signed points, filtered to the
    prime-order subgroup by total tag 0;
  * two satisfiable targets drawn from that image and one unsatisfiable
    subgroup target; for each, the S4 Boolean system (resultant form, exact
    membership ANF, pairwise distinct-x, field equations), full F_2 row
    reduction, libSingular std, root-count verification against the group
    law, and the formal degree of regularity of the top homogeneous ideal.

Caps are per stage and measure process CPU time (native/libcpualarm), so
censoring does not depend on machine load; ECC2K-130 run-01 used wall-clock
caps.  A capped stage is recorded as censored and never converted into a
degree.  Timings are reported as both wall and CPU seconds.  No discrete
logarithm is computed.

Because the floor is 25 times larger than ECC2K-130's, the study is split:
  census: all 6475 curves x 3 profiles, exact images; solver cells for k=4 polynomial
    sage -python run01_comparison.py --ids all --gb 4:polynomial --shards 6 --shard-index I --output ...
  panel: E0, orbit O00, and shift 00 of every orbit; solver cells for the other two profiles
    sage -python run01_comparison.py --ids panel --plan 4:random,5:polynomial --gb all ...
"""
import argparse
from collections import defaultdict
import hashlib
import itertools
import json
import math
import random
import time
from pathlib import Path

from sage.all import GF, PolynomialRing, prod
from cysignals.alarm import AlarmInterrupt

import m83
from m83 import alarm, cancel_alarm

FIELD, W, ELL = m83.FIELD, m83.W, m83.ELL
enc, dec, point_key = m83.enc, m83.dec, m83.point_key


def coordinate_basis(k, profile):
    if profile == 'polynomial':
        return [W ** i for i in range(k)]
    rng = random.Random(20260923)
    basis, pivots = [], {}
    while len(basis) < k:
        u = rng.getrandbits(m83.M)
        v = u
        while v and v.bit_length() - 1 in pivots:
            v ^= pivots[v.bit_length() - 1]
        if v:
            pivots[v.bit_length() - 1] = v
            basis.append(dec(u))
    return basis


def factor_domain(E, k, profile):
    basis = coordinate_basis(k, profile)
    vals = [sum((basis[i] for i in range(k) if mask >> i & 1), FIELD.zero()) for mask in range(1 << k)]
    lifts, tags, torsion = {}, {}, {}
    start = time.perf_counter()
    for mask, x in enumerate(vals):
        if x == 0:
            continue
        pts = E.lift_x(x, all=True)
        if pts:
            assert len(pts) == 2 and pts[1] == -pts[0]
            p = min(pts, key=lambda p: enc(p[1]))
            lifts[mask] = (p, -p)
            torsion[mask] = ELL * p
            assert (4 * torsion[mask]).is_zero()
    generators = [q for q in torsion.values() if not q.is_zero() and not (2 * q).is_zero()]
    if generators:
        T = generators[0]
        table = {point_key(i * T): i for i in range(4)}
    else:
        nonzero = [q for q in torsion.values() if not q.is_zero()]
        table = {None: 0}
        if nonzero:
            table[point_key(nonzero[0])] = 2
    for mask, q in torsion.items():
        z = table[point_key(q)]
        tags[mask] = (z, (-z) % 4)
    return {'basis': basis, 'values': vals, 'lifts': lifts, 'tags': tags,
            'setup_seconds': time.perf_counter() - start}


def enumerate_image(domain):
    start = time.perf_counter()
    image = defaultdict(set)
    full = set()
    eligible = total = infinity = 0
    ids = sorted(domain['lifts'])
    for tri in itertools.combinations(ids, 3):
        for signs in itertools.product(range(2), repeat=3):
            pts = [domain['lifts'][i][s] for i, s in zip(tri, signs)]
            target = pts[0] + pts[1] + pts[2]
            key = point_key(target)
            total += 1
            if key is None:
                infinity += 1
            else:
                full.add(key)
            if sum(domain['tags'][i][s] for i, s in zip(tri, signs)) % 4 == 0:
                eligible += 1
                if key is not None:
                    image[key].add(tri)
    assert total == 8 * math.comb(len(ids), 3)
    return {'image': image, 'full_distinct_targets': len(full), 'eligible_signed_triples': eligible,
            'all_signed_triples': total, 'infinity_triples': infinity,
            'enumeration_seconds': time.perf_counter() - start}


def make_equations(b, target_x, domain, k):
    start = time.perf_counter()
    nv = 3 * k

    def add(*polys):
        d = {}
        for p in polys:
            for mono, c in p.items():
                v = d.get(mono, FIELD.zero()) + c
                if v:
                    d[mono] = v
                elif mono in d:
                    del d[mono]
        return d

    def mult(p, q):
        d = {}
        for mono, c in p.items():
            for n, e in q.items():
                z = mono | n
                v = d.get(z, FIELD.zero()) + c * e
                if v:
                    d[z] = v
                elif z in d:
                    del d[z]
        return d

    def sq(p):
        return {mono: c * c for mono, c in p.items()}

    xs = [{1 << (block * k + i): c for i, c in enumerate(domain['basis'])} for block in range(3)]
    x, y, z = xs
    r = target_x
    a1 = sq(add(x, y)); b1 = mult(x, y); c1 = add(sq(b1), {0: b})
    a2 = sq(add(z, {0: r})); b2 = mult(z, {0: r}); c2 = add(sq(b2), {0: b})
    s4 = add(sq(add(mult(a1, c2), mult(a2, c1))),
             mult(add(mult(a1, b2), mult(a2, b1)), add(mult(b1, c2), mult(b2, c1))))
    squarefree = {mono: enc(c) for mono, c in s4.items()}
    S = PolynomialRing(GF(2), nv, names=['u%d' % i for i in range(nv)], order='degrevlex')
    vs = S.gens()
    bits = [{} for _ in range(m83.M)]
    for mask, coef in squarefree.items():
        exps = tuple((mask >> i) & 1 for i in range(nv))
        while coef:
            lo = coef & -coef
            bits[lo.bit_length() - 1][exps] = 1
            coef ^= lo
    raw = [S(d) for d in bits if d]
    truth = [0 if i in domain['lifts'] else 1 for i in range(1 << k)]
    anf = truth[:]
    for i in range(k):
        for mono in range(1 << k):
            if mono >> i & 1:
                anf[mono] ^= anf[mono ^ (1 << i)]
    for block in range(3):
        mem = sum((prod(vs[block * k + i] for i in range(k) if mono >> i & 1)
                   for mono, c in enumerate(anf) if c), S.zero())
        if mem:
            raw.append(mem)
    for a, c in itertools.combinations(range(3), 2):
        raw.append(prod(1 + vs[a * k + i] + vs[c * k + i] for i in range(k)))
    raw.extend(v * v + v for v in vs)
    return S, raw, time.perf_counter() - start


def row_reduce(S, raw):
    start = time.perf_counter()
    ds = [f.dict() for f in raw]
    mons = sorted(set().union(*(set(d) for d in ds)), key=lambda e: (sum(e), tuple(e)))
    index = {mono: i for i, mono in enumerate(mons)}
    inputs = [sum(1 << index[mono] for mono in d) for d in ds]
    pivots = {}
    for row in inputs:
        while row:
            p = row.bit_length() - 1
            if p not in pivots:
                pivots[p] = row
                break
            row ^= pivots[p]
    for p in sorted(pivots):
        for q in sorted(pivots):
            if q > p and (pivots[q] >> p) & 1:
                pivots[q] ^= pivots[p]
    result = []
    for p in sorted(pivots, reverse=True):
        row = pivots[p]
        d = {}
        while row:
            lo = row & -row
            d[mons[lo.bit_length() - 1]] = 1
            row ^= lo
        result.append(S(d))
    for row in inputs:
        while row:
            p = row.bit_length() - 1
            assert p in pivots
            row ^= pivots[p]
    return result, time.perf_counter() - start


def polynomial_cell(curve, domain, image, k, profile, kind, index, cap):
    seed = hashlib.sha256(('%s:%d:%s:%s:%d' % (curve['curve_id'], k, profile, kind, index)).encode()).digest()
    rng = random.Random(int.from_bytes(seed, 'big'))
    E = m83.curve(curve['b'])
    support = image['image']
    if kind == 'satisfiable':
        if not support:
            return {'kind': kind, 'status': 'no_eligible_targets'}
        key = rng.choice(sorted(support))
        target = E(dec(key[0]), dec(key[1]))
        expected = 6 * len(support[key])
    else:
        while True:
            x = dec(rng.getrandbits(m83.M))
            pts = E.lift_x(x, all=True)
            if not pts:
                continue
            target = 4 * pts[0]
            key = point_key(target)
            if key is not None and key not in support:
                break
        expected = 0
    record = {'kind': kind, 'replicate': index, 'target_x': str(key[0]), 'target_y': str(key[1]),
              'expected_ordered_x_solutions': expected}
    stage = 'construction'
    try:
        alarm(cap)
        S, raw, construction = make_equations(dec(curve['b']), target[0], domain, k)
        stage = 'linear_preprocessing'
        eqs, preprocessing = row_reduce(S, raw)
        record.update({'construction_seconds': construction, 'row_reduction_seconds': preprocessing,
                       'raw_equations': len(raw), 'preprocessed_equations': len(eqs),
                       'input_max_degree': max(int(f.degree()) for f in eqs)})
        cancel_alarm()
        stage = 'affine_groebner'
        I = S.ideal(eqs)
        G = None
        try:
            alarm(cap)
            started, cpu = time.perf_counter(), time.process_time()
            G = I.groebner_basis(algorithm='libsingular:std')
            record['groebner_seconds'] = time.perf_counter() - started
            record['groebner_cpu_seconds'] = time.process_time() - cpu
            record['output_groebner_max_degree'] = max(int(f.degree()) for f in G)
            record['groebner_status'] = 'computed'
        except AlarmInterrupt:
            record.update({'groebner_status': 'censored', 'groebner_cap_seconds': cap})
        finally:
            cancel_alarm()
        if G is not None:
            stage = 'affine_verification'
            alarm(cap)
            I.groebner_basis.set_cache(G)
            started = time.perf_counter()
            count = len(I.normal_basis())
            assert count == expected, (curve['curve_id'], kind, count, expected)
            assert all(f.reduce(G) == 0 for f in raw)
            if kind == 'satisfiable':
                replayed = 0
                for tri in support[key]:
                    for ordered in itertools.permutations(tri):
                        assignment = tuple((mask >> i) & 1 for mask in ordered for i in range(k))
                        assert all(g(*assignment) == 0 for g in G)
                        replayed += 1
                assert replayed == expected
                record['independent_group_witness_assignments_replayed'] = replayed
            record['quotient_dimension'] = count
            record['verification_seconds'] = time.perf_counter() - started
            record['groebner_status'] = 'verified'
            cancel_alarm()
        stage = 'top_degree_regularity'
        top = [S({e: c for e, c in f.dict().items() if sum(e) == f.degree()}) for f in eqs]
        H = S.ideal(top)
        try:
            alarm(cap)
            started, cpu = time.perf_counter(), time.process_time()
            HG = H.groebner_basis(algorithm='libsingular:std')
            H.groebner_basis.set_cache(HG)
            nb = H.normal_basis()
            record['degree_of_regularity'] = 0 if not nb else 1 + max(int(mono.degree()) for mono in nb)
            record['top_quotient_dimension'] = len(nb)
            record['regularity_seconds'] = time.perf_counter() - started
            record['regularity_cpu_seconds'] = time.process_time() - cpu
            record['regularity_status'] = 'verified'
        except AlarmInterrupt:
            record.update({'regularity_status': 'censored', 'regularity_cap_seconds': cap})
        finally:
            cancel_alarm()
        both = record.get('groebner_status') == record.get('regularity_status') == 'verified'
        record['status'] = 'verified' if both else 'partial_censored'
    except (TimeoutError, AlarmInterrupt):
        record.update({'status': 'censored', 'censored_stage': stage, 'cap_seconds': cap})
    except Exception as exc:
        record.update({'status': 'error', 'error_stage': stage, 'error': repr(exc)})
    finally:
        cancel_alarm()
    return record


def run_curve(curve, k, profile, reps, cap, cells=True):
    start = time.perf_counter()
    E = m83.curve(curve['b'])
    domain = factor_domain(E, k, profile)
    image = enumerate_image(domain)
    row = {**curve, 'k': k, 'profile': profile, 'factor_base_x_count': len(domain['lifts']),
           'factor_base_signed_point_count': 2 * len(domain['lifts']),
           'basis_integer_encodings': [str(enc(u)) for u in domain['basis']],
           'allowed_x_indices': sorted(domain['lifts']),
           'tag_types': {str(mask): list(t) for mask, t in domain['tags'].items()},
           'factor_base_setup_seconds': domain['setup_seconds'],
           **{key: value for key, value in image.items() if key != 'image'},
           'prime_subgroup_distinct_targets': len(image['image']),
           'prime_subgroup_coverage_denominator': str(ELL - 1),
           'log2_prime_subgroup_coverage': (math.log2(len(image['image'])) - math.log2(ELL - 1)
                                            if image['image'] else None),
           'cells': [], 'cells_measured': cells}
    for i in range(reps if cells else 0):
        row['cells'].append(polynomial_cell(curve, domain, image, k, profile, 'satisfiable', i, cap))
    if cells:
        row['cells'].append(polynomial_cell(curve, domain, image, k, profile, 'unsatisfiable', 0, cap))
    row['total_seconds'] = time.perf_counter() - start
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ids', default='E0')
    ap.add_argument('--reps', type=int, default=2)
    ap.add_argument('--cap', type=int, default=20)
    ap.add_argument('--output', required=True)
    ap.add_argument('--plan', default='4:polynomial,4:random,5:polynomial')
    ap.add_argument('--gb', default='all', help="profiles with solver cells, e.g. 4:polynomial, or 'all'")
    ap.add_argument('--shards', type=int, default=1)
    ap.add_argument('--shard-index', type=int, default=0)
    ap.add_argument('--resume', action='store_true')
    args = ap.parse_args()
    curves = m83.load_inventory()
    if args.ids == 'all':
        selected = {c['curve_id'] for c in curves}
    elif args.ids == 'panel':
        selected = {c['curve_id'] for c in curves
                    if c['curve_id'] == 'E0' or c['orbit'] == 0 or c['shift'] == 0}
    else:
        selected = set(args.ids.split(','))
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if path.exists():
        if not args.resume:
            raise ValueError('refusing to overwrite an existing run')
        for line in path.read_text().splitlines():
            row = json.loads(line)
            done.add((row['curve_id'], row['k'], row['profile']))
    random.Random(2026092301).shuffle(curves)
    curves = [c for i, c in enumerate(curves) if i % args.shards == args.shard_index]
    warm = PolynomialRing(GF(2), 2, 'warm')
    warm.ideal([v * v + v for v in warm.gens()]).groebner_basis(algorithm='libsingular:std')
    plan = [(int(s.split(':')[0]), s.split(':')[1]) for s in args.plan.split(',')]
    gb = None if args.gb == 'all' else {(int(s.split(':')[0]), s.split(':')[1]) for s in args.gb.split(',')}
    with path.open('a') as f:
        for curve in curves:
            if curve['curve_id'] not in selected:
                continue
            for k, profile in plan:
                if (curve['curve_id'], k, profile) in done:
                    continue
                result = run_curve(curve, k, profile, args.reps, args.cap, gb is None or (k, profile) in gb)
                f.write(json.dumps(result) + '\n')
                f.flush()
                print(json.dumps({'curve': curve['curve_id'], 'profile': profile, 'k': k,
                                  'x_count': result['factor_base_x_count'],
                                  'coverage': result['prime_subgroup_distinct_targets'],
                                  'cells': [{q: c.get(q) for q in ['kind', 'status', 'degree_of_regularity',
                                                                   'groebner_seconds', 'error']}
                                            for c in result['cells']],
                                  'seconds': round(result['total_seconds'], 3)}), flush=True)


if __name__ == '__main__':
    main()
