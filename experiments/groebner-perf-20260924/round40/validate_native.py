"""Independent native projection correctness, complete queries and budget controls."""
from collections import Counter
from contextlib import ExitStack
import base64
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'round37'
sys.path.insert(0, str(BASE))
import fixed_width as baseline
import test_fixed_width as independent
import projection as candidate


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def controls():
    from controls import controls as retained_controls
    yield from retained_controls()
    for value in range(4096):
        items = [(m << 1, 1 << e) for e in range(3) for m in range(4) if value >> (4 * e + m) & 1]
        yield f'exhaustive-y2-e3-{value}', 1, 2, 3, items
    # Degree-one Macaulay incompleteness is an explicit original-equation fallback.
    rows = [[0, 2, 3, 5, 10], [0, 2, 3, 4, 5, 6, 8, 9, 10], [0, 4, 6, 12]]
    yield 'degree-one-incomplete', 1, 4, 3, [(m << 1, 1 << i) for i, row in enumerate(rows) for m in row]


def integer(value):
    return {k: v for k, v in value.items() if type(v) in (int, bool)}


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    destination = parser.parse_args().output
    if destination.exists():
        raise FileExistsError(destination)
    receipt = json.loads((HERE / 'build/receipt.json').read_text())
    assert sha(HERE / 'producer.cpp') == receipt['source_sha256']
    for name, expected in receipt['dependency_sources'].items():
        assert sha(Path(name)) == expected
    for name, expected in receipt['binaries'].items():
        assert sha(HERE / name) == expected
    cases = list(controls())
    assert len(cases) == 4547
    report = {'schema': 'quadratic-projection-native-validation/1', 'status': 'PASS',
              'scope': 'Native optimized and UBSan correctness on the recorded host; no timing claim.',
              'validator_sha256': sha(Path(__file__)), 'api_sha256': sha(HERE / 'projection.py'),
              'build_receipt_sha256': sha(HERE / 'build/receipt.json'),
              'synthetic': [], 'budgets': [], 'queries': [], 'proofs': {},
              'timing_eligible': False, 'candidate_id': None, 'online_speedup': None}
    optimized = {}
    for sanitizer in (False, True):
        totals = Counter()
        with ExitStack() as stack:
            contexts = {}
            for label, x, y, e, items in cases:
                if (x, y, e) not in contexts:
                    contexts[x, y, e] = (stack.enter_context(candidate.Producer(x, y, e, sanitizer=sanitizer)),
                                         stack.enter_context(candidate.Checker(x, y, e, sanitizer=sanitizer)))
                producer, checker = contexts[x, y, e]
                answer = producer.produce(candidate.Packed(x + y, e, items), checker=checker)
                roots = independent.truth(x + y, items)
                assert answer['roots'] == roots and answer['certificate']['verified'], label
                assert independent.verify_basis(x + y, items, roots, answer['basis'], len(roots)), label
                assert independent.check_identities(x, y, e, items, answer['proof_bytes']) == answer['certificate']['stats']['contradictions']
                p, m, d = answer['projection_stats'], answer['multiplier_stats'], answer['deferred_stats']
                assert m['attempts'] == m['certified_branches'] + m['failed_branches']
                assert p['certified_branches'] <= m['certified_branches']
                assert p['attempts'] == p['certified_branches'] + p['rank_fallbacks'] + p['satisfying_fallbacks'] + p['budget_skips']
                assert m['rows'] + m['row_xors'] + d['reconstruction_pivots'] + p['work'] <= 67108864
                if label == 'degree-one-incomplete':
                    assert m['certified_branches'] == 0 and answer['stats']['fallback_assignments'] == 32
                row = {'case': label, 'sanitizer': sanitizer, 'proof_sha256': answer['proof_sha256'],
                       'projection': integer(p), 'multiplier': integer(m), 'deferred': integer(d)}
                if sanitizer:
                    assert {k: v for k, v in row.items() if k != 'sanitizer'} == optimized[label]
                else:
                    optimized[label] = {k: v for k, v in row.items() if k != 'sanitizer'}
                report['synthetic'].append(row)
                totals.update({k: p[k] for k in ('attempts', 'certified_branches', 'rank_fallbacks', 'budget_skips')})
        print('SYNTHETIC PASS', len(cases), sanitizer, dict(totals), flush=True)
    for mode in ('budget_test', 'multiplier_budget_test'):
        for label, items in [('empty', []), ('affine-unsat', [(16, 1), (32, 2), (48, 4), (0, 4)])]:
            with candidate.Producer(4, 2, 3, **{mode: True}) as producer, candidate.Checker(4, 2, 3) as checker:
                try:
                    answer = producer.produce(candidate.Packed(6, 3, items), checker=checker)
                    assert answer['certificate']['verified']
                    assert answer['roots'] == independent.truth(6, items)
                    value = {'status': 'solved', 'projection': answer['projection_stats'],
                             'multiplier': answer['multiplier_stats'], 'deferred': answer['deferred_stats']}
                except candidate.Inconclusive as error:
                    value = {'status': 'inconclusive', 'detail': str(error), 'projection': error.projection_stats,
                             'multiplier': error.multiplier_stats, 'deferred': error.deferred_stats}
                p, m, d = value['projection'], value['multiplier'], value['deferred']
                assert p['work'] + m['rows'] + m['row_xors'] + d['reconstruction_pivots'] <= 8
                report['budgets'].append({'case': label, 'mode': mode, **value})
    assert any(r['status'] == 'inconclusive' for r in report['budgets'])
    print('BUDGETS PASS', flush=True)

    inputs = json.loads(gzip.decompress((HERE / 'fixtures/inputs.json.gz').read_bytes()))
    qbaseline = load('projection_query_control', BASE / 'fixed_width_query.py')
    qcandidate = load('projection_query_candidate', HERE / 'projection_query.py')
    qcandidate.Basis = candidate.Basis
    from public_replay import Point
    query_expectations, query_proofs = {}, {}
    for label, module, sanitizer in [('baseline', qbaseline, False), ('projection', qcandidate, False), ('projection', qcandidate, True)]:
        with ExitStack() as stack:
            contexts = {}
            for item in inputs:
                shape = tuple(item[k] for k in ('n', 'mod', 'b', 'm', 'ell'))
                if shape not in contexts:
                    contexts[shape] = stack.enter_context((module.FixedWidthQuery if label == 'baseline' else module.ProjectionQuery)(*shape, sanitizer=sanitizer))
                query = contexts[shape]
                answer = query.solve(Point(**item['target']))
                assert answer['status'] == 'solved' and answer['verified'], (item['name'], label, answer)
                proof = answer.pop('proof_bytes')
                assert hashlib.sha256(proof).hexdigest() == answer['proof_sha256']
                report['proofs'].setdefault(answer['proof_sha256'], base64.b64encode(proof).decode())
                keys = ('basis_terms', 'basis_sha256', 'assignment', 'curve_witness', 'public_target')
                mathematical = {k: answer[k] for k in keys}
                if label == 'baseline':
                    query_expectations[item['name']] = mathematical
                else:
                    assert mathematical == query_expectations[item['name']], item['name']
                    if not sanitizer:
                        query_proofs[item['name']] = (proof, integer(answer['projection_stats']))
                    else:
                        assert (proof, integer(answer['projection_stats'])) == query_proofs[item['name']]
                report['queries'].append({'name': item['name'], 'workload_sha256': item['workload_sha256'],
                                          'variant': label, 'sanitizer': sanitizer, 'result': answer})
                print('QUERY PASS', item['name'], label, sanitizer, flush=True)
    assert len(report['queries']) == 54
    for name, expected in receipt['dependency_sources'].items():
        assert sha(Path(name)) == expected
    destination.write_bytes(gzip.compress(json.dumps(report, separators=(',', ':')).encode(), mtime=0))
    print('PASS', len(report['synthetic']), 'native systems;', len(report['queries']), 'complete queries', flush=True)


if __name__ == '__main__':
    main()
