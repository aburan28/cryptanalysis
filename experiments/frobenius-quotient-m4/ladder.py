# m = 4 chained-S_3 decomposition on the Frobenius-stable weight factor base.
#
# One cell = (n, w).  Two arms on the same base and system:
#   planted  -- target is a sum of 4 base points (satisfiable; correctness control)
#   random   -- target is a uniformly random curve point (what relation
#               collection actually pays for; almost always unsatisfiable)
# Every SAT model is lifted and re-added (indexcalc.liftAndCheck).  Budget
# outcomes are recorded as censored, never as UNSAT.
#
#   python3 ladder.py --n 11 --weight 2 --trials 6 --timeout 600 --out cell.json
#
# No type hints, camelCase identifiers (codegen convention).

import argparse
import json
import os
import platform
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'ecc2k130', 'runner', 'codegen'))

import cnf as cnfmod
import curves
import decomp
import indexcalc

POINTS = 4


def solveOne(prog, roots, onb, curve, n, weight, target, maxConflicts, timeout):
    c = cnfmod.Cnf()
    pvars = decomp.encode(prog, roots, n, POINTS, weight, target[0], c)
    for v in pvars:
        c.addClause(v)
    t0 = time.process_time()
    w0 = time.time()
    val, status = indexcalc.solveCnf(c, maxConflicts, timeout)
    cpu = time.process_time() - t0
    wall = time.time() - w0
    row = {'status': status, 'cpu_s': cpu, 'wall_s': wall}
    if status == 'sat':
        coords = []
        for v in pvars:
            cc = 0
            for j in range(n):
                if indexcalc.litValue(val, v[j], c):
                    cc |= 1 << j
            coords.append(cc)
        got = indexcalc.liftAndCheck(onb, curve, coords, target)
        row['verified'] = got is not None
        if got is None:
            row['status'] = 'spurious'
    return row


def randomPoint(onb, curve, n, rng):
    while True:
        x = onb.fromCoords(rng.getrandbits(n))
        p = curve.pointFromX(x)
        if p is not None:
            return p


def reachableSums(curve, base):
    """Every point that is a signed sum of POINTS base points (repetition
    allowed).  A superset of what the system admits, so a solver SAT outside
    it, or UNSAT inside it with distinct points available, is flagged."""
    signed = set()
    for p in base.values():
        signed.add(p)
        signed.add(curve.neg(p))
    s2 = set()
    for a in signed:
        for b in signed:
            s2.add(curve.add(a, b))
    s4 = set()
    for a in s2:
        for b in s2:
            s4.add(curve.add(a, b))
    return s4


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, required=True)
    ap.add_argument('--weight', type=int, required=True)
    ap.add_argument('--trials', type=int, default=6)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--timeout', type=float, default=600)
    ap.add_argument('--max-conflicts', type=int, default=0)
    ap.add_argument('--leaf', type=int, default=12)
    ap.add_argument('--arms', default='planted,random')
    ap.add_argument('--oracle', action='store_true',
                    help='brute-force the reachable 4-sums and record agreement')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    if a.n % 2 == 0:
        raise SystemExit('n must be odd')
    onb = curves.NormalView(a.n)
    curve = curves.CurvePb(onb.pb)
    base, orbits = indexcalc.factorBase(onb, curve, a.weight)
    prog, roots = decomp.buildSystemPb(a.n, onb.taps, onb.rowsNbToPb, POINTS, a.leaf)
    keys = sorted(base.keys())
    reach = reachableSums(curve, base) if a.oracle else None
    rec = {'n': a.n, 'weight': a.weight, 'points': POINTS, 'seed': a.seed,
           'timeout_s': a.timeout, 'max_conflicts': a.max_conflicts,
           'base_points': len(base), 'orbits': len(orbits),
           'gates': prog.bitOpCount(roots), 'solver': 'CryptoMiniSat via python-sat',
           'host': platform.node(), 'python': platform.python_version(),
           'arms': {}}
    for arm in a.arms.split(','):
        rng = random.Random('%s-%d-%d-%d' % (arm, a.n, a.weight, a.seed))
        rows = []
        for t in range(a.trials):
            if arm == 'planted':
                target = None
                for _ in range(POINTS):
                    target = curve.add(target, base[keys[rng.randrange(len(keys))]])
                if target is None:
                    continue
            else:
                target = randomPoint(onb, curve, a.n, rng)
            row = solveOne(prog, roots, onb, curve, a.n, a.weight, target,
                           a.max_conflicts, a.timeout)
            row['trial'] = t
            if reach is not None:
                row['oracle_reachable'] = target in reach
                if row['status'] == 'sat' and not row['oracle_reachable']:
                    raise SystemExit('SAT on an unreachable target: lift check bug')
            rows.append(row)
            print('%s n=%d w=%d trial %d %s %.2fs' % (arm, a.n, a.weight, t,
                  row['status'], row['cpu_s']), flush=True)
            if arm == 'planted' and row['status'] == 'unsat':
                raise SystemExit('planted target reported UNSAT: encoding bug')
        rec['arms'][arm] = rows
        with open(a.out, 'w') as f:
            json.dump(rec, f, indent=1, sort_keys=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
