"""Frozen complete-query comparison; keep every admission and execution outcome."""
import argparse
import base64
from contextlib import ExitStack
import datetime
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import time

from adapter import HERE, load, ProjectionQuery
from public_replay import Point


def read(path):
    return json.loads(gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    data = json.dumps(value, separators=(',', ':')).encode()
    path.write_bytes(gzip.compress(data, mtime=0) if path.suffix == '.gz' else data + b'\n')


from bindings import bindings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--correctness', type=Path, required=True)
    parser.add_argument('--audit', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.mkdir(parents=True)
    plan_path = HERE / 'measurement_plan.json'
    plan = read(plan_path)
    frozen = bindings()
    fixtures_path = HERE.parent / 'round40/fixtures/inputs.json.gz'
    for p in (Path(__file__), plan_path, args.correctness, args.audit, fixtures_path):
        frozen[str(p)] = sha(p)
    correctness, audit = read(args.correctness), read(args.audit)
    assert correctness['status'] == audit['status'] == 'PASS'
    assert audit['input_sha256'] == sha(args.correctness)
    for path, digest in correctness['executed_bindings'].items():
        assert sha(Path(path)) == digest, path
        frozen[path] = digest
    assert correctness['schema'] == 'independent-preparation-validation/1'
    assert correctness['metal']['status'] == 'AVAILABLE'
    expected = {(r['name'], r['backend'], r['transform'], r['preparation']): r['result']
                for r in correctness['queries'] if not r['sanitizer'] and r['symmetry']}
    audited = {(r['name'], r['backend'], r['transform'], r['preparation']): r
               for r in audit['records'] if not r['sanitizer'] and r['symmetry']}
    prior = load('prepare53_benchmark_prior52', HERE.parent / 'round52/adapter.py')
    items = sorted(read(fixtures_path), key=lambda i: (-i['nvars'], i['name']))
    threshold = os.cpu_count() * plan['max_load_per_logical_cpu']
    summary = {'schema': 'independent-preparation-paired-query/1', 'plan': plan, 'frozen': frozen,
               'host': {'architecture': platform.machine(), 'platform': platform.platform(),
                        'python': platform.python_version(), 'logical_cpus': os.cpu_count(),
                        'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()},
               'trials': [], 'candidate_id': None, 'online_speedup': None}
    rejected = 0
    rng = random.Random(plan['order_seed'])
    for item in items:
        for trial in range(plan['trials_per_input']):
            name = item['name'] + '-r' + str(trial + 1)
            record = {'name': name, 'input': item['name'], 'workload_sha256': item['workload_sha256'],
                      'admission': [], 'rows': [], 'setup': [], 'status': 'PENDING', 'timing_eligible': False}
            summary['trials'].append(record)
            begin = time.monotonic()
            if rejected >= plan['max_rejected_admissions']:
                record['status'] = 'NOT_RUN_ADMISSION_EXHAUSTED'
            else:
                while True:
                    loadavg = os.getloadavg()
                    record['admission'].append({'load': loadavg, 'elapsed': time.monotonic() - begin})
                    if loadavg[0] <= threshold:
                        break
                    if time.monotonic() - begin >= plan['admission_wait_seconds']:
                        rejected += 1
                        record['status'] = 'NOT_ADMITTED'
                        break
                    time.sleep(plan['admission_poll_seconds'])
            if record['status'] != 'PENDING':
                save(args.output / (name + '.json.gz'), record)
                save(args.output / 'summary.json.gz', summary)
                print(record['status'], name, flush=True)
                continue
            good = quiet = True
            proofs = {}
            with ExitStack() as stack:
                contexts = {}
                setup_failure = None
                shape = tuple(item[k] for k in ('n', 'mod', 'b', 'm', 'ell'))
                for arm in plan['arms']:
                    start = time.perf_counter_ns()
                    cls = prior.ProjectionQuery if arm.startswith('prior') else ProjectionQuery
                    opts = {'backend': 'cpu' if arm.endswith('cpu') else 'metal',
                            'identity': 'factored_local', 'transform': 'tile16' if 'tile16' in arm else 'full'}
                    if not arm.startswith('prior'):
                        opts['preparation'] = arm.split('-')[0]
                    try:
                        q = stack.enter_context(cls(*shape, **opts))
                    except Exception as error:
                        good = False
                        setup_failure = {'arm': arm, 'detail': repr(error),
                                         'elapsed_ns': time.perf_counter_ns()-start}
                        record['setup_failure'] = setup_failure
                        break
                    contexts[arm] = q
                    record['setup'].append({'arm': arm, 'elapsed_ns': time.perf_counter_ns() - start,
                                            'producer': str(q.basis.producer.path), 'device': q.basis.producer.device,
                                            'max_query_workers': 2 if arm.startswith('overlap') else 1,
                                            'resource_envelope': plan['resource_envelope']})
                for repetition in ([] if setup_failure else range(-plan['warmups'], plan['measured_pairs'])):
                    order = list(plan['arms'])
                    rng.shuffle(order)
                    for arm in order:
                        load_start = os.getloadavg()
                        start = time.perf_counter_ns()
                        try:
                            answer = contexts[arm].solve(Point(**item['target']))
                        except Exception as error:
                            answer = {'status': 'exception', 'verified': False, 'detail': repr(error)}
                            if hasattr(error, 'preparation_schedule'):
                                answer['preparation_schedule'] = error.preparation_schedule
                        elapsed = time.perf_counter_ns() - start
                        load_end = os.getloadavg()
                        proof = answer.pop('proof_bytes', None)
                        backend = 'cpu' if arm.endswith('cpu') else 'metal'
                        transform = 'tile16' if 'tile16' in arm else 'full'
                        preparation = 'serial' if arm.startswith('prior') else arm.split('-')[0]
                        key = item['name'], backend, transform, preparation
                        ref, evidence = expected[key], audited[key]
                        verified = answer.get('status') == 'solved' and answer.get('verified') is True
                        verified = verified and all(answer.get(k) == ref[k] for k in ('basis_terms', 'basis_sha256', 'assignment', 'proof_sha256'))
                        verified = verified and answer['basis_certificate']['solutions'] == evidence['roots']
                        verified = verified and proof is not None and hashlib.sha256(proof).hexdigest() == evidence['proof_sha256']
                        if not arm.startswith('prior'):
                            verified = verified and answer.get('preparation_schedule', {}).get('drained') is True
                        if proof is not None:
                            proofs.setdefault(answer['proof_sha256'], base64.b64encode(proof).decode())
                        good = good and verified
                        quiet = quiet and max(load_start[0], load_end[0]) <= threshold
                        record['rows'].append({'repetition': repetition, 'arm': arm, 'elapsed_ns': elapsed,
                                               'load_start': load_start, 'load_end': load_end,
                                               'matched_reference': bool(verified), 'answer': answer})
            record.update(status='SETUP_FAILED' if setup_failure else 'VERIFIED' if good else 'FAILED',
                          timing_eligible=bool(good and quiet), proofs=proofs)
            save(args.output / (name + '.json.gz'), record)
            # Proof payloads live in each immutable trial, not duplicated in the index.
            summary['trials'][-1] = {k: v for k, v in record.items() if k not in ('proofs', 'rows')}
            summary['trials'][-1].update(report_sha256=sha(args.output / (name + '.json.gz')), queries=len(record['rows']))
            save(args.output / 'summary.json.gz', summary)
            print('PAIRED_TRIAL', name, record['status'], 'qualified', record['timing_eligible'], flush=True)
    for path, expected_sha in frozen.items():
        assert sha(Path(path)) == expected_sha, path
    summary['status'] = 'COMPLETE'
    save(args.output / 'summary.json.gz', summary)


if __name__ == '__main__':
    main()
