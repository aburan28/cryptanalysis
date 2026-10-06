"""Exhaustive projected-solution comparison, not an attack-speed benchmark.

Run from any directory with pycryptosat installed. The contract is frozen in
research/nagao_relations/experiments/nagao_relation_contract.json.
Existing files are never overwritten.
"""

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import random
import subprocess
import sys
import time
import traceback

import cnf as cnfmod
import curves
import decomp
import field
import indexcalc
import nagaodecomp


def affinePoints(onb, curve):
    # pointFromX deliberately omits the valid 2-torsion point at x=0.
    points = [(0, onb.one())]
    for coords in range(1, 1 << onb.m):
        point = curve.pointFromX(onb.fromCoords(coords))
        if point is not None:
            points.append(point)
            neg = curve.neg(point)
            if neg != point:
                points.append(neg)
    assert len(points) + 1 == curves.curveOrder(onb.m)
    assert all(curve.onCurve(point) for point in points)
    return points


def oracleTable(onb, curve, weight):
    """Independent curve additions; no polynomial or RR certificate is used."""
    base, _ = indexcalc.factorBase(onb, curve, weight)
    xs = sorted(base)
    table = {}
    tested = 0
    for i in range(len(xs)):
        for j in range(i + 1, len(xs)):
            for k in range(j + 1, len(xs)):
                coords = (xs[i], xs[j], xs[k])
                points = [base[x] for x in coords]
                for signs in range(8):
                    total = None
                    for bit, point in enumerate(points):
                        total = curve.add(total, curve.neg(point) if signs & (1 << bit) else point)
                    tested += 1
                    if total is None or onb.toCoords(total[0]) in coords:
                        continue
                    table.setdefault(total, set()).add(coords)
    return table, {"factor_base_abscissas": len(xs), "signed_triples_tested": tested}


def cnfSatisfied(c, model):
    for clause in c.clauses:
        if not any(bool(model[abs(lit)]) == (lit > 0) for lit in clause):
            return False
    for lits, rhs in c.xors:
        parity = False
        for lit in lits:
            parity ^= bool(model[abs(lit)]) == (lit > 0)
        if parity != rhs:
            return False
    return True


def compareInstance(onb, curve, target, weight, variant, expected, seconds, maximumModels):
    import pycryptosat

    started = time.perf_counter()
    n = onb.m
    xr, yr = (onb.toCoords(value) for value in target)
    c = cnfmod.Cnf()
    if variant == 'chained-s3':
        prog, roots = decomp.buildSystem(n, onb.n, 3, min(12, n))
        pvars = decomp.encode(prog, roots, n, 3, weight, xr, c, orderPoints=False)
        nagaodecomp.addRestrictedDomain(c, pvars, xr, orderPoints=True)
        variables = {'pvars': pvars}
    else:
        formulation = variant.removeprefix('rr-')
        prog, roots = nagaodecomp.buildSystem(n, onb.n, min(12, n), formulation)
        variables = nagaodecomp.encode(prog, roots, n, weight, xr, yr, c, formulation)
        pvars = variables['pvars']
    built = time.perf_counter()
    structural = c.stats()
    structural['ir_bit_operations_per_evaluation'] = prog.bitOpCount(roots)
    structural['cnf_sha256'] = hashlib.sha256(json.dumps(
        [c.nVars, c.clauses, c.xors], separators=(',', ':')).encode()).hexdigest()

    solver = pycryptosat.Solver(threads=1)
    for clause in c.clauses:
        solver.add_clause(clause)
    for lits, rhs in c.xors:
        solver.add_xor_clause(lits, rhs)
    solutions = set()
    rejected = []
    calls = 0
    complete = False
    errors = []
    deadline = time.perf_counter() + seconds
    while calls < maximumModels:
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            break
        ok, values = solver.solve(time_limit=remaining)
        calls += 1
        if ok is None:
            break
        if not ok:
            complete = True
            break
        model = {i: value for i, value in enumerate(values) if i}
        if not cnfSatisfied(c, model):
            errors.append('solver model fails emitted constraints')
            break
        coords = tuple(sorted(sum(int(model[v]) << bit for bit, v in enumerate(vec)) for vec in pvars))
        if variant != 'chained-s3':
            decoded = nagaodecomp.decode(model, variables, c)
            if not nagaodecomp.reconstructWitness(onb, curve, decoded, target):
                errors.append('RR certificate fails independent reconstruction')
                break
        # Verify using all signs in the independent affine group arithmetic.
        verified = indexcalc.liftAndCheck(onb, curve, list(coords), target)
        if verified is None:
            rejected.append(list(coords))
            if variant != 'chained-s3':
                errors.append('RR projected tuple has no group-law decomposition')
                break
        else:
            solutions.add(coords)
        # Block the actual model ordering; the shared domain uses numeric order.
        solver.add_clause([-v if model[v] else v for vec in pvars for v in vec])
    finished = time.perf_counter()
    del solver
    missing = sorted(expected - solutions) if complete else None
    extra = sorted(solutions - expected)
    return {
        'variant': variant, 'target': [xr, yr], 'field_degree': n, 'weight': weight,
        'complete': complete, 'correct': complete and not missing and not extra and not errors,
        'expected_projected_solutions': len(expected),
        'projected_solutions': [list(row) for row in sorted(solutions)],
        'missing': missing, 'extra': extra, 'errors': errors,
        'rejected_semaev_models': rejected, 'solver_calls': calls,
        'structure': structural,
        'diagnostic_seconds': {'construction': built - started, 'solve_enumerate_verify': finished - built},
        'solver_operation_count': None, 'attack_S': None, 'ratio_to_rho': None,
        'classification': 'implementation validation; no measured speedup'
    }


