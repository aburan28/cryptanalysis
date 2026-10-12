"""Frozen packed-factor S3-chain panel with original-equation replay."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from chain_fixture import fixture
from packed_separator import HERE, solve


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--n', type=int, default=9)
    parser.add_argument('--ell', type=int, default=3)
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--m', type=int, action='append')
    parser.add_argument('--max-bag', type=int, default=21)
    parser.add_argument('--max-states', type=int, default=100_000_000)
    args = parser.parse_args()
    root = HERE.parents[1]
    for path in list(HERE.glob('*.py')) + list(HERE.glob('*.cpp')):
        assert path.read_bytes() == subprocess.check_output(
            ['git', 'show', 'HEAD:' + str(path.relative_to(root))], cwd=root)
    receipt = json.loads((HERE / 'build/receipt.json').read_text())
    for name, digest in receipt['binaries'].items():
        assert sha(HERE / 'build' / name) == digest
    args.output.mkdir(parents=True, exist_ok=False)
    report = dict(schema='f6-packed-s3-panel/1', status='RUNNING',
                  source_commit=subprocess.check_output(
                      ['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
                  scripts={p.name: sha(p) for p in HERE.glob('*.py')},
                  build=receipt, rows=[], timing_eligible=False,
                  qualified_speedup=None)
    target = args.output / 'report.json'
    target.write_text(json.dumps(report, indent=2) + '\n')
    for m in args.m or (3, 4, 5, 6):
        case = fixture(args.n, m, args.ell, args.seed)
        results = {}
        for sanitized in (False, True):
            result = solve(case['nvars'], case['equations'],
                           max_bag=args.max_bag, max_states=args.max_states,
                           sanitized=sanitized)
            assert result['status'] == 'satisfiable'
            assert result['width'] == case['structural_profile']['induced_width']
            assert result['independently_verified'] is True
            results['ubsan' if sanitized else 'optimized'] = result
        assert results['optimized']['assignment'] == results['ubsan']['assignment']
        row = dict(case=case, results=results)
        path = args.output / f'n{args.n}-m{m}-ell{args.ell}-seed{args.seed}.json'
        path.write_text(json.dumps(row, indent=2) + '\n')
        report['rows'].append(dict(n=args.n, m=m, ell=args.ell, seed=args.seed,
                                   status='PASS', result=path.name, sha256=sha(path)))
        target.write_text(json.dumps(report, indent=2) + '\n')
        print('F6_PACKED_CASE_PASS', m, results['optimized']['width'], flush=True)
    report['status'] = 'PASS'
    target.write_text(json.dumps(report, indent=2) + '\n')
    print('F6_PACKED_PANEL_PASS', len(report['rows']), flush=True)


if __name__ == '__main__':
    main()
