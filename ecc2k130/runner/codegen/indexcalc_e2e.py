"""Bounded subgroup-correct IC experiment, including the degree-131 ONB.

Uses the existing Semaev-chain circuit. Field/curve counters are a vector of
logical calls, not calibrated machine operations. All elapsed phases are kept.
"""
import argparse
from contextlib import contextmanager
from collections import Counter
import hashlib
import json
import multiprocessing
import os
import sys
import random
import time

import cnf
import curves
import decomp
import field
import indexcalc


class Ledger:
    def __init__(self):
        self.counts = Counter()
        self.phases = {}
        self.active = False
        self.start = time.perf_counter_ns()

    @contextmanager
    def phase(self, name):
        assert not self.active, 'exclusive phase accounting only'
        self.active = True
        if os.environ.get('IC_E2E_PROGRESS') == '1':
            print('begin ' + name, file=sys.stderr, flush=True)
        before = self.counts.copy()
        start = time.perf_counter_ns()
        try:
            yield
        finally:
            entry = self.phases.setdefault(name, {'ns': 0, 'calls': Counter()})
            entry['ns'] += time.perf_counter_ns() - start
            entry['calls'].update(self.counts - before)
            self.active = False
            if os.environ.get('IC_E2E_PROGRESS') == '1':
                print('end ' + name, file=sys.stderr, flush=True)

    def report(self):
        total = time.perf_counter_ns() - self.start
        measured = sum(p['ns'] for p in self.phases.values())
        assert total >= measured
        return {'elapsed_ns': total, 'phases': self.phases,
                'orchestration_ns': total - measured, 'logical_calls': self.counts,
                'total_common_operations': None, 'S': None, 'rho_ratio': None,
                'note': 'nested logical call categories must not be summed; SAT internal operations are uncalibrated'}


class AuditField(field.Onb):
    def __init__(self, m, ledger):
        self.ledger = ledger
        super().__init__(m)

    def inv(self, value):
        # Extended Euclid in F2[z]/(1+z+...+z^(2m)). Nonzero symmetric
        # field elements are units in this ring, even when the ring splits.
        self.ledger.counts['field.inv'] += 1
        if not value:
            raise ZeroDivisionError()
        a, b, u, v = value, self.allOnes, 1, 0
        while a != 1:
            if not a:
                raise ValueError('nonunit in the ONB ring')
            shift = a.bit_length() - b.bit_length()
            if shift < 0:
                a, b, u, v = b, a, v, u
                shift = -shift
            a ^= b << shift
            u ^= v << shift
            self.ledger.counts['polynomial.xor'] += 2
        while u.bit_length() >= self.allOnes.bit_length():
            u ^= self.allOnes << (u.bit_length() - self.allOnes.bit_length())
            self.ledger.counts['polynomial.xor'] += 1
        return self.normalize(u)

    def trace(self, value):
        self.ledger.counts['field.trace'] += 1
        return self.toCoords(value).bit_count() & 1


def counted(name, original):
    def call(self, *args, **kwargs):
        self.ledger.counts[name] += 1
        return original(self, *args, **kwargs)
    return call


for method in ['mul', 'frob', 'add', 'fromCoords', 'toCoords']:
    setattr(AuditField, method, counted('field.' + method, getattr(field.Onb, method)))


class AuditCurve(curves.Curve):
    def __init__(self, onb, ledger):
        self.ledger = ledger
        super().__init__(onb)


for method in ['add', 'dbl', 'mul', 'neg', 'frob', 'pointFromX', 'onCurve']:
    setattr(AuditCurve, method, counted('group.' + method, getattr(curves.Curve, method)))


def canonicalSupport(support, m, perm):
    best = None
    current = support
    for _ in range(m):
        value = sum(1 << i for i in current)
        best = value if best is None else min(best, value)
        current = [perm[i] for i in current]
    return best


