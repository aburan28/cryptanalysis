#!/usr/bin/env python3
"""The Riemann-Roch encodings, solved by WDSat and by CryptoMiniSat.

    python3 wdsat_rr_panel.py [--n 9] [--targets 8] [--budget 10] [--json out]

Both arms get the **same equations**, from the same `ir.Prog`, for the same
target and formulation.  WDSat's ANF mode takes no OR-clauses (see
`wdsat.py`), so the domain constraints the CNF frontend would add are
withheld from *both* arms and the models are filtered afterwards; the CNF
arm with those constraints is run separately and labelled separately.

Unit: conflicts, each solver's own counter.  Boundary: exhaustive search
over the free variables.  Wall-clock is a practicality note, never the
metric.  See `research/notes/ecc2k130/RESEARCH_ECC2K130_WDSAT.md` for the
falsification target this was written against.

No type hints, camelCase identifiers, no itertools (project convention).
"""

import argparse
import json
import os
import platform
import subprocess
import sys
import tempfile
import time

import curves
import cnf as cnfmod
import decomp
import field
import nagaodecomp as nagao
import wdsat

WDSAT_SRC = os.environ.get('WDSAT_SRC', '/tmp/ec-baseline-cache/vendor/WDSat/src')


def firstTarget(f, curve, skip=0):
    """A finite curve point that is the sum of three factor-base points.

    Reuses the frontend's own certificate builder, so the instance is one
    the encoding is meant to satisfy rather than an arbitrary point.
    """
    pts = []
    for x in range(1, min(1 << f.m, 200)):
        p = curve.pointFromX(f.fromCoords(x))
        if p is not None:
            pts.append(p)
    seen = 0
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            for k in range(j + 1, len(pts)):
                chosen = [pts[i], pts[j], pts[k]]
                target = curve.add(curve.add(chosen[0], chosen[1]), chosen[2])
                if target is None or target[0] == 0:
                    continue
                cert = nagao.certificateForPoints(f, curve, chosen, target)
                if cert is None:
                    continue
                if seen < skip:
                    seen += 1
                    continue
                return chosen, target, cert
    return None, None, None


def addNonzeroWitnesses(prog, roots, m, nring, leaf, formulation, core=False):
    """Pin the RR chart's domain inside the ANF, using field inverses.

    The CNF frontend states the domain as disjunctions -- `b != 0`, the
    abscissas nonzero and pairwise distinct -- and WDSat's ANF mode cannot
    read a disjunction (see `wdsat.py`).  Over a field a nonzero condition
    has an equational form that ANF *can* carry: `v != 0` exactly when
    some `u` has `v * u = 1`.  So each condition becomes a fresh witness
    vector and one field multiplication, quadratic in the ONB
    coordinates, and the domain survives into both arms.

    It is not free: seven witnesses at `m` bits each, plus their multiply
    circuits, and the algebra pays what the clause database used to.
    Returns the names of the witness vectors.
    """
    one = [prog.addInput('one', j) for j in range(m)]
    mul = lambda v, w: decomp.onbMul(prog, v, w, m, leaf)

    def vectorOf(name):
        return [prog.addInput(name, j) for j in range(m)]

    def nonzero(vec, witness):
        u = vectorOf(witness)
        product = mul(vec, u)
        for j in range(m):
            roots.append(prog.xor(product[j], one[j]))
        return witness

    # `core` drops the conditions that can be filtered from a model
    # afterwards, keeping only what the solver needs to avoid drowning in
    # degenerate solutions.  Each dropped condition is one field multiply
    # fewer, which is what decides whether the instance fits under
    # WDSat's `__MAX_ANF_ID__` ceiling at all.
    names = []
    xs = [[prog.addInput('p%d' % i, j) for j in range(m)] for i in range(3)]
    b = [prog.addInput('b', j) for j in range(m)]
    xr = [prog.addInput('r', j) for j in range(m)]
    names.append(nonzero(b, 'ub'))
    for i in range(3):
        names.append(nonzero(xs[i], 'up%d' % i))
    for i in range(3):
        for k in range(i + 1, 3):
            diff = [prog.xor(xs[i][j], xs[k][j]) for j in range(m)]
            names.append(nonzero(diff, 'ud%d%d' % (i, k)))
    # reconstructWitness requires the three abscissas and the target's to
    # be four distinct values, so the chart excludes p_i = x_R as well.
    if not core:
        for i in range(3):
            diff = [prog.xor(xs[i][j], xr[j]) for j in range(m)]
            names.append(nonzero(diff, 'ur%d' % i))
    return names


