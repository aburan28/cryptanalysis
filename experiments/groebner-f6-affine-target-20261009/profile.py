"""Pair complete fresh-target F6 queries with and without affine ANF setup."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import statistics
import subprocess

from affine_query import HERE, AffineContext
from chain_fixture import fixture

TARGETS = (0, 1, 2, 9, 100, 511)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reps', type=int, default=5)
    args = parser.parse_args()
    assert args.reps > 0
    root = HERE.parents[1]
    for path in HERE.glob('*.py'):
        assert path.read_bytes() == subprocess.check_output(
            ['git', 'show', 'HEAD:' + str(path.relative_to(root))], cwd=root)
    receipt_path = HERE / 'build/receipt.json'
    receipt = json.loads(receipt_path.read_text())
    assert receipt['source_commit'] == subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    for name, digest in receipt['sources'].items():
        assert sha(HERE / name) == digest
    reference_path = HERE.parent / 'groebner-f6-packed-20261009/evidence/semantic.json'
    reference = json.loads(reference_path.read_text())
    assert reference['status'] == 'PASS' and len(reference['rows']) == 512
    args.output.mkdir(parents=True, exist_ok=False)
    report = dict(schema='f6-affine-target-complete-query/1', status='RUNNING',
                  source_commit=receipt['source_commit'], build=receipt,
                  reference_sha256=sha(reference_path), targets=list(TARGETS),
                  repetitions=args.reps, rows=[], summary={}, setup={},
                  timing_eligible=False, qualified_speedup=None)
    target = args.output / 'report.json'
    save(target, report)
    lock = Path('/private/tmp/f6-affine-complete-query.lock')
    with lock.open('a') as guard:
        fcntl.flock(guard, fcntl.LOCK_EX)
        context = AffineContext(fixture(9, 4, 3, 1))
        report['setup'] = dict(context_ns=context.setup_ns,
                               compact=context.base.compact.setup,
                               message=context.base.base.message.setup,
                               monomials=len(context.template.universe),
                               lookup_groups=len(context.template.groups))
        save(target, report)
        try:
            for repetition in range(-1, args.reps):
                order = TARGETS[repetition % len(TARGETS):] + TARGETS[:repetition % len(TARGETS)]
                for target_x in order:
                    arms = ('compact', 'affine') if repetition % 2 == 0 else ('affine', 'compact')
                    pair = {}
                    for arm in arms:
                        try:
                            result = context.run(target_x, arm)
                            expected = reference['rows'][target_x]
                            for key in ('status', 'assignment', 'point_verified',
                                        'equation_verified'):
                                assert result[key] == expected[key], (target_x, key)
                            row = dict(repetition=repetition + 1, warmup=repetition < 0,
                                       target_x=target_x, arm=arm, execution='completed',
                                       result=result)
                            pair[arm] = result
                        except Exception as error:
                            row = dict(repetition=repetition + 1, warmup=repetition < 0,
                                       target_x=target_x, arm=arm, execution='failure',
                                       error=repr(error))
                        report['rows'].append(row)
                        save(target, report)
                    if len(pair) != 2:
                        report['status'] = 'INCOMPLETE'
                        save(target, report)
                        raise SystemExit(1)
                    for key in ('status', 'assignment', 'point_verified',
                                'equation_verified'):
                        assert pair['compact'][key] == pair['affine'][key], key
        finally:
            context.close()
    for target_x in TARGETS:
        pairs = {}
        for row in report['rows']:
            if row['target_x'] == target_x and not row['warmup']:
                pairs.setdefault(row['repetition'], {})[row['arm']] = row['result']
        assert len(pairs) == args.reps and all(len(pair) == 2 for pair in pairs.values())
        ratios = [pair['affine']['online_ns'] / pair['compact']['online_ns']
                  for pair in pairs.values()]
        report['summary'][str(target_x)] = dict(n=len(ratios),
            median_affine_over_compact=statistics.median(ratios),
            range_affine_over_compact=[min(ratios), max(ratios)], ratios=ratios,
            median_delta_ms=statistics.median(
                (pair['affine']['online_ns'] - pair['compact']['online_ns']) / 1e6
                for pair in pairs.values()),
            status=next(iter(pairs.values()))['affine']['status'])
    report['status'] = 'PASS'
    save(target, report)
    print('F6_AFFINE_PROFILE_PASS', len(report['rows']), flush=True)


if __name__ == '__main__':
    main()
