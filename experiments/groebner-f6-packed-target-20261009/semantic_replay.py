"""Replay all 512 frozen targets with directly packed ANF coefficients."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from packed_query import HERE, PackedContext
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
    for path in HERE.glob('*.py'):
        assert path.read_bytes() == subprocess.check_output(
            ['git', 'show', 'HEAD:' + str(path.relative_to(root))], cwd=root)
    receipt = json.loads((HERE / 'build/receipt.json').read_text())
    reference_path = HERE.parent / 'groebner-f6-packed-20261009/evidence/semantic.json'
    reference = json.loads(reference_path.read_text())
    assert reference['status'] == 'PASS' and len(reference['rows']) == 512
    context = PackedContext(fixture(9, 4, 3, 1))
    report = dict(schema='f6-packed-target-512-replay/1', status='RUNNING',
                  source_commit=receipt['source_commit'], build=receipt,
                  reference_sha256=sha(reference_path), setup_ns=context.setup_ns,
                  rows=[], timing_eligible=False, qualified_speedup=None)
    save(args.output, report)
    try:
        for target_x in range(512):
            try:
                result = {arm: context.run(target_x, arm)
                          for arm in ('compact', 'affine', 'packed')}
                frozen = reference['rows'][target_x]
                keys = ('status', 'assignment', 'point_verified', 'equation_verified')
                match = all(value[key] == frozen[key]
                            for value in result.values() for key in keys)
                row = dict(target_x=target_x, execution='completed', match=match,
                           results=result)
            except Exception as error:
                row = dict(target_x=target_x, execution='failure', match=False,
                           error=repr(error))
            report['rows'].append(row)
            save(args.output, report)
            if not row['match']:
                report['status'] = 'COUNTEREXAMPLE'
                save(args.output, report)
                raise SystemExit(f'F6_PACKED_TARGET_COUNTEREXAMPLE {target_x}')
            if (target_x + 1) % 64 == 0:
                print('F6_PACKED_TARGET_REPLAY_PROGRESS', target_x + 1, flush=True)
    finally:
        context.close()
    report['status'] = 'PASS'
    save(args.output, report)
    print('F6_PACKED_TARGET_REPLAY_PASS 512', flush=True)


if __name__ == '__main__':
    main()
