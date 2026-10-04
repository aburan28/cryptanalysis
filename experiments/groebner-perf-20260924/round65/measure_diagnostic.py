"""Balanced fresh single-query diagnostic, explicitly ineligible for speed claims."""
import argparse
from contextlib import ExitStack
import gzip
import hashlib
import itertools
import json
import os
from pathlib import Path
import time

from adapter import HERE, ProjectionQuery
from bindings import bindings
from public_replay import Point


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists(): raise FileExistsError(args.output)
    args.output.mkdir(parents=True)
    fixture = HERE.parent/'round40/fixtures/inputs.json.gz'
    inputs = {v['name']: v for v in json.loads(gzip.decompress(fixture.read_bytes()))}
    names = ('n31-m3-ell6-seed101', 'n31-m3-ell8-seed201', 'n31-m3-ell9-seed201')
    arms = ('cpu', 'metal', 'metal_simd')
    orders = list(itertools.permutations(arms)) * 3
    frozen = bindings()
    assert str(HERE/'build/receipt.json') in frozen
    frozen[str(fixture)] = sha(fixture)
    plan = {'names': names, 'arms': arms, 'orders': orders, 'producer': 'metal',
            'timing_eligible': False, 'host_isolation_receipt': None,
            'purpose': 'Balanced single-query engineering diagnostic. No aggregate speedup or automatic routing decision.',
            'interval': 'One fresh solve through independent certificate, equation and public-curve replay; copies and synchronization included; reusable context setup separately timed.',
            'executed_bindings': frozen}
    save(args.output/'plan.json', plan)
    report = {'status': 'RUNNING', 'plan_sha256': sha(args.output/'plan.json'),
              'setup': [], 'queries': [], 'timing_eligible': False,
              'candidate_id': None, 'online_speedup': None, 'aggregate_speedup': None}
    with (args.output/'queries.jsonl').open('x') as journal:
        for name in names:
            item = inputs[name]
            shape = tuple(item[k] for k in ('n', 'mod', 'b', 'm', 'ell'))
            target = Point(**item['target'])
            with ExitStack() as stack:
                contexts = {}
                for arm in arms:
                    started = time.perf_counter_ns()
                    contexts[arm] = stack.enter_context(ProjectionQuery(*shape, backend='metal',
                        transform_backend=arm, identity='factored_local', preparation='serial', transform='full'))
                    report['setup'].append({'name': name, 'arm': arm, 'wall_ns': time.perf_counter_ns()-started})
                expected = None
                for trial, order in enumerate(orders):
                    for arm in order:
                        load = os.getloadavg()
                        started = time.perf_counter_ns()
                        answer = contexts[arm].solve(target)
                        wall = time.perf_counter_ns()-started
                        raw = answer.pop('proof_bytes')
                        assert answer['verified'] and answer['status'] == 'solved'
                        assert hashlib.sha256(raw).hexdigest() == answer['proof_sha256']
                        exact = tuple(answer[k] for k in ('basis_sha256', 'proof_sha256', 'assignment'))
                        if expected is None: expected = exact
                        assert exact == expected
                        assert sum(answer['phases_ns'].values()) == answer['complete_query_ns']
                        record = {'name': name, 'arm': arm, 'trial': trial, 'order': order,
                                  'wall_ns': wall, 'load_start': load, 'load_end': os.getloadavg(), 'result': answer}
                        report['queries'].append(record)
                        journal.write(json.dumps(record, separators=(',', ':'))+'\n'); journal.flush()
            print('BALANCED_DIAGNOSTIC_PASS', name, len(orders)*len(arms), flush=True)
    for path, digest in frozen.items(): assert sha(Path(path)) == digest, path
    report['status'] = 'PASS'
    save(args.output/'report.json', report)


if __name__ == '__main__':
    main()
