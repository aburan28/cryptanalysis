# Harness for SAT-based point decomposition on Koblitz curves.
#
# This exists to measure one number: how the cost of a single decomposition
# grows with the field size.  Everything else about index calculus for ECDLP is
# bookkeeping around that, and it is the only thing that decides whether the
# approach can ever reach a curve anyone cares about.  Index calculus does not
# beat rho at m=131 today and nothing here changes that; what is missing from
# the public record is a measured growth curve for a Frobenius-reduced factor
# base on a Koblitz curve, which is what this produces.
#
#   python3 indexcalc.py --m 41 --points 4 --weight 3 --trials 20
#
# No type hints, camelCase identifiers, no itertools (project convention).

import argparse
import random
import sys
import time

import cnf as cnfmod
import curves
import decomp
import field


def combinationsUpTo(n, w):
    """Index subsets of size at most w, smallest first."""
    out = [[]]
    cur = [[]]
    for _ in range(w):
        nxt = []
        for c in cur:
            start = (c[-1] + 1) if c else 0
            for i in range(start, n):
                nxt.append(c + [i])
        out.extend(nxt)
        cur = nxt
    return out


def factorBase(onb, curve, weight):
    """{P : HW(x(P)) <= weight}, and its Frobenius orbits.

    Orbits are what the relation matrix is indexed by, so their count is the
    number of relations a run needs -- the m-fold saving the Koblitz structure
    buys."""
    m = onb.m
    pts = {}
    for sup in combinationsUpTo(m, weight):
        c = 0
        for i in sup:
            c |= 1 << i
        x = onb.fromCoords(c)
        p = curve.pointFromX(x)
        if p is not None:
            pts[c] = p
    orbits = {}
    seen = set()
    for c in pts:
        if c in seen:
            continue
        orb = []
        d = c
        for _ in range(m):
            if d in pts:
                orb.append(d)
            seen.add(d)
            x = onb.frob(onb.fromCoords(d), 1)
            d = onb.toCoords(x)
            if d == c:
                break
        orbits[c] = orb
    return pts, orbits


def solveCnf(c, maxConflicts=0, timeout=0):
    """Solve, optionally under a conflict budget.

    A budget is what makes this usable as a measuring instrument rather than a
    solver: past a certain field size an instance simply does not finish, and
    the useful datum is then "did not finish within N conflicts", not a process
    that never returns.  Returns (model, status) with status one of
    'sat', 'unsat', 'budget'."""
    from pysat.solvers import CryptoMinisat
    s = CryptoMinisat()
    for cl in c.clauses:
        s.add_clause(cl)
    for lits, rhs in c.xors:
        s.add_xor_clause(lits, rhs)
    if maxConflicts or timeout:
        # both budgets have to be numbers: this binding passes them straight
        # through to pycryptosat, which rejects a None
        s.conf_budget(maxConflicts if maxConflicts else 2 ** 31)
        s.time_budget(timeout if timeout else 10 ** 9)
        ok = s.solve_limited()
    else:
        ok = s.solve()
    model = s.get_model() if ok else None
    s.delete()
    if ok is None:
        return None, 'budget'
    if not ok:
        return None, 'unsat'
    val = {}
    for l in model:
        val[abs(l)] = 1 if l > 0 else 0
    return val, 'sat'


def litValue(val, l, c):
    if l == c.true:
        return 1
    if l == c.false:
        return 0
    v = val.get(abs(l), 0)
    return v if l > 0 else 1 - v


def liftAndCheck(onb, curve, coords, target):
    """Turn solved x-coordinates into points and find signs summing to target.

    S_3 says points with these x-coordinates sum to zero for *some* choice of
    y, so the signs are not determined by the system; there are only 2^k of
    them.  A solution can also be spurious -- the system does not require each
    x to be an x-coordinate at all -- so this is where those are rejected."""
    pts = []
    for c in coords:
        p = curve.pointFromX(onb.fromCoords(c))
        if p is None:
            return None
        pts.append(p)
    k = len(pts)
    for mask in range(1 << k):
        # None is the point at infinity throughout, which is also the identity
        # curve.add expects, so the accumulator needs no separate empty state
        acc = None
        for i in range(k):
            q = curve.neg(pts[i]) if (mask >> i) & 1 else pts[i]
            acc = curve.add(acc, q)
        if acc is not None and acc == target:
            signs = []
            for i in range(k):
                signs.append(-1 if (mask >> i) & 1 else 1)
            return pts, signs
    return None