def runPanel(results=None):
    root = Path(__file__).resolve().parents[2]
    contractPath = root / 'research/nagao_relations/experiments/nagao_relation_contract.json'
    contract = json.loads(contractPath.read_text())
    if results is None:
        results = []
    cases = []
    for panel in contract['sat_panel']:
        onb = field.Onb(panel['n'])
        curve = curves.Curve(onb)
        started = time.perf_counter()
        table, oracle = oracleTable(onb, curve, panel['weight'])
        targets = affinePoints(onb, curve)
        if panel.get('seed') is not None:
            targets = random.Random(panel['seed']).sample(targets, 24)
        oracle['diagnostic_setup_seconds'] = time.perf_counter() - started
        cases.append({'field_degree': panel['n'], 'weight': panel['weight'],
                      'target_count': len(targets), 'oracle': oracle})
        for target in targets:
            expected = table.get(target, set())
            for variant in contract['sat_variants']:
                try:
                    row = compareInstance(onb, curve, target, panel['weight'], variant, expected,
                                          contract['sat_watchdog']['seconds_per_instance'],
                                          contract['sat_watchdog']['maximum_projected_models'])
                except Exception:
                    row = {
                        'variant': variant, 'field_degree': onb.m, 'weight': panel['weight'],
                        'target': [onb.toCoords(value) for value in target],
                        'complete': False, 'correct': False,
                        'status': 'failed_infrastructure', 'traceback': traceback.format_exc(),
                        'expected_projected_solutions': len(expected)
                    }
                results.append(row)
        print('completed n=%d weight=%d targets=%d' % (panel['n'], panel['weight'], len(targets)), file=sys.stderr)
    code = Path(__file__).resolve().parent
    sources = ['nagaocompare.py', 'nagaodecomp.py', 'decomp.py', 'cnf.py', 'ir.py',
               'build.py', 'field.py', 'curves.py', 'indexcalc.py']
    return {
        'schema': 'nagao-projected-solutions-v1', 'command': [sys.executable] + sys.argv,
        'git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
        'git_status': subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True),
        'python': platform.python_version(), 'platform': platform.platform(),
        'pycryptosat': importlib.metadata.version('pycryptosat'),
        'contract_sha256': hashlib.sha256(contractPath.read_bytes()).hexdigest(),
        'source_sha256': {name: hashlib.sha256((code / name).read_bytes()).hexdigest() for name in sources},
        'cases': cases, 'results': results,
        'valid': all(row['correct'] for row in results),
        'limits': contract['metric_limits']
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('output already exists; choose a new immutable evidence path')
    rows = []
    try:
        output = runPanel(rows)
    except (Exception, KeyboardInterrupt):
        output = {'schema': 'nagao-projected-solutions-v1', 'valid': False,
                  'command': [sys.executable] + sys.argv,
                  'status': 'failed_infrastructure', 'traceback': traceback.format_exc(),
                  'results': rows}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x') as handle:
        json.dump(output, handle, indent=2)
        handle.write('\n')
    print(json.dumps({'valid': output['valid'], 'comparisons': len(output['results']), 'out': str(args.out)}))
    return 0 if output['valid'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
