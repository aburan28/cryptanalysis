"""Fresh complete-query controls for independent CPU/Metal transforms; no speed claim."""
import argparse
import base64
from contextlib import ExitStack
import gzip
import hashlib
import json
import os
from pathlib import Path
import time

from adapter import HERE, ProjectionQuery, base, producer
from bindings import bindings
from public_replay import Point


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare(actual, expected):
    for field in ('status', 'complete', 'basis_terms', 'basis_sha256', 'proof_sha256',
                  'assignment', 'verified', 'gpu_projection_stats'):
        assert actual.get(field) == expected.get(field), field
    for field in ('metrics', 'partial_stats', 'projection_stats', 'normalization_stats',
                  'multiplier_stats', 'deferred_stats', 'symmetry_stats'):
        integers = lambda d: {k: v for k, v in d.items() if type(v) in (int, bool)}
        assert integers(actual[field]) == integers(expected[field]), field
    assert actual['basis_certificate']['solutions'] == expected['basis_certificate']['solutions']
    for field in ('stats', 'partial_stats', 'identity_check_stats', 'symmetry_check_stats',
                  'partial_locality_stats', 'partial_reservation_stats'):
        integers = lambda d: {k: v for k, v in d.items() if type(v) in (int, bool)}
        assert integers(actual['basis_certificate'][field]) == integers(expected['basis_certificate'][field]), field
    assert actual['preparation_schedule']['drained']
    assert sum(actual['phases_ns'].values()) == actual['complete_query_ns']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--metal', action='store_true')
    args = parser.parse_args()
    if args.output.exists(): raise FileExistsError(args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fixture = HERE.parent/'round40/fixtures/inputs.json.gz'
    frozen = bindings()
    assert str(HERE/'build/native-receipt.json') in frozen
    assert frozen[str(Path(__file__).resolve())] == sha(Path(__file__))
    frozen[str(fixture)] = sha(fixture)
    inputs = json.loads(gzip.decompress(fixture.read_bytes()))
    # Same producer in each pair. Device substitution applies only to the
    # independently reconstructed coefficient transform, never to cached answers.
    modes = [('cpu', 'cpu', False), ('cpu', 'cpu', True)]
    availability = {'requested': args.metal, 'status': 'NOT_REQUESTED'}
    if args.metal:
        try:
            from adapter import Checker
            with Checker(2, 3, 3, transform_backend='metal') as c:
                availability.update(status='AVAILABLE', device=c.transform_device)
        except RuntimeError as error:
            if str(error) != 'requested independent Metal transform unavailable': raise
            availability.update(status='UNAVAILABLE', detail=str(error))
        else:
            modes += [('cpu', 'metal', False), ('metal', 'metal', False),
                  ('cpu', 'metal_simd', False), ('metal', 'metal_simd', False)]
    report = {'schema': 'constant-identity-query-validation/1', 'status': 'RUNNING',
              'metal': availability, 'executed_bindings': frozen, 'fixture_sha256': sha(fixture),
              'validator_sha256': sha(Path(__file__)), 'queries': [], 'proofs': {}, 'constant_modes': ['original', 'prepared', 'folded'],
              'timing_eligible': False, 'host_isolation_receipt': None,
              'candidate_id': None, 'online_speedup': None}
    with gzip.open(args.output.with_suffix('.jsonl.gz'), 'xt', compresslevel=1) as journal:
        for backend, transform_backend, sanitizer, constant_mode in [(*mode, identity) for mode in modes for identity in ('original', 'prepared', 'folded')]:
            with ExitStack() as stack:
                contexts = {}
                for item in inputs:
                    shape = tuple(item[k] for k in ('n', 'mod', 'b', 'm', 'ell'))
                    if shape not in contexts:
                        config = dict(backend=backend, sanitizer=sanitizer, identity='factored_local', transform='full')
                        actual = stack.enter_context(ProjectionQuery(*shape, transform_backend=transform_backend, constant_identity=constant_mode, **config))
                        expected = stack.enter_context(base.ProjectionQuery(*shape, **config))
                        contexts[shape] = actual, expected
                    new, old = contexts[shape]
                    target = Point(**item['target'])
                    expected = old.solve(target)
                    assert expected['verified'] and expected['status'] == 'solved'
                    for preparation in ('serial', 'prepared', 'overlap'):
                        new.basis.configure_preparation(preparation)
                        load = os.getloadavg()
                        started = time.perf_counter_ns()
                        actual = new.solve(target)
                        wall = time.perf_counter_ns()-started
                        compare(actual, expected)
                        assert actual['verified'] and actual['status'] == 'solved'
                        certificate = actual['basis_certificate']
                        constant = certificate['constant_identity_stats']
                        assert constant['requested'] == ('original', 'prepared', 'folded').index(constant_mode)
                        assert constant['used'] == int(constant_mode != 'original')
                        words = (1 << (2*item['ell'])) * ((item['n']+63)//64) if constant_mode != 'original' else 0
                        assert constant['prepared_words'] == words
                        assert constant['workspace_bytes'] == words * (4 if item['n'] <= 32 else 8)
                        assert constant['features'] == 1 + item['ell']*(item['ell']+1)//2
                        assert constant['avoided_parities'] == certificate['symmetry_check_stats']['avoided_constant_parities']
                        assert certificate['preparation_stats']['used'] == int(preparation != 'serial')
                        assert certificate['preparation_stats']['recomputed'] == 0
                        device = certificate['device_transform_stats']
                        assert device['requested'] == device['executed'] == int(transform_backend != 'cpu')
                        if transform_backend != 'cpu':
                            low = min(2*item['ell'], 5 if item['n'] <= 32 else 4) if transform_backend == 'metal_simd' else 0
                            assert device['fused_stages'] == low
                            assert device['dispatches'] == 2 * item['ell'] - low + int(low > 0)
                            assert device['input_bytes'] == device['output_bytes'] == device['scratch_bytes']
                        raw = actual.pop('proof_bytes')
                        assert hashlib.sha256(raw).hexdigest() == expected['proof_sha256']
                        report['proofs'].setdefault(actual['proof_sha256'], base64.b64encode(raw).decode())
                        row = {'name': item['name'], 'workload_sha256': item['workload_sha256'],
                               'backend': backend, 'transform_backend': transform_backend,
                               'sanitizer': sanitizer, 'constant_identity': constant_mode, 'preparation': preparation, 'wall_ns': wall,
                               'load_start': load, 'load_end': os.getloadavg(), 'result': actual}
                        report['queries'].append(row)
                        journal.write(json.dumps(row, separators=(',', ':'))+'\n'); journal.flush()
                    print('COMPLETE_QUERIES_PASS', item['name'], backend, transform_backend, sanitizer, constant_mode, flush=True)
    assert len(report['queries']) == len(inputs) * len(modes) * 3 * 3
    for path, digest in frozen.items(): assert sha(Path(path)) == digest, path
    report['status'] = 'PASS'
    args.output.write_bytes(gzip.compress(json.dumps(report, separators=(',', ':')).encode(), mtime=0))
    print('INDEPENDENT_TRANSFORM_QUERY_PASS', len(report['queries']), 'fresh complete queries', flush=True)


if __name__ == '__main__':
    main()