def equationsOnlyAssignment(f, target):
    """The inputs both arms fix: the target coordinates and the field unit."""
    xr = f.toCoords(target[0])
    yr = f.toCoords(target[1])
    assign = {}
    for j in range(f.m):
        assign[('r', j)] = (xr >> j) & 1
        assign[('s', j)] = (yr >> j) & 1
        assign[('one', j)] = 1
    return assign, xr, yr


def runWdsat(prog, roots, assign, tmp, budget, gaussian):
    system, varOf = wdsat.exportAnf(prog, roots, assign)
    exe, values = wdsat.buildSolver(WDSAT_SRC, system, tmp)
    path = os.path.join(tmp, 'rr.anf')
    verdict = wdsat.solve(exe, system, path, timeout=budget, gaussian=gaussian)
    return system, varOf, verdict, values


def runCryptoMiniSat(prog, roots, assign, f, budget):
    """The same equations through the CNF/XOR frontend the RR work uses."""
    from pysat.solvers import CryptoMinisat
    c = cnfmod.Cnf()
    lits = {}
    varOf = {}
    names = ['p0', 'p1', 'p2', 'y0', 'y1', 'y2', 'a', 'b']
    names += ['ub', 'up0', 'up1', 'up2', 'ud01', 'ud02', 'ud12',
              'ur0', 'ur1', 'ur2']
    for name in names:
        for j in range(f.m):
            key = (name, j)
            v = c.newVar()
            lits[key] = v
            varOf[key] = v
    for key, bit in assign.items():
        lits[key] = c.true if bit else c.false
    for lit in prog.emitCnf(roots, lits, c):
        c.assertZero(lit)
    solver = CryptoMinisat()
    started = time.time()
    try:
        for clause in c.clauses:
            solver.add_clause(clause)
        for xlits, rhs in c.xors:
            solver.add_xor_clause(xlits, rhs)
        # Both budgets must be set: pysat's CryptoMiniSat binding passes
        # them straight through and an unset one arrives as None.  The
        # conflict cap is the one the RR comparison already used.
        solver.conf_budget(100000)
        solver.time_budget(int(budget))
        ok = solver.solve_limited()
        seconds = time.time() - started
        conflicts = None
        try:
            stats = solver.accum_stats()
            if isinstance(stats, dict):
                conflicts = stats.get('conflicts')
        except (AttributeError, NotImplementedError):
            conflicts = None
        model = None
        if ok:
            raw = solver.get_model()
            model = {}
            for lit in raw:
                model[abs(lit)] = 1 if lit > 0 else 0
        return {'sat': ok, 'model': model, 'varOf': varOf, 'cnf': c,
                'conflicts': conflicts, 'seconds': seconds}
    finally:
        solver.delete()


def verifyWitness(f, curve, target, xs, ys, a, b):
    """Rebuild the relation from the abscissas alone and check its sum."""
    decoded = {'xs': xs, 'ys': ys, 'a': a, 'b': b}
    try:
        return nagao.reconstructWitness(f, curve, decoded, target) is not None
    except (ValueError, ZeroDivisionError):
        return False