def subgroupBase(onb, curve, ell, eigen, weight):
    """One column per signed Frobenius orbit, checked in the prime subgroup.

    Every nonempty support orbit contains coordinate zero. Enumerating those
    supports avoids materializing all m rotated copies before subgroup checks.
    """
    if not 1 <= weight <= 4 or (onb.m == 131 and weight > 2):
        raise ValueError('materialized experiment restricts degree 131 to weight 2, and small fields to weight 4')
    perm = decomp.sigmaPerm(onb.m, onb.n, 1)
    candidates = set()
    for tail in indexcalc.combinationsUpTo(onb.m - 1, weight - 1):
        support = [0] + [i + 1 for i in tail]
        candidates.add(canonicalSupport(support, onb.m, perm))
    reps, lookup = [], {}
    for coordinate in sorted(candidates):
        # Every odd-order point is a double; x(2P)=lambda^2+lambda
        # has trace zero. This is necessary, not a subgroup certificate.
        if coordinate.bit_count() & 1:
            continue
        p = curve.pointFromX(onb.fromCoords(coordinate))
        if p is None or curve.mul(p, ell) is not None:
            continue
        column = len(reps)
        reps.append(p)
        q, coefficient = p, 1
        for _ in range(onb.m):
            for point, coeff in [(q, coefficient), (curve.neg(q), -coefficient % ell)]:
                if point in lookup:
                    assert lookup[point] == (column, coeff)
                lookup[point] = (column, coeff)
            q, coefficient = curve.frob(q), coefficient * eigen % ell
    assert reps, 'empty subgroup factor base'
    return reps, lookup


def setup(m, weight, points, ledger, artifactCache=None):
    with ledger.phase('setup'):
        onb = AuditField(m, ledger)
        curve = AuditCurve(onb, ledger)
        ell = curves.curveOrder(m) // 4
        assert curves.curveOrder(m) == 4 * ell and curves.isPrimeBig(ell)
        if m == 131:
            assert ell == 680564733841876926932320129493409985129
        generator = curve.randomPointOfOrder(ell, 4, random.Random(8701 + m))
        eigen = curves.frobeniusEigenvalue(curve, generator, ell)
        if artifactCache is None:
            reps, lookup = subgroupBase(onb, curve, ell, eigen, weight)
            prog, roots = decomp.buildSystem(m, onb.n, points, 12)
        else:
            reps, lookup = artifactCache.base(m, onb.n, ell, eigen, weight,
                lambda: subgroupBase(onb, curve, ell, eigen, weight))
            prog, roots = artifactCache.circuit(m, onb.n, points, 12,
                lambda: decomp.buildSystem(m, onb.n, points, 12))
    return onb, curve, ell, generator, eigen, reps, lookup, prog, roots


def proper(points, signs, curve):
    signed = [curve.neg(p) if sign < 0 else p for p, sign in zip(points, signs)]
    return all(signed[i] != curve.neg(signed[j]) for i in range(len(signed)) for j in range(i))


def strictLift(onb, curve, coordinates, target, lookup):
    actual = [curve.pointFromX(onb.fromCoords(x)) for x in coordinates]
    if any(p is None or p not in lookup for p in actual):
        return None
    for mask in range(1 << len(actual)):
        signs = [-1 if mask >> i & 1 else 1 for i in range(len(actual))]
        if not proper(actual, signs, curve):
            continue
        total = None
        for p, sign in zip(actual, signs):
            total = curve.add(total, curve.neg(p) if sign < 0 else p)
        if total == target:
            return actual, signs
    return None


def oracle(curve, lookup, target, points):
    """Independent exhaustive proper-sum oracle; small fields only."""
    values = sorted(lookup)
    def visit(start, chosen, total):
        if len(chosen) == points:
            return total == target
        for i in range(start, len(values)):
            p = values[i]
            if any(p == curve.neg(q) for q in chosen):
                continue
            if visit(i, chosen + [p], curve.add(total, p)):
                return True
        return False
    return visit(0, [], None)


