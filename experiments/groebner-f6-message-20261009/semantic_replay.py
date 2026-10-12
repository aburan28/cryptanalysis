"""Replay all 512 frozen abscissae through cached exact messages."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from message_query import HERE, MessageContext
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
    for name, digest in receipt['binaries'].items():
        assert sha(HERE / 'build' / name) == digest
    reference_path = HERE.parent / 'groebner-f6-packed-20261009/evidence/semantic.json'
    reference = json.loads(reference_path.read_text())
    assert reference['status'] == 'PASS' and len(reference['rows']) == 512
    context = MessageContext(fixture(9, 4, 3, 1))
    report = dict(schema='f6-message-512-target-replay/1', status='RUNNING',
                  source_commit=subprocess.check_output(
                      ['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
                  reference_sha256=sha(reference_path), setup_ns=context.setup_ns,
                  boundary_mask=context.boundary_mask,
                  message_setup=context.message.setup, rows=[],
                  timing_eligible=False, qualified_speedup=None)
    save(args.output, report)
    try:
        for target in range(512):
            try:
                result = context.run(target, 'message')
                frozen = reference['rows'][target]
                match = all((result['status'] == frozen['status'],
                             result['assignment'] == frozen['assignment'],
                             result['point_verified'] == frozen['point_verified'],
                             result['equation_verified'] == frozen['equation_verified']))
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
                print('F6_MESSAGE_COUNTEREXAMPLE', target, flush=True)
                raise SystemExit(1)
            if (target + 1) % 64 == 0:
                print('F6_MESSAGE_REPLAY_PROGRESS', target + 1, flush=True)
    finally:
        context.close()
    report['status'] = 'PASS'
    save(args.output, report)
    print('F6_MESSAGE_REPLAY_PASS 512', flush=True)


if __name__ == '__main__':
    main()
