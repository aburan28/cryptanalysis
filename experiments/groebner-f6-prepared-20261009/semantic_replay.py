"""Replay every frozen target through a reusable static-factor layout."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from prepared_query import HERE, QueryContext
from chain_fixture import fixture


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--max-targets', type=int, default=512)
    args = parser.parse_args()
    assert 1 <= args.max_targets <= 512 and not args.output.exists()
    root = HERE.parents[1]
    for path in list(HERE.glob('*.py')) + list(HERE.glob('*.cpp')):
        assert path.read_bytes() == subprocess.check_output(
            ['git', 'show', 'HEAD:' + str(path.relative_to(root))], cwd=root)
    receipt = json.loads((HERE / 'build/receipt.json').read_text())
    for name, digest in receipt['binaries'].items():
        assert sha(HERE / 'build' / name) == digest
    reference_path = HERE.parent / 'groebner-f6-packed-20261009/evidence/semantic.json'
    reference = json.loads(reference_path.read_text())
    assert reference['status'] == 'PASS' and len(reference['rows']) == 512
    case = fixture(9, 4, 3, 1)
    context = QueryContext(case)
    report = dict(schema='f6-prepared-512-target-replay/1', status='RUNNING',
                  source_commit=subprocess.check_output(
                      ['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
                  reference_sha256=sha(reference_path), setup_ns=context.setup_ns,
                  layout=context.layout.setup, rows=[], timing_eligible=False,
                  qualified_speedup=None)
    save(args.output, report)
    try:
        for target in range(args.max_targets):
            try:
                result = context.run(target, 'prepared')
                frozen = reference['rows'][target]
                match = all((result['status'] == frozen['status'],
                             result['assignment'] == frozen['assignment'],
                             result['point_verified'] == frozen['point_verified'],
                             result['solver']['width'] == frozen['width'],
                             result['solver']['factor_states'] == frozen['factor_states'],
                             result['solver']['elimination_states'] == frozen['elimination_states']))
                row = dict(target_x=target, execution='completed', match=match,
                           result=result)
            except Exception as error:
                row = dict(target_x=target, execution='failure', match=False,
                           error=repr(error))
            report['rows'].append(row)
            save(args.output, report)
            if not row['match']:
                report['status'] = 'COUNTEREXAMPLE'
                save(args.output, report)
                print('F6_PREPARED_COUNTEREXAMPLE', target, flush=True)
                raise SystemExit(1)
            if (target + 1) % 64 == 0:
                print('F6_PREPARED_REPLAY_PROGRESS', target + 1, flush=True)
    finally:
        context.close()
    report['status'] = 'PASS'
    save(args.output, report)
    print('F6_PREPARED_REPLAY_PASS', args.max_targets, flush=True)


if __name__ == '__main__':
    main()