def decomposeLocal(context, target, points, weight, variant, ledger, budget=.25):
    from pysat.solvers import CryptoMinisat
    onb, curve, ell, generator, eigen, reps, lookup, prog, roots = context
    if target is None:
        return None, {'status': 'identity_excluded'}
    with ledger.phase('encoding'):
        c = cnf.Cnf()
        pvars = decomp.encode(prog, roots, onb.m, points, weight, onb.toCoords(target[0]), c,
                             orderPoints=variant == 'candidate')
        if variant == 'candidate':
            for variables in pvars:
                c.addClause(variables)  # No x=0 point belongs to the odd subgroup.
                c.addXor(variables, False)  # Necessary trace-zero condition.
        ledger.counts['cnf.variables'] += c.nVars
        ledger.counts['cnf.clauses'] += len(c.clauses)
        ledger.counts['cnf.xors'] += len(c.xors)
    dispatchStats = None
    if os.environ.get('ONB_F2_BACKEND'):
        from onb_f2 import Dispatch
        with ledger.phase('xor_preprocess'):
            dispatch = Dispatch(os.environ['ONB_F2_BACKEND'], os.environ.get('ONB_F2_LIBRARY'))
            dispatch.preprocess(c)
            dispatchStats = dict(dispatch.stats)
    with ledger.phase('solver_load'):
        solver = CryptoMinisat()
        for clause in c.clauses:
            solver.add_clause(clause)
        for literals, rhs in c.xors:
            solver.add_xor_clause(literals, rhs)
    details = {'status': 'budget', 'models': 0, 'rejected_models': 0, 'solve_ns': 0,
               'vars': c.nVars, 'clauses': len(c.clauses), 'xors': len(c.xors),
               'sat_internal_operations': None, 'f2_dispatch': dispatchStats}
    try:
        for _ in range(16):
            remaining = budget - details['solve_ns'] / 1e9
            if remaining <= 0:
                break
            with ledger.phase('solve'):
                solver.conf_budget(2000)
                solver.time_budget(remaining)
                start = time.perf_counter_ns()
                ok = solver.solve_limited()
                details['solve_ns'] += time.perf_counter_ns() - start
                ledger.counts['sat.calls'] += 1
            if ok is None:
                break
            if not ok:
                details['status'] = 'unsat'
                return None, details
            with ledger.phase('extract_lift_verify'):
                model = {abs(lit): lit > 0 for lit in solver.get_model()}
                details['models'] += 1
                coordinates = [sum((1 << j) for j, lit in enumerate(v) if model.get(lit, False)) for v in pvars]
                assert all(value.bit_count() <= weight for value in coordinates)
                lifted = strictLift(onb, curve, coordinates, target, lookup)
                if lifted:
                    actual, signs = lifted
                    if all(p in lookup for p in actual) and proper(actual, signs, curve):
                        row = [0] * len(reps)
                        for p, sign in zip(actual, signs):
                            col, coeff = lookup[p]
                            row[col] = (row[col] + sign * coeff) % ell
                        # Check orbit-coefficient transport independently in the group.
                        total = None
                        for coeff, rep in zip(row, reps):
                            total = curve.add(total, curve.mul(rep, coeff))
                        assert total == target
                        details['status'] = 'verified'
                        details['row'] = row
                        details['x_coordinates'] = coordinates
                        return row, details
                details['rejected_models'] += 1
                ledger.counts['sat.blocked_models'] += 1
                solver.add_clause([-lit if model.get(lit, False) else lit for v in pvars for lit in v])
        return None, details
    finally:
        with ledger.phase('solver_teardown'):
            solver.delete()


def solverChild(pipe, context, target, points, weight, variant, budget):
    meter = Ledger()
    context[0].ledger = meter
    context[1].ledger = meter
    try:
        row, details = decomposeLocal(context, target, points, weight, variant, meter, budget)
        pipe.send(('result', row, details, meter.phases, meter.counts))
    except BaseException as error:
        pipe.send(('error', type(error).__name__, str(error)))
    finally:
        pipe.close()


