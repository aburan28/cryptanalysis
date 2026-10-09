"""Pair complete fresh-target compact and full-message F6 queries."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import statistics
import subprocess

from compact_query import HERE, CompactContext
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
    receipt = json.loads((HERE / 'build/receipt.json').read_text())
    for name, digest in receipt['binaries'].items():
        assert sha(HERE / 'build' / name) == digest
    reference_path = HERE.parent / 'groebner-f6-packed-20261009/evidence/semantic.json'
    reference = json.loads(reference_path.read_text())
    assert reference['status'] == 'PASS' and len(reference['rows']) == 512
    args.output.mkdir(parents=True, exist_ok=False)
    report = dict(schema='f6-compact-boundary-complete-query/1', status='RUNNING',
                  source_commit=subprocess.check_output(
                      ['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
                  build=receipt, reference_sha256=sha(reference_path),
                  targets=list(TARGETS), repetitions=args.reps,
                  rows=[], summary={}, setup={},
                  timing_eligible=False, qualified_speedup=None)
    target = args.output / 'report.json'
    save(target, report)
    lock = Path('/private/tmp/f6-compact-complete-query.lock')
    with lock.open('a') as guard:
        fcntl.flock(guard, fcntl.LOCK_EX)
        context = CompactContext(fixture(9, 4, 3, 1))
        report['setup'] = dict(context_ns=context.setup_ns,
                               message=context.base.message.setup,
                               compact=context.compact.setup)
        save(target, report)
        try:
            for repetition in range(-1, args.reps):
                order = TARGETS[repetition % len(TARGETS):] + TARGETS[:repetition % len(TARGETS)]
                for target_x in order:
                    arms = ('message', 'compact') if repetition % 2 == 0 else ('compact', 'message')
                    pair = {}
                    for arm in arms:
                        try:
                            result = context.run(target_x, arm)
                            expected = reference['rows'][target_x]
                            assert result['status'] == expected['status']
                            assert result['assignment'] == expected['assignment']
                            assert result['point_verified'] == expected['point_verified']
                            assert result['equation_verified'] == expected['equation_verified']
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
                    for key in ('status', 'assignment', 'point_verified', 'equation_verified'):
                        assert pair['message'][key] == pair['compact'][key], key
        finally:
            context.close()
    for target_x in TARGETS:
        pairs = {}
        for row in report['rows']:
            if row['target_x'] == target_x and not row['warmup']:
                pairs.setdefault(row['repetition'], {})[row['arm']] = row['result']
        assert len(pairs) == args.reps and all(len(pair) == 2 for pair in pairs.values())
        ratios = [pair['compact']['online_ns'] / pair['message']['online_ns']
                  for pair in pairs.values()]
        deltas = [(pair['compact']['online_ns'] - pair['message']['online_ns']) / 1e6
                  for pair in pairs.values()]
        report['summary'][str(target_x)] = dict(n=len(ratios),
            median_compact_over_message=statistics.median(ratios),
            range_compact_over_message=[min(ratios), max(ratios)],
            median_delta_ms=statistics.median(deltas), ratios=ratios,
            status=next(iter(pairs.values()))['compact']['status'])
    report['status'] = 'PASS'
    save(target, report)
    print('F6_COMPACT_PROFILE_PASS', len(report['rows']), flush=True)


if __name__ == '__main__':
    main()