def readVector(f, values, name):
    out = 0
    for j in range(f.m):
        bit = values.get((name, j))
        if bit is None:
            return None
        out |= bit << j
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=9)
    ap.add_argument('--targets', type=int, default=8)
    ap.add_argument('--budget', type=float, default=10.0)
    ap.add_argument('--json', default='')
    ap.add_argument('--core-witnesses', action='store_true',
                    help='drop the p_i != x_R conditions and filter those '
                         'models afterwards, to fit under __MAX_ANF_ID__')
    args = ap.parse_args()

    f = field.Onb(args.n)
    curve = curves.Curve(f)
    tmp = tempfile.mkdtemp(prefix='wdsat-rr-')
    rows = []

    for formulation in nagao.FORMULATIONS:
        leaf = min(args.n, 12)
        prog, roots = nagao.buildSystem(args.n, f.n, leaf, formulation)
        roots = list(roots)
        witnesses = addNonzeroWitnesses(prog, roots, args.n, f.n, leaf,
                                        formulation, args.core_witnesses)
        for t in range(args.targets):
            chosen, target, cert = firstTarget(f, curve, skip=t)
            if target is None:
                break
            assign, xr, yr = equationsOnlyAssignment(f, target)
            row = {'n': args.n, 'formulation': formulation, 'target': t,
                   'xr': xr, 'yr': yr, 'witnesses': witnesses}

            for gaussian in (True, False):
                system, varOf, verdict, values = runWdsat(
                    prog, roots, assign, tmp, args.budget, gaussian)
                arm = 'wdsat_xg' if gaussian else 'wdsat_plain'
                row[arm] = {
                    'sat': verdict.sat,
                    'outcome': verdict.outcome,
                    'conflicts': verdict.conflicts,
                    'seconds': round(verdict.seconds, 4),
                    'vars': system.nVars,
                    'equations': len(system.equations),
                }
                row['free_vars'] = len(varOf)
                row['config'] = values
                if verdict.sat:
                    read = {}
                    for key, var in varOf.items():
                        read[key] = verdict.value(var)
                    xs = [readVector(f, read, 'p%d' % i) for i in range(3)]
                    ys = [readVector(f, read, 'y%d' % i) for i in range(3)] \
                        if formulation == 'incidence' else []
                    a = readVector(f, read, 'a')
                    b = readVector(f, read, 'b')
                    ok = None not in xs and a is not None and b is not None \
                        and verifyWitness(f, curve, target, xs, ys, a, b)
                    row[arm]['witness_verified'] = bool(ok)

            cms = runCryptoMiniSat(prog, roots, assign, f, args.budget)
            row['cryptominisat'] = {
                'sat': cms['sat'],
                'outcome': ('sat' if cms['sat'] is True
                            else 'unsat' if cms['sat'] is False
                            else 'timeout'),
                'conflicts': cms['conflicts'],
                'seconds': round(cms['seconds'], 4),
            }
            if cms['sat']:
                read = {}
                for key, var in cms['varOf'].items():
                    read[key] = cms['model'].get(var)
                xs = [readVector(f, read, 'p%d' % i) for i in range(3)]
                ys = [readVector(f, read, 'y%d' % i) for i in range(3)] \
                    if formulation == 'incidence' else []
                a = readVector(f, read, 'a')
                b = readVector(f, read, 'b')
                ok = None not in xs and a is not None and b is not None \
                    and verifyWitness(f, curve, target, xs, ys, a, b)
                row['cryptominisat']['witness_verified'] = bool(ok)
            rows.append(row)
            report(row)

    summary = {
        'generated': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'host': platform.platform(),
        'python': sys.version.split()[0],
        'budget_seconds': args.budget,
        'wdsat_src': WDSAT_SRC,
        'unit': 'conflicts (each solver own counter); seconds is a practicality note',
        'note': 'equations only; WDSat ANF mode takes no OR-clauses, so the '
                'domain constraints are withheld from both arms',
        'rows': rows,
    }
    if args.json:
        fh = open(args.json, 'w')
        json.dump(summary, fh, indent=2, sort_keys=True)
        fh.write('\n')
        fh.close()
    tally(rows)


def decided(entry):
    return entry is not None and entry.get('sat') is not None


def report(row):
    def show(name):
        e = row.get(name)
        if e is None:
            return '%-14s   —' % name
        # `sat` is a tri-state and the missing case is the important one:
        # CryptoMiniSat's solve_limited returns None when the conflict or
        # time budget expires, which is neither a model nor a refutation.
        # Deriving the label with `if e['sat'] else 'UNSAT'` printed those
        # non-decisions as disproofs.
        if e['sat'] is True:
            state = 'SAT'
        elif e['sat'] is False:
            state = 'UNSAT'
        else:
            state = e.get('outcome') or 'undecided'
        wit = e.get('witness_verified')
        mark = '' if wit is None else (' witness ok' if wit else ' WITNESS BAD')
        return '%-14s %-8s conflicts %-8s %6.2fs%s' % (
            name, state, e['conflicts'], e['seconds'], mark)
    print('n=%d %s target %d' % (row['n'], row['formulation'], row['target']))
    for name in ('wdsat_xg', 'wdsat_plain', 'cryptominisat'):
        print('   ' + show(name))
    sys.stdout.flush()


def tally(rows):
    print()
    print('=== decided / attempted, by arm and formulation ===')
    print()
    forms = []
    for r in rows:
        if r['formulation'] not in forms:
            forms.append(r['formulation'])
    print('| formulation | arm | decided | of | witnesses verified | bad witnesses |')
    print('|---|---|---:|---:|---:|---:|')
    for form in forms:
        subset = [r for r in rows if r['formulation'] == form]
        for arm in ('wdsat_xg', 'wdsat_plain', 'cryptominisat'):
            ok = sum(1 for r in subset if decided(r.get(arm)))
            good = sum(1 for r in subset
                       if r.get(arm, {}).get('witness_verified') is True)
            bad = sum(1 for r in subset
                      if r.get(arm, {}).get('witness_verified') is False)
            print('| %s | %s | %d | %d | %d | %d |'
                  % (form, arm, ok, len(subset), good, bad))
    print()
    print('A timeout is neither a model nor a refutation and is not counted as either.')


if __name__ == '__main__':
    main()