def decompose(context, target, points, weight, variant, ledger, budget=.25):
    # CryptoMiniSat preprocessing can overrun its native limit. A separate
    # process bounds the entire query, including encoding and model lifting.
    processContext = multiprocessing.get_context('fork')
    receive, send = processContext.Pipe(duplex=False)
    process = processContext.Process(target=solverChild,
        args=(send, context, target, points, weight, variant, budget))
    start = time.perf_counter_ns()
    process.start()
    send.close()
    message = None
    try:
        if receive.poll(1.0):
            try:
                message = receive.recv()
            except EOFError:
                pass
    finally:
        if process.is_alive():
            process.terminate()
        process.join(timeout=.2)
        if process.is_alive():
            process.kill()
            process.join()
        receive.close()
    elapsed = time.perf_counter_ns() - start
    if message is None:
        phase = ledger.phases.setdefault('query_external_timeout', {'ns': 0, 'calls': Counter()})
        phase['ns'] += elapsed
        ledger.counts['query.external_timeouts'] += 1
        phase['calls']['query.external_timeouts'] += 1
        return None, {'status': 'external_timeout', 'query_ns': elapsed,
                      'inner_phase_counters_available': False, 'sat_internal_operations': None}
    if message[0] == 'error':
        raise RuntimeError('solver child: ' + message[1] + ': ' + message[2])
    _, row, details, phases, counts = message
    measured = sum(phase['ns'] for phase in phases.values())
    assert elapsed >= measured
    for name, value in phases.items():
        phase = ledger.phases.setdefault(name, {'ns': 0, 'calls': Counter()})
        phase['ns'] += value['ns']
        phase['calls'].update(value['calls'])
    ledger.counts.update(counts)
    phase = ledger.phases.setdefault('query_process_overhead', {'ns': 0, 'calls': Counter()})
    phase['ns'] += elapsed - measured
    details['query_ns'] = elapsed
    details['inner_phase_counters_available'] = True
    return row, details


