"""Compare reserved or direct row accounting with the frozen prior checker."""
import argparse
import base64
from contextlib import ExitStack
import gzip
import hashlib
import json
from pathlib import Path
import sys

from adapter import HERE, ProjectionQuery, load, producer
from bindings import bindings
from reservation_accounting import reservation_accounting

prior = load('reserve54_validation_prior53', HERE.parent/'round53/adapter.py')
accounting = load('prepare53_accounting52', HERE.parent/'round52/locality_accounting.py')
sys.path.insert(0, str(HERE.parent/'round37'))
import test_fixed_width as independent
from public_replay import Point


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_bytes())


def integer(row):
    return {k: v for k, v in row.items() if type(v) in (int, bool)}


def compare(actual, expected, reserved):
    for field in ('status', 'complete', 'basis_terms', 'basis_sha256', 'proof_sha256',
                  'assignment', 'verified', 'gpu_projection_stats'):
        assert actual.get(field) == expected.get(field), field
    for field in ('metrics', 'partial_stats', 'projection_stats', 'normalization_stats',
                  'multiplier_stats', 'deferred_stats', 'symmetry_stats'):
        assert integer(actual[field]) == integer(expected[field]), field
    if 'basis_certificate' in actual:
        accounting.compare_certificates(actual['basis_certificate'], expected['basis_certificate'])
        assert integer(actual['basis_certificate']['partial_locality_stats']) == integer(expected['basis_certificate']['partial_locality_stats'])
        reservation_accounting(actual['basis_certificate'], reserved)
    assert actual['preparation_schedule']['drained']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--metal', action='store_true')
    parser.add_argument('--partial-reservation', choices=('direct', 'reserved'), default='reserved')
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frozen = bindings()
    corpus = HERE.parent/'round42/fixtures/controls.json.gz'
    manifest = read(corpus.with_name('manifest.json'))
    assert sha(corpus) == manifest['sha256']
    cases = read(corpus)
    assert len(cases) == manifest['controls'] == 6001
    truths = {name: independent.truth(x+y, terms) for name, x, y, e, terms, mod, kind in cases}
    modes = [('cpu', False), ('cpu', True)]
    metal = {'requested': args.metal, 'status': 'NOT_REQUESTED'}
    if args.metal:
        try:
            with producer.Producer(2, 3, 3, backend='metal') as probe:
                metal.update(status='AVAILABLE', device=probe.device)
        except ValueError as error:
            if str(error) != 'requested Metal device unavailable':
                raise
            metal.update(status='UNAVAILABLE', detail=str(error))
        else:
            modes.append(('metal', False))
    report = {'schema': 'partial-work-reservation-validation/1', 'status': 'RUNNING', 'partial_reservation': args.partial_reservation,
              'executed_bindings': frozen, 'metal': metal, 'controls': [], 'queries': [], 'proofs': {},
              'validator_sha256': sha(Path(__file__)), 'corpus_sha256': sha(corpus),
              'timing_eligible': False, 'candidate_id': None, 'online_speedup': None}
    journal_path = args.output.with_suffix(args.output.suffix+'.jsonl.gz')
    with gzip.open(journal_path, 'xt', compresslevel=1) as journal:
        def retain(kind, row):
            report[kind].append(row)
            journal.write(json.dumps({'kind': kind, **row}, separators=(',', ':'))+'\n')
            journal.flush()

        for backend, sanitizer in modes:
            with ExitStack() as stack:
                contexts = {}
                for index, (name, x, y, e, terms, modulus, kind) in enumerate(cases):
                    key = x, y, e, modulus
                    if key not in contexts:
                        new = stack.enter_context(producer.Basis(x, y, e, backend=backend, sanitizer=sanitizer))
                        old = stack.enter_context(prior.producer.Basis(x, y, e, backend=backend, sanitizer=sanitizer))
                        new.configure_preparation('overlap')
                        new.checker.configure_partial_reservation(args.partial_reservation)
                        if modulus is not None:
                            new.producer.configure_normalization(modulus)
                            old.producer.configure_normalization(modulus)
                        contexts[key] = new, old
                    new, old = contexts[key]
                    anf = producer.Packed(x+y, e, terms)
                    for partial, projection in ((False, False), (False, True), (True, False), (True, True)):
                        for basis in (new, old):
                            basis.producer.configure_partial(partial)
                            basis.producer.configure_gpu_projection(projection)
                        actual, expected = new.compute(anf), old.compute(anf)
                        compare(actual, expected, args.partial_reservation == 'reserved')
                        row = {'case': name, 'backend': backend, 'sanitizer': sanitizer, 'shape': [x, y, e],
                               'partial_enabled': partial, 'gpu_projection_enabled': projection, 'kind': kind,
                               'status': actual['status'], 'schedule': actual['preparation_schedule']}
                        if actual['status'] == 'inconclusive':
                            assert len(truths[name]) > 256 and 'complete roots exceed 256' in actual['detail']
                            assert not actual['preparation_schedule']['certification_reached']
                        else:
                            assert actual['complete'] and actual['status'] == 'gb'
                            cert = actual['basis_certificate']
                            assert cert['solutions'] == truths[name]
                            assert independent.verify_basis(x+y, terms, truths[name], actual['basis_terms'], len(truths[name]))
                            assert cert['preparation_stats']['used'] == 1
                            row.update(proof_sha256=actual['proof_sha256'], certificate=cert)
                        retain('controls', row)
                    if (index+1) % 1000 == 0:
                        print('CONTROLS_PASS', backend, sanitizer, index+1, flush=True)

        fixture = HERE.parent/'round40/fixtures/inputs.json.gz'
        inputs = read(fixture)
        for backend, sanitizer in modes:
            with ExitStack() as stack:
                contexts = {}
                for item in inputs:
                    shape = tuple(item[k] for k in ('n', 'mod', 'b', 'm', 'ell'))
                    if shape not in contexts:
                        opts = {'backend': backend, 'sanitizer': sanitizer, 'identity': 'factored_local'}
                        new = stack.enter_context(ProjectionQuery(*shape, partial_reservation=args.partial_reservation, **opts))
                        old = stack.enter_context(prior.ProjectionQuery(*shape, **opts))
                        contexts[shape] = new, old
                    new, old = contexts[shape]
                    for symmetry in (False, True):
                        for query in (new, old):
                            query.checker.configure_symmetry(symmetry)
                        for transform in ('full', 'tile16'):
                            for query in (new, old):
                                query.checker.configure_transform(transform)
                            expected = old.solve(Point(**item['target']))
                            assert expected['status'] == 'solved' and expected['verified']
                            for preparation in ('serial', 'prepared', 'overlap'):
                                new.basis.configure_preparation(preparation)
                                actual = new.solve(Point(**item['target']))
                                compare(actual, expected, args.partial_reservation == 'reserved')
                                assert actual['status'] == 'solved' and actual['verified']
                                assert sum(actual['phases_ns'].values()) == actual['complete_query_ns']
                                stats = actual['basis_certificate']['preparation_stats']
                                assert stats['used'] == int(preparation != 'serial')
                                assert stats['recomputed'] == 0
                                raw = actual.pop('proof_bytes')
                                assert hashlib.sha256(raw).hexdigest() == actual['proof_sha256']
                                report['proofs'].setdefault(actual['proof_sha256'], base64.b64encode(raw).decode())
                                retain('queries', {'name': item['name'], 'workload_sha256': item['workload_sha256'],
                                                   'backend': backend, 'sanitizer': sanitizer, 'symmetry': symmetry,
                                                   'transform': transform, 'preparation': preparation, 'result': actual})
                            print('QUERIES_PASS', item['name'], backend, sanitizer, symmetry, transform, flush=True)
    assert len(report['controls']) == 24004*len(modes)
    assert len(report['queries']) == 216*len(modes)
    for path, digest in frozen.items():
        assert sha(Path(path)) == digest, path
    report.update(status='PASS', fixture_sha256=sha(fixture))
    args.output.write_bytes(gzip.compress(json.dumps(report, separators=(',', ':')).encode(), mtime=0))
    print('RESERVATION_VALIDATION_PASS', len(report['controls']), 'controls;', len(report['queries']), 'queries', flush=True)


if __name__ == '__main__':
    main()
