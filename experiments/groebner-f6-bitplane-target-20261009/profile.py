"""Pair complete fresh-target bitplane and packed-ANF separator queries."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import statistics
import subprocess

from bitplane_query import HERE, BitplaneContext
from chain_fixture import fixture

TARGETS = (0, 1, 2, 9, 100, 511)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reps', type=int, default=6)
    args = parser.parse_args()
    assert args.reps > 0
    root = HERE.parents[1]
    for path in list(HERE.glob('*.py')) + list(HERE.glob('*.cpp')):
        assert path.read_bytes() == subprocess.check_output(
            ['git', 'show', 'HEAD:' + str(path.relative_to(root))], cwd=root)
    receipt = json.loads((HERE / 'build/receipt.json').read_text())
    assert receipt['source_commit'] == subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    for name, digest in receipt['sources'].items():
        assert sha(HERE / name) == digest
    for name, digest in receipt['binaries'].items():
        assert sha(HERE / 'build' / name) == digest
    reference_path = HERE.parent / 'groebner-f6-packed-20261009/evidence/semantic.json'
    reference = json.loads(reference_path.read_text())
    assert reference['status'] == 'PASS' and len(reference['rows']) == 512
    args.output.mkdir(parents=True, exist_ok=False)
    report = dict(schema='f6-bitplane-complete-query/1', status='RUNNING',
                  source_commit=receipt['source_commit'], build=receipt,
                  reference_sha256=sha(reference_path), targets=list(TARGETS),
                  repetitions=args.reps, rows=[], summary={}, setup={},
                  timing_eligible=False, qualified_speedup=None)
    path = args.output / 'report.json'
    save(path, report)
    lock = Path('/private/tmp/f6-bitplane-complete-query.lock')
    with lock.open('a') as guard:
        fcntl.flock(guard, fcntl.LOCK_EX)
        context = BitplaneContext(fixture(9, 4, 3, 1))
        report['setup'] = dict(context_ns=context.setup_ns,
                               packed=context.baseline.compact.setup,
                               bitplane=context.index.setup)
        save(path, report)
        try:
            for repetition in range(-1, args.reps):
                order = TARGETS[repetition % len(TARGETS):] + TARGETS[:repetition % len(TARGETS)]
                for target_x in order:
                    arms = ('packed', 'bitplane') if repetition % 2 == 0 else ('bitplane', 'packed')
                    pair = {}
                    for arm in arms:
                        try:
                            result = context.run(target_x, arm)
                            expected = reference['rows'][target_x]
                            assert result['status'] == expected['status']
                            if result['status'] == 'satisfiable':
                                assert result['equation_verified'] is True
                                assert result['point_verified'] is True
                            row = dict(repetition=repetition + 1,
                                       warmup=repetition < 0, target_x=target_x,
                                       arm=arm, execution='completed', result=result)
                            pair[arm] = result
                        except Exception as error:
                            row = dict(repetition=repetition + 1,
                                       warmup=repetition < 0, target_x=target_x,
                                       arm=arm, execution='failure', error=repr(error))
                        report['rows'].append(row)
                        save(path, report)
                    if len(pair) != 2 or pair['packed']['status'] != pair['bitplane']['status']:
                        report['status'] = 'INCOMPLETE'
                        save(path, report)
                        raise SystemExit(1)
        finally:
            context.close()
    for target_x in TARGETS:
        pairs = {}
        for row in report['rows']:
            if row['target_x'] == target_x and not row['warmup']:
                pairs.setdefault(row['repetition'], {})[row['arm']] = row['result']
        assert len(pairs) == args.reps and all(len(pair) == 2 for pair in pairs.values())
        ratios = [pair['bitplane']['online_ns'] / pair['packed']['online_ns']
                  for pair in pairs.values()]
        report['summary'][str(target_x)] = dict(n=len(ratios),
            median_bitplane_over_packed=statistics.median(ratios),
            range_bitplane_over_packed=[min(ratios), max(ratios)], ratios=ratios,
            status=next(iter(pairs.values()))['bitplane']['status'])
    report['status'] = 'PASS'
    save(path, report)
    print('F6_BITPLANE_PROFILE_PASS', len(report['rows']), flush=True)


if __name__ == '__main__':
    main()
