"""Replay all 512 S3 targets against the independent packed-factor result."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from bitplane_query import HERE, BitplaneContext
from chain_fixture import fixture


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists()
    root = HERE.parents[1]
    for path in list(HERE.glob('*.py')) + list(HERE.glob('*.cpp')):
        assert path.read_bytes() == subprocess.check_output(
            ['git', 'show', 'HEAD:' + str(path.relative_to(root))], cwd=root)
    receipt = json.loads((HERE / 'build/receipt.json').read_text())
    reference_path = HERE.parent / 'groebner-f6-packed-20261009/evidence/semantic.json'
    reference = json.loads(reference_path.read_text())
    assert reference['status'] == 'PASS' and len(reference['rows']) == 512
    context = BitplaneContext(fixture(9, 4, 3, 1))
    report = dict(schema='f6-bitplane-target-512-replay/1', status='RUNNING',
                  source_commit=receipt['source_commit'], build=receipt,
                  reference_sha256=sha(reference_path), setup_ns=context.setup_ns,
                  static_setup=context.index.setup, rows=[],
                  timing_eligible=False, qualified_speedup=None)
    save(args.output, report)
    try:
        for target_x in range(512):
            try:
                baseline = context.run(target_x, 'packed')
                candidate = context.run(target_x, 'bitplane')
                frozen = reference['rows'][target_x]
                status_match = (baseline['status'] == candidate['status'] ==
                                frozen['status'])
                valid = (candidate['equation_verified'] is True and
                         candidate['point_verified'] is True
                         if candidate['status'] == 'satisfiable'
                         else candidate['assignment'] is None)
                row = dict(target_x=target_x, execution='completed',
                           match=status_match and valid,
                           same_assignment=baseline['assignment'] == candidate['assignment'],
                           baseline=baseline, candidate=candidate)
            except Exception as error:
                row = dict(target_x=target_x, execution='failure', match=False,
                           error=repr(error))
            report['rows'].append(row)
            save(args.output, report)
            if not row['match']:
                report['status'] = 'COUNTEREXAMPLE'
                save(args.output, report)
                raise SystemExit(f'F6_BITPLANE_COUNTEREXAMPLE {target_x}')
            if (target_x + 1) % 64 == 0:
                print('F6_BITPLANE_REPLAY_PROGRESS', target_x + 1, flush=True)
    finally:
        context.close()
    report['status'] = 'PASS'
    save(args.output, report)
    print('F6_BITPLANE_REPLAY_PASS 512', flush=True)


if __name__ == '__main__':
    main()
