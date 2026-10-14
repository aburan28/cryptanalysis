"""Correctness and step-count validation of rho_frob on the ten planted scalars.

Pure Python (no Sage): rebuilds E0, the run.sage generator procedure and the
ten planted scalars, checks the Frobenius eigenvalue and the canonical form,
then runs the frozen rho design (protocol.json "rho") on every scalar. No
timing is recorded: CPU numbers from this backend are not results.

    python3 validate_rho.py [--reps 64] [--out validation/local-validation.json]
"""

import argparse
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rho_frob as rf  # noqa: E402

SCALARS_SEED = 20260924
N_INSTANCES = 10


def scalars(p=rf.R_ORDER):
    rng = random.Random(SCALARS_SEED)
    return [rng.randrange(2, p - 1) for _ in range(N_INSTANCES)]


def generators(B):
    """run.sage generator(cur, 'E0'): x from random.Random('gen:E0'), then
    cofactor * lift_x(x, all=True)[0]. Sage's lift_x order is not reproduced
    here, so both lifts are returned; they are P and -P."""
    rng = random.Random('gen:E0')
    while True:
        x = rng.randrange(1, 2 ** rf.N_BITS)
        pts = B.lift_x_all(x)
        if pts:
            cands = [B.mul(rf.COFACTOR, T) for T in pts]
            if not B.is_zero(cands[0]):
                return cands


def bootstrap_mean_ci(xs, n=10000, seed=20261014):
    rng = random.Random(seed)
    m = len(xs)
    means = sorted(sum(xs[rng.randrange(m)] for _ in range(m)) / m for _ in range(n))
    return means[int(0.025 * n)], means[int(0.975 * n) - 1]


def check_structure(B, P, lam, r):
    out = {}
    assert B.on_curve(P) and not B.is_zero(P)
    assert B.is_zero(B.mul(r, P)), 'P is not in the order-r subgroup'
    out['order_r'] = True
    assert (lam * lam + lam + 2) % r == 0
    assert B.mul(lam, P) == B.frob(P, 1)
    out['tau_is_lambda'] = True
    # Canonical form is a class invariant, the class has 2n points, and the
    # coefficient unit matches the point.
    rng = random.Random('canon-check')
    lp = [pow(lam, e, r) for e in range(rf.N_BITS)]
    for _ in range(200):
        k = rng.randrange(1, r)
        W = B.mul(k, P)
        Wc, e, eps, key, _ = B.canon(W)
        assert B.mul(eps * lp[e] % r, W) == Wc
        cls = set()
        for e2 in range(rf.N_BITS):
            for s2 in (1, -1):
                V = B.frob(W, e2)
                V = V if s2 > 0 else B.neg(V)
                cls.add(V)
                assert B.canon(V)[3] == key
        assert len(cls) == 2 * rf.N_BITS
    out['canonical_class_invariant_checks'] = 200
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--reps', type=int, default=64)
    ap.add_argument('--out', default=os.path.join(HERE, 'validation', 'local-validation.json'))
    args = ap.parse_args()
    proto = json.load(open(os.path.join(HERE, 'protocol.json')))
    rp = proto['rho']
    B = rf.PyBackend()
    r = rf.R_ORDER
    ss = scalars()
    assert ss == proto['scalars'], 'planted scalars differ from protocol.json'
    gens = generators(B)
    rec = {'backend': 'python', 'note': 'correctness and operation counts only; no timing is a result',
           'scalars': ss, 'reps_per_scalar': args.reps, 'generators': []}
    floor = math.sqrt(math.pi / (4 * rf.N_BITS))
    for gi, P in enumerate(gens):
        lam = rf.frob_eigen(B, P)
        struct = check_structure(B, P, lam, r)
        tables = [rf.WalkTable(B, P, rp['walk_seed_format'] % k, R=rp['R']) for k in range(args.reps)]
        steps, ops, fruitless, restarts, fails, per = [], [], 0, 0, 0, []
        reps = args.reps if gi == 0 else min(8, args.reps)
        for ii, s in enumerate(ss):
            Q = B.mul(s, P)
            row = []
            for k in range(reps):
                st = rf.solve(B, P, Q, lam, tables[k])
                good = st['status'] == 'collision' and st['verified'] and st['log'] == s % r
                fails += not good
                steps.append(st['steps'])
                ops.append(st['group_ops'])
                fruitless += st['fruitless']
                restarts += st['restarts']
                row.append({k2: st[k2] for k2 in ('steps', 'group_ops', 'adds', 'dbls', 'lookahead_extra',
                                                   'fruitless', 'restarts', 'table_entries', 'status',
                                                   'log', 'verified')})
            per.append({'instance': ii, 'scalar': s,
                        'verified': sum(1 for x in row if x['verified'] and x['log'] == s % r),
                        'mean_steps': sum(x['steps'] for x in row) / len(row),
                        'mean_group_ops': sum(x['group_ops'] for x in row) / len(row),
                        'solves': row})
        sq = math.sqrt(r)
        S_steps = [x / sq for x in steps]
        lo, hi = bootstrap_mean_ci(S_steps)
        mS = sum(S_steps) / len(S_steps)
        rec['generators'].append({
            'which': 'lift_x root %d (P%s)' % (gi, '' if gi == 0 else ' negated'),
            'P': list(P), 'lambda': lam, 'structure': struct,
            'solves': len(steps), 'failures': fails, 'fruitless_cycles': fruitless, 'restarts': restarts,
            'mean_steps': sum(steps) / len(steps), 'mean_group_ops': sum(ops) / len(ops),
            'S_steps_mean': mS, 'S_steps_ci95': [lo, hi],
            'S_ops_mean': sum(ops) / len(ops) / sq,
            'floor_S': floor, 'S_steps_over_floor': mS / floor,
            'S_steps_over_floor_ci95': [lo / floor, hi / floor],
            'per_scalar': per})
        print('generator %d: %d solves, %d failures, mean steps %.1f, S_steps %.4f (%.4f-%.4f), '
              'floor %.4f, ratio %.3f, mean ops %.1f, fruitless %d, restarts %d'
              % (gi, len(steps), fails, sum(steps) / len(steps), mS, lo, hi, floor, mS / floor,
                 sum(ops) / len(ops), fruitless, restarts), flush=True)
    # Stress test of the fruitless-cycle path: R = 2, no look-ahead.
    P = gens[0]
    lam = rf.frob_eigen(B, P)
    stress = {'R': 2, 'lookahead': False, 'solves': 0, 'failures': 0, 'fruitless_cycles': 0, 'restarts': 0,
              'steps': []}
    for k in range(20):
        tb = rf.WalkTable(B, P, 'stress:%d' % k, R=2)
        for ii, s in enumerate(ss):
            st = rf.solve(B, P, B.mul(s, P), lam, tb, lookahead=False)
            stress['solves'] += 1
            stress['failures'] += not (st['status'] == 'collision' and st['verified'] and st['log'] == s % r)
            stress['fruitless_cycles'] += st['fruitless']
            stress['restarts'] += st['restarts']
            stress['steps'].append(st['steps'])
    stress['mean_steps'] = sum(stress['steps']) / len(stress['steps'])
    del stress['steps']
    rec['fruitless_stress'] = stress
    print('stress (R=2, no look-ahead):', stress, flush=True)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w') as f:
        json.dump(rec, f, indent=1)
        f.write('\n')
    if any(g['failures'] for g in rec['generators']) or stress['failures']:
        sys.exit(1)


if __name__ == '__main__':
    main()