def runTrials(m, points, weight, trials, seed, leaf, verbose, maxConflicts=0, timeout=0):
    # Recovering y from x solves z^2 + z = c by half-trace, which is only valid
    # for odd m; on even m curves.pointFromX asserts deep inside instead of
    # saying why, so refuse here.
    if m % 2 == 0:
        raise ValueError('m must be odd: recovering y from x uses the half-trace')
    onb = field.Onb(m)
    curve = curves.Curve(onb)
    rng = random.Random(seed)
    base, orbits = factorBase(onb, curve, weight)
    if verbose:
        print('m=%d  factor base %d points in %d Frobenius orbits '
              '(relations a full run would need: %d)'
              % (m, len(base), len(orbits), len(orbits)), flush=True)
    prog, roots = decomp.buildSystem(m, onb.n, points, leaf)
    gates = prog.bitOpCount(roots)
    if verbose:
        print('system: %d points, %d S_3 links, %d gates'
              % (points, points - 1, gates), flush=True)

    keys = sorted(base.keys())
    solved = spurious = unsat = budget = 0
    times = []
    for t in range(trials):
        # a target that is decomposable by construction, so a failure to find
        # any decomposition is a bug rather than a property of the target
        chosen = [base[keys[rng.randrange(len(keys))]] for _ in range(points)]
        target = None
        for p in chosen:
            target = curve.add(target, p)
        if target is None:
            continue
        c = cnfmod.Cnf()
        pvars = decomp.encode(prog, roots, m, points, weight,
                              onb.toCoords(target[0]), c)
        t0 = time.time()
        val, status = solveCnf(c, maxConflicts, timeout)
        dt = time.time() - t0
        times.append(dt)
        if status == 'budget':
            budget += 1
            if verbose:
                print('  trial %2d  budget    %7.2fs   (gave up)'
                      % (t, dt), flush=True)
            continue
        if status == 'unsat':
            unsat += 1
            if verbose:
                print('  trial %2d  UNSAT in %.2fs  (target was built from the base)'
                      % (t, dt), flush=True)
            continue
        coords = []
        for v in pvars:
            cc = 0
            for j in range(m):
                if litValue(val, v[j], c):
                    cc |= 1 << j
            coords.append(cc)
        got = liftAndCheck(onb, curve, coords, target)
        if got is None:
            spurious += 1
        else:
            solved += 1
        if verbose:
            st = c.stats()
            print('  trial %2d  %-9s %7.2fs   vars %d clauses %d xors %d'
                  % (t, 'solved' if got else 'spurious', dt,
                     st['vars'], st['clauses'], st['xors']), flush=True)
    times.sort()
    med = times[len(times) // 2] if times else 0.0
    return {'m': m, 'points': points, 'weight': weight, 'gates': gates,
            'base': len(base), 'orbits': len(orbits), 'solved': solved,
            'spurious': spurious, 'unsat': unsat, 'budget': budget,
            'median': med, 'total': sum(times)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--m', type=int, default=11)
    ap.add_argument('--points', type=int, default=3)
    ap.add_argument('--weight', type=int, default=2)
    ap.add_argument('--trials', type=int, default=5)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--leaf', type=int, default=12)
    ap.add_argument('--max-conflicts', type=int, default=0,
                    help='solver conflict budget; 0 = run to completion')
    ap.add_argument('--timeout', type=float, default=0,
                    help='per-instance wall-clock budget in seconds; 0 = none')
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args()
    r = runTrials(args.m, args.points, args.weight, args.trials, args.seed,
                  args.leaf, not args.quiet, args.max_conflicts, args.timeout)
    print('m=%d points=%d weight=%d: solved %d, spurious %d, unsat %d, budget %d, '
          'median %.2fs, gates %d, orbits %d'
          % (r['m'], r['points'], r['weight'], r['solved'], r['spurious'],
             r['unsat'], r['budget'], r['median'], r['gates'], r['orbits']))
    return 0 if r['unsat'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