class RelationMatrix:
    def __init__(self, size, prime, ledger):
        self.size, self.prime, self.ledger = size, prime, ledger
        self.rows = {}

    def push(self, coefficients, rhs):
        row = [x % self.prime for x in coefficients] + [rhs % self.prime]
        for pivot in sorted(self.rows):
            coefficient = row[pivot]
            if coefficient:
                row = [(x - coefficient * y) % self.prime for x, y in zip(row, self.rows[pivot])]
                self.ledger.counts['matrix.modular_multiply_subtract'] += len(row)
        pivot = next((i for i, x in enumerate(row[:-1]) if x), None)
        if pivot is None:
            assert row[-1] == 0, 'inconsistent relation'
            return False
        inverse = pow(row[pivot], -1, self.prime)
        self.ledger.counts['matrix.modular_inverse'] += 1
        row = [x * inverse % self.prime for x in row]
        self.ledger.counts['matrix.modular_multiply'] += len(row)
        for i, old in list(self.rows.items()):
            coefficient = old[pivot]
            if coefficient:
                self.rows[i] = [(x - coefficient * y) % self.prime for x, y in zip(old, row)]
                self.ledger.counts['matrix.modular_multiply_subtract'] += len(row)
        self.rows[pivot] = row
        return True

    def solution(self):
        return [self.rows[i][-1] for i in range(self.size)] if len(self.rows) == self.size else None


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def experiment(m, variant, seed, workload, trials=20, weight=2, points=3, artifactCache=None):
    ledger = Ledger()
    context = setup(m, weight, points, ledger, artifactCache)
    onb, curve, ell, generator, eigen, reps, lookup, prog, roots = context
    rng = random.Random(seed)
    records = []
    matrix = RelationMatrix(len(reps), ell, ledger)
    report = {'degree': m, 'variant': variant, 'seed': seed, 'workload': workload, 'points': points,
              'weight': weight, 'subgroup_order': str(ell), 'signed_base_size': len(lookup),
              'orbit_columns': len(reps), 'frobenius_eigenvalue': str(eigen),
              'input_hash': digest([m, seed, workload, points, weight, generator, reps]),
              'records': records, 'status': 'complete', 'scalar_recovered': None}
    count = trials if workload == 'stage' else 256
    for i in range(count):
        with ledger.phase('target_generation'):
            scalar = rng.randrange(1, ell)
            target = curve.mul(generator, scalar)
        row, detail = decompose(context, target, points, weight, variant, ledger)
        detail.update(index=i, target_hash=digest(target))
        if m <= 9:
            with ledger.phase('independent_oracle'):
                exists = oracle(curve, lookup, target, points)
                assert row is None or exists
                assert detail['status'] != 'unsat' or not exists
                detail['oracle_exists'] = exists
        records.append(detail)
        if workload == 'dlp':
            if row is not None:
                with ledger.phase('relation_filter_and_matrix'):
                    detail['independent'] = matrix.push(row, scalar)
            if matrix.solution() is not None:
                break
    if workload == 'stage':
        # Planted controls have their own records and are excluded from random yield.
        controls = []
        values = sorted(lookup)
        for i in range(3):
            with ledger.phase('planted_control_generation'):
                while True:
                    chosen = [values[rng.randrange(len(values))] for _ in range(points)]
                    if not proper(chosen, [1] * points, curve):
                        continue
                    target = None
                    for p in chosen:
                        target = curve.add(target, p)
                    if target is not None:
                        break
            row, detail = decompose(context, target, points, weight, variant, ledger)
            assert detail['status'] != 'unsat', 'planted proper relation rejected'
            detail['target_hash'] = digest(target)
            controls.append(detail)
        report['planted_controls'] = controls
    else:
        assert m <= 9, 'no claim of full degree-131 recovery'
        logs = matrix.solution()
        report['matrix_rank'] = len(matrix.rows)
        if logs is None:
            report['status'] = 'insufficient_relations'
        else:
            with ledger.phase('factor_log_certificates'):
                for log, point in zip(logs, reps):
                    assert curve.mul(generator, log) == point
            with ledger.phase('target_generation'):
                expected = random.Random(seed ^ 0xEC131).randrange(1, ell)
                target = curve.mul(generator, expected)
            descents = []
            descentRng = random.Random(seed ^ 0xDE5C)
            for i in range(128):
                with ledger.phase('descent_target_generation'):
                    shift = descentRng.randrange(1, ell)
                    residual = curve.add(target, curve.mul(generator, shift))
                row, detail = decompose(context, residual, points, weight, variant, ledger)
                descents.append(detail)
                if row is not None:
                    with ledger.phase('scalar_recovery_and_certificate'):
                        recovered = (sum(c * log for c, log in zip(row, logs)) - shift) % ell
                        ledger.counts['scalar.modular_products'] += len(logs)
                        assert recovered == expected and curve.mul(generator, recovered) == target
                    report['scalar_recovered'] = str(recovered)
                    report['certificate'] = {'generator': generator, 'target': target, 'expected_scalar': str(expected), 'factor_base_logs': logs, 'factor_base_representatives': reps, 'verified': True}
                    break
            report['descents'] = descents
            if report['scalar_recovered'] is None:
                report['status'] = 'descent_budget'
    if artifactCache is not None:
        report['cache'] = dict(artifactCache.stats)
    report['accounting'] = ledger.report()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--m', type=int, choices=[5, 9, 131], required=True)
    parser.add_argument('--variant', choices=['reference', 'candidate'], required=True)
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--workload', choices=['stage', 'dlp'], default='stage')
    parser.add_argument('--trials', type=int, default=20)
    args = parser.parse_args()
    if args.workload == 'dlp' and args.m == 131:
        parser.error('degree-131 full recovery is not implemented by this bounded experiment')
    print(json.dumps(experiment(args.m, args.variant, args.seed, args.workload, args.trials, weight=4 if args.m == 5 else 2)))


if __name__ == '__main__':
    main()
