"""Paired independent one-target IC runs; preparation is separate, never amortized."""
import argparse
from contextlib import ExitStack
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import sys
import time
import numpy

from ic_query import ARMS, HERE, PreparedIC, Point, kernel, sha256_hex
from identity import candidate, fixture, source_snapshot
from receipts import receipt

SEEDS = (701, 702, 703)


def eligible(report):
    admission = report['admission']
    limit = admission['logical_cpus']*admission['max_load_per_cpu']
    return (report['status'] == 'RECORDED' and admission['admitted'] and bool(report['rows'])
            and not report.get('correctness_only', False)
            and admission['load'][0] <= limit
            and all(max(row['load_start'][0], row['load_end'][0]) <= limit for row in report['rows'])
            and report['host']['load_end'][0] <= limit)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repetitions', type=int, default=15)
    parser.add_argument('--max-load-per-cpu', type=float, default=1)
    parser.add_argument('--admission-wait-seconds', type=int, default=0)
    parser.add_argument('--correctness-only', action='store_true',
                        help='retain a busy-host correctness trace; never timing eligible')
    parser.add_argument('--dimensions', type=int, nargs='+', default=[3, 6], choices=(3, 6))
    args = parser.parse_args()
    if args.repetitions < 2 or not 0 <= args.admission_wait_seconds <= 300:
        parser.error('at least two repetitions; admission wait 0..300 seconds')
    if len(set(args.dimensions)) != len(args.dimensions):
        parser.error('duplicate dimensions')
    if not math.isfinite(args.max_load_per_cpu) or args.max_load_per_cpu <= 0:
        parser.error('positive finite load limit required')
    admission_path = Path(str(args.output)+'.admission.json')
    if args.output.exists() or admission_path.exists():
        parser.error('existing result/admission cannot be overwritten')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    cpus, started, samples = os.cpu_count() or 1, time.monotonic(), []
    while True:
        load = os.getloadavg()
        samples.append({'elapsed_seconds': time.monotonic()-started, 'load': load})
        admitted = not args.correctness_only and load[0] <= cpus*args.max_load_per_cpu
        admission = {'logical_cpus': cpus, 'load': load, 'max_load_per_cpu': args.max_load_per_cpu,
                     'admitted': admitted, 'timed_attempts': 0,
                     'wait_limit_seconds': args.admission_wait_seconds, 'samples': samples}
        admission_path.write_text(json.dumps(admission, indent=2)+'\n')
        if args.correctness_only or admitted or time.monotonic()-started >= args.admission_wait_seconds:
            break
        print('waiting for admission', samples[-1], flush=True)
        time.sleep(max(0, min(30, args.admission_wait_seconds-(time.monotonic()-started))))
    if not admitted and not args.correctness_only:
        print(json.dumps({'status': 'NOT_ADMITTED', 'timed_attempts': 0}))
        raise SystemExit(2)
    snapshot = source_snapshot()
    report = {'schema': 'round20-one-target-comparison/1', 'status': 'RUNNING',
              'scope': 'Separately prepared one-target workloads per exact base; solver comparisons within a base only, no batch amortization or scaling claim',
              'correctness_only': args.correctness_only,
              'dimensions': args.dimensions, 'seeds': [401] if args.correctness_only else list(SEEDS),
              'arms': [*ARMS, 'rho'], 'repetitions': args.repetitions, 'admission': admission,
              'host': {'platform': platform.platform(), 'python': sys.version, 'logical_cpus': cpus,
                       'numpy': numpy.__version__,
                       'load_start': load, 'clock': vars(time.get_clock_info('perf_counter'))},
              'source_snapshot': snapshot,
              'source_sha256': {k: hashlib.sha256(v.encode()).hexdigest() for k, v in snapshot.items()},
              'build_receipts': {str(r): json.loads((HERE.parent/f'round{r}/build/receipt.json').read_text())
                                 for r in (14, 15, 17, 18, 20)},
              'inputs': [], 'candidates': {}, 'rows': [],
              'run_number_start': time.time_ns(),
              'qualification_rule': 'initial, every paired-group start/end and final one-minute load <= logical CPUs times declared limit; necessary, not sufficient for an exclusive host'}

    def save():
        temporary = Path(str(args.output)+'.tmp')
        temporary.write_bytes(gzip.compress(json.dumps(report, separators=(',', ':')).encode(), compresslevel=1, mtime=0))
        temporary.replace(args.output)

    rng = random.Random(2026092707)
    try:
        # This context only constructs fixtures. Neither candidate receives its
        # known fixture scalar, target, or target-dependent answer during setup.
        for ell in args.dimensions:
            with PreparedIC(ell=ell) as builder:
                if builder.preparation['status'] != 'ready':
                    raise RuntimeError('fixture preparation failed')
                for seed in report['seeds']:
                    start = time.perf_counter_ns()
                    wid, workload, expected = fixture(builder, seed)
                    report['inputs'].append({'workload_id': wid, 'workload': workload,
                                             'fixture_scalar': expected, 'fixture_ns': time.perf_counter_ns()-start})
        report['kernel_binary_sha256'] = hashlib.sha256(Path(kernel.lib()._name).read_bytes()).hexdigest()
        save()
        for frozen in report['inputs']:
            workload, wid = frozen['workload'], frozen['workload_id']
            Q = Point(**workload['target'])
            for rep in range(args.repetitions+1):
                serial = report['run_number_start']+rep
                row = {'workload_id': wid, 'repetition': rep, 'warmup': rep == 0,
                       'run_number': serial, 'load_start': os.getloadavg(), 'results': {}}
                report['rows'].append(row)
                save()
                with ExitStack() as stack:
                    prepared, started_at, identities = {}, {}, {}
                    setup_order = list(ARMS)
                    rng.shuffle(setup_order)
                    row['setup_order'] = setup_order
                    for arm in setup_order:
                        started_at[arm] = time.perf_counter_ns()
                        q = stack.enter_context(PreparedIC(arm=arm, ell=workload['factor_base_policy']['ell'],
                                                          collection_seed=workload['collection_seed']))
                        prepared[arm] = q
                        if q.preparation['status'] == 'ready':
                            excluded = sorted((p.x, p.y, p.inf) for p in q.seen_points)
                            if sha256_hex(excluded) != workload['excluded_points_sha256']:
                                raise RuntimeError('prepared point set differs from frozen workload')
                        cid, manifest = candidate(q, snapshot)
                        identities[arm] = cid, manifest
                        report['candidates'][cid] = manifest
                    order = [*ARMS, 'rho']
                    rng.shuffle(order)
                    row['order'] = order
                    for arm in order:
                        cpu_start = time.process_time_ns()
                        if arm == 'rho':
                            answer = prepared['baseline'].rho(Q)
                        else:
                            answer = prepared[arm].recover(Q, workload['rerandomization_seed'])
                        row['results'][arm] = {'answer': answer, 'cpu_ns': time.process_time_ns()-cpu_start}
                        if arm != 'rho':
                            row['results'][arm]['elapsed_from_preparation_start_ns'] = time.perf_counter_ns()-started_at[arm]
                        report['admission']['timed_attempts'] += 1
                        save()
                    rho = row['results']['rho']['answer']
                    row['receipts'] = {}
                    for arm in ARMS:
                        sample = row['results'][arm]
                        sample['fixture_scalar_matches'] = sample['answer']['scalar'] == frozen['fixture_scalar']
                        if sample['answer']['verified'] and not sample['fixture_scalar_matches']:
                            raise RuntimeError('recovered scalar differs from the external fixture')
                        row['receipts'][arm] = receipt(prepared[arm], *identities[arm], wid, workload,
                            sample['answer'], rho, serial, sample['elapsed_from_preparation_start_ns'])
                    if rho['verified'] and rho['scalar'] != frozen['fixture_scalar']:
                        raise RuntimeError('rho differs from the external fixture')
                row['load_end'] = os.getloadavg()
                save()
            print('workload', wid, 'completed', args.repetitions, 'pairs plus one warmup', flush=True)
        report['status'] = 'RECORDED'
    except BaseException as error:
        report.update(status='INTERRUPTED', interruption=repr(error))
        raise
    finally:
        report['host']['load_end'] = os.getloadavg()
        report['timing_admission_eligible'] = eligible(report)
        save()


if __name__ == '__main__':
    main()
