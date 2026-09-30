"""Combined constructor/Metal correctness; complete proofs and explicit fallbacks."""
import argparse
from contextlib import ExitStack
import base64
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import normalized as candidate
from normalized_query import NormalizedQuery

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'round40'
sys.path.insert(0, str(HERE.parent / 'round37'))
import test_fixed_width as independent
from public_replay import Point
from transport_controls import validate_transport_tables


def read(path):
    return json.loads(gzip.decompress(path.read_bytes()) if path.name.endswith('.gz') else path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def integer(record):
    return {k: v for k, v in record.items() if type(v) in (int, bool)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--metal', action='store_true')
    args = parser.parse_args()
    output = args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(output)
    receipt_path = HERE / 'build/receipt.json'
    receipt = read(receipt_path)
    def check_sources():
        for path, digest in receipt['sources'].items():
            assert sha(HERE.parent / path) == digest
        for kind in ('binaries', 'generated'):
            for path, digest in receipt[kind].items():
                assert sha(HERE / 'build' / path) == digest
    check_sources()
    corpus_path = HERE / 'fixtures/controls.json.gz'
    corpus_manifest = read(HERE / 'fixtures/manifest.json')
    assert sha(corpus_path) == corpus_manifest['sha256']
    cases = read(corpus_path)
    assert len(cases) == corpus_manifest['controls'] == 6001
    truths = {name: independent.truth(x + y, terms) for name, x, y, e, terms, mod, kind in cases}
    modes = [('cpu', False), ('cpu', True)]
    metal = {'requested': args.metal, 'status': 'NOT_REQUESTED', 'device': None}
    if args.metal:
        try:
            with candidate.Producer(2, 9, 31, backend='metal') as probe:
                metal.update(status='AVAILABLE', device=probe.device)
        except ValueError as error:
            if str(error) != 'requested Metal device unavailable':
                raise
            metal.update(status='UNAVAILABLE', detail=str(error))
        else:
            modes.append(('metal', False))
    report = {'schema': 'normalized-wide-metal-validation/1', 'status': 'RUNNING',
              'validator_sha256': sha(Path(__file__)), 'build_receipt_sha256': sha(receipt_path),
              'corpus_sha256': sha(corpus_path), 'metal': metal, 'transport_controls': validate_transport_tables(),
              'controls': [], 'budgets': [], 'queries': [], 'proofs': {}, 'devices': [],
              'timing_eligible': False, 'candidate_id': None, 'online_speedup': None}
    for backend, sanitizer in modes:
        with ExitStack() as stack:
            contexts = {}
            for index, (name, x, y, e, terms, modulus, kind) in enumerate(cases):
                shape = x, y, e, modulus
                if shape not in contexts:
                    p = stack.enter_context(candidate.Producer(x, y, e, backend=backend, sanitizer=sanitizer))
                    if modulus is not None:
                        p.configure_normalization(modulus)
                    c = stack.enter_context(candidate.Checker(x, y, e, sanitizer=sanitizer))
                    contexts[shape] = p, c
                    report['devices'].append({'backend': backend, 'sanitizer': sanitizer, 'shape': shape, 'device': p.device})
                p, c = contexts[shape]
                row = {'case': name, 'backend': backend, 'sanitizer': sanitizer, 'kind': kind,
                       'shape': [x, y, e], 'truth_roots': len(truths[name])}
                try:
                    answer = p.produce(candidate.Packed(x + y, e, terms), checker=c)
                except candidate.Inconclusive as error:
                    assert len(truths[name]) > 256 and 'complete roots exceed 256' in str(error), (name, str(error))
                    row.update(status='expected-inconclusive', detail=str(error))
                else:
                    assert answer['roots'] == truths[name] and answer['certificate']['verified'], (name, backend)
                    assert independent.verify_basis(x + y, terms, truths[name], answer['basis'], len(truths[name]))
                    assert independent.check_identities(x, y, e, terms, answer['proof_bytes']) == answer['certificate']['stats']['contradictions']
                    norm, projection, m, d = (answer[k] for k in ('normalization_stats', 'projection_stats', 'multiplier_stats', 'deferred_stats'))
                    assert norm['attempts'] == norm['prepared'] + norm['mismatches'] + norm['nonunits'] + norm['budget_skips']
                    assert norm['transpose_parities'] == 0 and norm['work'] <= projection['work']
                    assert projection['work'] + m['rows'] + m['row_xors'] + d['reconstruction_pivots'] <= 67108864
                    if kind == 'zero-scalar':
                        assert norm['zero_scalars'] > 0
                    if kind == 'nonunit':
                        assert norm['nonunits'] > 0
                    expected_gpu = backend == 'metal' and e <= 32
                    assert bool(answer['stats']['gpu_used']) == expected_gpu
                    row.update(status='verified', proof_sha256=answer['proof_sha256'], gpu_used=expected_gpu,
                               normalization=integer(norm), projection=integer(projection),
                               multiplier=integer(m), deferred=integer(d), metrics=integer(answer['stats']))
                report['controls'].append(row)
                if (index + 1) % 1000 == 0:
                    print('CONTROLS_PASS', backend, sanitizer, index + 1, flush=True)
    for mode in ('budget_test', 'multiplier_budget_test'):
        for name, terms in [('empty', []), ('affine-unsat', [(2, 1), (4, 2), (6, 4), (0, 4)])]:
            with candidate.Producer(1, 3, 7, **{mode: True}) as p, candidate.Checker(1, 3, 7) as c:
                assert p.configure_normalization(131)
                try:
                    answer = p.produce(candidate.Packed(4, 7, terms), checker=c)
                    assert answer['roots'] == independent.truth(4, terms) and answer['certificate']['verified']
                    stats = {k: answer[k] for k in ('normalization_stats', 'projection_stats', 'multiplier_stats', 'deferred_stats')}
                    status = 'verified'
                except candidate.Inconclusive as error:
                    stats = {k: getattr(error, k) for k in ('normalization_stats', 'projection_stats', 'multiplier_stats', 'deferred_stats')}
                    status = 'inconclusive'
                norm, proj, mul, defer = (stats[k] for k in ('normalization_stats', 'projection_stats', 'multiplier_stats', 'deferred_stats'))
                assert norm['work'] <= proj['work']
                assert proj['work'] + mul['rows'] + mul['row_xors'] + defer['reconstruction_pivots'] <= 8
                report['budgets'].append({'mode': mode, 'case': name, 'status': status, **stats})
    inputs_path = BASE / 'fixtures/inputs.json.gz'
    inputs = read(inputs_path)
    for backend, sanitizer in modes:
        with ExitStack() as stack:
            workspaces = {}
            for item in inputs:
                shape = tuple(item[k] for k in ('n', 'mod', 'b', 'm', 'ell'))
                if shape not in workspaces:
                    workspaces[shape] = stack.enter_context(NormalizedQuery(*shape, backend=backend, sanitizer=sanitizer))
                answer = workspaces[shape].solve(Point(**item['target']))
                assert answer['status'] == 'solved' and answer['verified']
                proof = answer.pop('proof_bytes')
                assert hashlib.sha256(proof).hexdigest() == answer['proof_sha256']
                expected_gpu = backend == 'metal' and item['n'] <= 32
                assert bool(answer['metrics']['gpu_used']) == expected_gpu
                if item['nvars'] >= 21:
                    assert answer['normalization_stats']['prepared'] > 0
                    assert answer['normalization_stats']['mismatches'] == 0
                report['proofs'].setdefault(answer['proof_sha256'], base64.b64encode(proof).decode())
                report['queries'].append({'name': item['name'], 'workload_sha256': item['workload_sha256'],
                                          'backend': backend, 'sanitizer': sanitizer, 'result': answer})
                print('QUERY_PASS', item['name'], backend, sanitizer, 'GPU', expected_gpu, flush=True)
    assert len(report['queries']) == 18 * len(modes) and len(report['controls']) == 6001 * len(modes)
    check_sources()
    report.update(status='PASS', fixture_sha256=sha(inputs_path))
    output.write_bytes(gzip.compress(json.dumps(report, separators=(',', ':')).encode(), mtime=0))
    print('COMBINED_VALIDATION_PASS', len(report['controls']), 'systems;', len(report['queries']), 'queries', flush=True)


if __name__ == '__main__':
    main()
