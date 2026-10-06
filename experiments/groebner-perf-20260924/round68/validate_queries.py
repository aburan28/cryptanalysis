"""Fresh complete-query comparisons against the unchanged producer and checker graph."""
import argparse
import base64
from contextlib import ExitStack
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

from adapter import HERE, ProjectionQuery, base, producer
from bindings import bindings
from query_cases import query_modes, check_accounting
from public_replay import Point


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare(actual, expected):
    for name in ('status', 'complete', 'basis_terms', 'basis_sha256', 'proof_sha256',
                 'assignment', 'verified', 'gpu_projection_stats'):
        assert actual.get(name) == expected.get(name), name
    for name in ('metrics', 'partial_stats', 'projection_stats', 'normalization_stats',
                 'multiplier_stats', 'deferred_stats', 'symmetry_stats'):
        integers = lambda record: {k: v for k, v in record.items() if type(v) in (int, bool)}
        assert integers(actual[name]) == integers(expected[name]), name
    assert actual['basis_certificate']['solutions'] == expected['basis_certificate']['solutions']
    for name in ('stats', 'partial_stats', 'identity_check_stats', 'symmetry_check_stats',
                 'partial_locality_stats', 'partial_reservation_stats', 'constant_identity_stats'):
        integers = lambda record: {k: v for k, v in record.items() if type(v) in (int, bool)}
        assert integers(actual['basis_certificate'][name]) == integers(expected['basis_certificate'][name]), name
    assert actual['preparation_schedule']['drained']
    assert sum(actual['phases_ns'].values()) == actual['complete_query_ns']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--metal', action='store_true')
    args = parser.parse_args()
    if args.output.exists(): raise FileExistsError(args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frozen = bindings()
    fixture = HERE.parent / 'round40/fixtures/inputs.json.gz'
    frozen[str(fixture)] = sha(fixture)
    assert frozen[str(Path(__file__).resolve())] == sha(Path(__file__))
    inputs = json.loads(gzip.decompress(fixture.read_bytes()))
    availability = {'requested': args.metal, 'status': 'NOT_REQUESTED'}
    if args.metal:
        try:
            with producer.Producer(2, 3, 3, backend='metal') as probe:
                probe.configure_producer_transform('metal_tiled')
                availability.update(status='AVAILABLE', device=probe.device)
        except ValueError as error:
            if str(error) != 'requested Metal device unavailable': raise
            availability.update(status='UNAVAILABLE', detail=str(error))
    report = {'schema': 'shared-producer-transform-query-validation/1', 'status': 'RUNNING',
              'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=HERE, text=True).strip(),
              'metal': availability, 'executed_bindings': frozen, 'fixture_sha256': sha(fixture),
              'validator_sha256': sha(Path(__file__)), 'queries': [], 'proofs': {}, 'unsupported_setups': {},
              'timing_eligible': False, 'host_isolation_receipt': None, 'candidate_id': None, 'online_speedup': None}
    modes = query_modes(availability['status'] == 'AVAILABLE')
    with gzip.open(args.output.with_suffix('.jsonl.gz'), 'xt', compresslevel=1) as journal:
        for backend, checker_backend, sanitizer, transform in modes:
            with ExitStack() as stack:
                contexts = {}
                for item in inputs:
                    shape = tuple(item[key] for key in ('n', 'mod', 'b', 'm', 'ell'))
                    if shape not in contexts:
                        config = dict(backend=backend, identity='factored_local', transform='full',
                                      transform_backend=checker_backend, constant_identity='prepared')
                        setup_started = time.perf_counter_ns()
                        try:
                            actual = stack.enter_context(ProjectionQuery(*shape, sanitizer=sanitizer,
                                                                         producer_transform=transform, **config))
                        except RuntimeError as error:
                            if not (backend == 'metal' and transform != 'cpu' and item['n'] > 32 and
                                    str(error) == 'producer transform requires a compatible Metal producer'):
                                raise
                            setup_id = hashlib.sha256(json.dumps([shape, backend, checker_backend, sanitizer, transform]).encode()).hexdigest()
                            report['unsupported_setups'][setup_id] = {
                                'shape': shape, 'backend': backend, 'transform_backend': checker_backend,
                                'sanitizer': sanitizer, 'producer_transform': transform,
                                'detail': str(error), 'wall_ns': time.perf_counter_ns() - setup_started,
                                'stage': 'target-independent setup', 'queries_executed': 0,
                            }
                            contexts[shape] = None, setup_id
                            actual = None
                        # The unchanged Metal wrapper has no sanitizer build;
                        # compare its exact output/counters to the new sanitized code.
                        if actual is not None:
                            expected = stack.enter_context(base.ProjectionQuery(*shape,
                                sanitizer=sanitizer if backend == 'cpu' else False, **config))
                            assert actual.basis.producer.path.parent.parent.name == 'round68'
                            assert expected.basis.producer.path.parent.parent.name == 'round51'
                            assert actual.checker.path.parent.parent.name == expected.checker.path.parent.parent.name == 'round66'
                            contexts[shape] = actual, expected
                    new, old = contexts[shape]
                    if new is None:
                        # One rejected invariant setup makes three planned
                        # preparation cells unavailable, not three query attempts.
                        for preparation in ('serial', 'prepared', 'overlap'):
                            row = {'name': item['name'], 'workload_sha256': item['workload_sha256'],
                                   'backend': backend, 'transform_backend': checker_backend, 'sanitizer': sanitizer,
                                   'producer_transform': transform, 'constant_identity': 'prepared', 'preparation': preparation,
                                   'attempted_query': False, 'wall_ns': None, 'setup_failure_id': old,
                                   'result': {'status': 'unsupported', 'complete': False, 'verified': False,
                                              'detail': report['unsupported_setups'][old]['detail']}}
                            report['queries'].append(row)
                            journal.write(json.dumps(row, separators=(',', ':')) + '\n'); journal.flush()
                        print('UNSUPPORTED_SETUP_RETAINED', item['name'], checker_backend, sanitizer, transform, flush=True)
                        continue
                    target = Point(**item['target'])
                    expected = old.solve(target)
                    assert expected['verified'] and expected['status'] == 'solved'
                    for preparation in ('serial', 'prepared', 'overlap'):
                        new.basis.configure_preparation(preparation)
                        load = os.getloadavg()
                        started = time.perf_counter_ns()
                        actual = new.solve(target)
                        elapsed = time.perf_counter_ns() - started
                        compare(actual, expected)
                        check_accounting(actual, item, backend, transform)
                        assert actual['basis_certificate']['preparation_stats']['used'] == int(preparation != 'serial')
                        assert actual['basis_certificate']['preparation_stats']['recomputed'] == 0
                        raw = actual.pop('proof_bytes')
                        assert raw == expected['proof_bytes'] and hashlib.sha256(raw).hexdigest() == actual['proof_sha256']
                        report['proofs'].setdefault(actual['proof_sha256'], base64.b64encode(raw).decode())
                        row = {'name': item['name'], 'workload_sha256': item['workload_sha256'],
                               'backend': backend, 'transform_backend': checker_backend, 'sanitizer': sanitizer,
                               'producer_transform': transform, 'constant_identity': 'prepared', 'preparation': preparation,
                               'attempted_query': True, 'wall_ns': elapsed, 'load_start': load, 'load_end': os.getloadavg(), 'result': actual}
                        report['queries'].append(row)
                        journal.write(json.dumps(row, separators=(',', ':')) + '\n'); journal.flush()
                    print('COMPLETE_QUERY_PASS', item['name'], backend, checker_backend, sanitizer, transform, flush=True)
    assert len(report['queries']) == len(inputs) * len(modes) * 3
    for path, digest in frozen.items(): assert sha(Path(path)) == digest, path
    report['status'] = 'PASS'
    args.output.write_bytes(gzip.compress(json.dumps(report, separators=(',', ':')).encode(), mtime=0))
    verified = sum(row['result']['verified'] for row in report['queries'])
    print('SHARED_PRODUCER_QUERY_PASS', verified, 'fresh complete queries;',
          len(report['queries']) - verified, 'unsupported planned cells;',
          len(report['unsupported_setups']), 'rejected setups', flush=True)


if __name__ == '__main__': main()
