"""Compare all n9 m4 target abscissae with independent finite-point sums."""
import argparse
import hashlib
from itertools import product
import json
from pathlib import Path
import subprocess

from chain_fixture import Curve, GF2n, fixture, retarget
from packed_separator import HERE, solve


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def point_choices(curve, x):
    point = curve.lift_x(x)
    return () if point is None else tuple(set((point, curve.neg(point))))


def point_replay(curve, assignment, m, ell, target):
    choices = [point_choices(curve, (assignment >> (i * ell)) & ((1 << ell) - 1))
               for i in range(m)]
    for points in product(*choices):
        partials = [curve.sum(list(points[:i])) for i in range(2, m + 1)]
        if all(not point.inf for point in partials) and partials[-1].x == target:
            return True
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--max-targets', type=int, default=512)
    args = parser.parse_args()
    assert 1 <= args.max_targets <= 512
    root = HERE.parents[1]
    for path in list(HERE.glob('*.py')) + list(HERE.glob('*.cpp')):
        assert path.read_bytes() == subprocess.check_output(
            ['git', 'show', 'HEAD:' + str(path.relative_to(root))], cwd=root)
    receipt = json.loads((HERE / 'build/receipt.json').read_text())
    for name, digest in receipt['binaries'].items():
        assert sha(HERE / 'build' / name) == digest
    case = fixture(9, 4, 3, 1)
    curve = Curve(GF2n(9), 1)
    options = [point for x in range(1 << case['ell'])
               for point in point_choices(curve, x)]
    reachable = set()
    for points in product(options, repeat=case['m']):
        partials = [curve.sum(list(points[:i])) for i in range(2, case['m'] + 1)]
        if all(not point.inf for point in partials):
            reachable.add(partials[-1].x)
    assert reachable and len(options) < 32
    assert not args.output.exists()
    report = dict(schema='f6-packed-semantic-screen/1', status='RUNNING',
                  source_commit=subprocess.check_output(
                      ['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
                  build_sha256=sha(HERE / 'build/receipt.json'),
                  n=9, m=4, ell=3, seed=1, target_count=args.max_targets,
                  factor_base_points=len(options), reachable_target_x=sorted(reachable),
                  rows=[], timing_eligible=False, qualified_speedup=None)

    def save():
        args.output.write_text(json.dumps(report, indent=2) + '\n')

    save()
    counterexample = next(x for x in range(512) if x not in reachable)
    unguarded = solve(case['nvars'], retarget(case, counterexample),
                     max_bag=21, max_states=100_000_000)
    assert unguarded['status'] == 'satisfiable'
    report['unlifted_counterexample'] = dict(target_x=counterexample,
                                             status=unguarded['status'],
                                             assignment=unguarded['assignment'])
    save()
    for target in range(args.max_targets):
        rows = retarget(case, target, require_liftable=True)
        result = solve(case['nvars'], rows, max_bag=21, max_states=100_000_000)
        expected = target in reachable
        actual = result['status'] == 'satisfiable'
        point_verified = (point_replay(curve, result['assignment'], case['m'],
                                       case['ell'], target) if actual else None)
        report['rows'].append(dict(target_x=target, expected_reachable=expected,
                                   status=result['status'], assignment=result['assignment'],
                                   equation_verified=result['independently_verified'],
                                   point_verified=point_verified, width=result['width'],
                                   factor_states=result['factor_states'],
                                   elimination_states=result['elimination_states'],
                                   wall_ns=result['wall_ns']))
        save()
        if actual != expected or (actual and not point_verified):
            report['status'] = 'COUNTEREXAMPLE'
            save()
            print('F6_PACKED_SEMANTIC_COUNTEREXAMPLE', target, flush=True)
            raise SystemExit(1)
        if (target + 1) % 64 == 0:
            print('F6_PACKED_SEMANTIC_PROGRESS', target + 1, flush=True)
    report['status'] = 'PASS'
    save()
    print('F6_PACKED_SEMANTIC_PASS', args.max_targets, flush=True)


if __name__ == '__main__':
    main()
