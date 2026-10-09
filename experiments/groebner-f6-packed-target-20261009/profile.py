"""Pair complete compact, affine-row, and directly packed F6 queries."""
import argparse
import fcntl
import hashlib
import itertools
import json
from pathlib import Path
import statistics
import subprocess
import tempfile

from packed_query import HERE, PackedContext
from chain_fixture import fixture

TARGETS = (0, 1, 2, 9, 100, 511)
ARMS = ('compact', 'affine', 'packed')
ORDERS = tuple(itertools.permutations(ARMS))


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
    report = dict(schema='f6-packed-target-complete-query/1', status='RUNNING',
                  source_commit=receipt['source_commit'], build=receipt,
                  reference_sha256=sha(reference_path), targets=list(TARGETS),
                  arms=list(ARMS), orders=[list(order) for order in ORDERS],
                  repetitions=args.reps, rows=[], summary={}, setup={},
                  timing_eligible=False, qualified_speedup=None)
    path = args.output / 'report.json'
    save(path, report)
    lock = Path(tempfile.gettempdir()) / 'f6-packed-target-complete-query.lock'
    with lock.open('a') as guard:
        fcntl.flock(guard, fcntl.LOCK_EX)
        context = PackedContext(fixture(9, 4, 3, 1))
        report['setup'] = dict(context_ns=context.setup_ns,
                               compact=context.compact.setup,
                               monomials=len(context.affine.template.universe),
                               lookup_groups=len(context.affine.template.groups),
                               packed_capacity=context.rows.capacity,
                               offsets_slots=len(context.rows.offsets))
        save(path, report)
        try:
            for repetition in range(-1, args.reps):
                order = TARGETS[repetition % len(TARGETS):] + TARGETS[:repetition % len(TARGETS)]
                for target_index, target_x in enumerate(order):
                    arm_order = ORDERS[(repetition + target_index) % len(ORDERS)]
                    triple = {}
                    for arm in arm_order:
                        try:
                            result = context.run(target_x, arm)
                            expected = reference['rows'][target_x]
                            for key in ('status', 'assignment', 'point_verified',
                                        'equation_verified'):
                                assert result[key] == expected[key], (target_x, key)
                            row = dict(repetition=repetition + 1, warmup=repetition < 0,
                                       target_x=target_x, arm=arm, execution='completed',
                                       result=result)
                            triple[arm] = result
                        except Exception as error:
                            row = dict(repetition=repetition + 1, warmup=repetition < 0,
                                       target_x=target_x, arm=arm, execution='failure',
                                       error=repr(error))
                        report['rows'].append(row)
                        save(path, report)
                    if len(triple) != 3:
                        report['status'] = 'INCOMPLETE'
                        save(path, report)
                        raise SystemExit(1)
                    for key in ('status', 'assignment', 'point_verified',
                                'equation_verified'):
                        assert len({triple[arm][key] for arm in ARMS}) == 1, key
        finally:
            context.close()
    for target_x in TARGETS:
        triples = {}
        for row in report['rows']:
            if row['target_x'] == target_x and not row['warmup']:
                triples.setdefault(row['repetition'], {})[row['arm']] = row['result']
        assert len(triples) == args.reps and all(len(triple) == 3 for triple in triples.values())
        summary = dict(n=args.reps, status=next(iter(triples.values()))['packed']['status'])
        for reference_arm in ('affine', 'compact'):
            ratios = [triple['packed']['online_ns'] / triple[reference_arm]['online_ns']
                      for triple in triples.values()]
            summary['packed_over_' + reference_arm] = dict(
                median=statistics.median(ratios), range=[min(ratios), max(ratios)],
                ratios=ratios)
        report['summary'][str(target_x)] = summary
    report['status'] = 'PASS'
    save(path, report)
    print('F6_PACKED_TARGET_PROFILE_PASS', len(report['rows']), flush=True)


if __name__ == '__main__':
    main()
