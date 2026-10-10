"""Frozen complete queries with raw failures, owned proofs and phase accounting."""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

from early_query import HERE, Query

spec = importlib.util.spec_from_file_location('leased_context112', HERE.parent/'round111/panel.py')
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
sha, save, plan = previous.sha, previous.save, previous.plan


def worker(args):
    previous.Query = lambda **kwargs: Query(early_mode=args.early_mode, **kwargs)
    context = previous.Context(args.case, args.sanitized)
    try:
        row = context.run(args.case, 'matrix-block4')
    finally:
        for layout in context.layouts.values(): layout.close()
    result = row['result']
    if 'proof' in result:
        owned = result.pop('proof')
        path = args.output.with_suffix('.gbp')
        path.write_bytes(owned.serialized())
        result['proof_artifact'] = dict(path=path.name, sha256=sha(path),
            bytes=path.stat().st_size, nodes=owned.nodes, outputs=owned.outputs)
    row.update(name=args.case, sanitized=args.sanitized, early_mode=args.early_mode,
        fixture=context.cases[args.case], timing_eligible=False, qualified_speedup=None)
    save(args.output, row)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--case')
    parser.add_argument('--sanitized', action='store_true')
    parser.add_argument('--early-mode', type=int, choices=(0, 1), default=1)
    args = parser.parse_args()
    if args.case:
        worker(args)
        return
    args.output.mkdir(parents=True, exist_ok=False)
    report = dict(status='RUNNING', source_commit=subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=HERE, text=True).strip(),
        scripts={p.name: sha(p) for p in HERE.glob('*.py')}, plan=plan(),
        build=json.loads((HERE/'build/receipt.json').read_text()), rows=[],
        timing_eligible=False, qualified_speedup=None)
    save(args.output/'report.json', report)
    for sanitized in (False, True):
        for mode in (0, 1):
            for name in plan()['cases']:
                target = args.output/(name+'-early'+str(mode)+('-ubsan' if sanitized else '')+'.json')
                command = [sys.executable, str(HERE/'panel.py'), '--case', name,
                           '--early-mode', str(mode), '--output', str(target)]
                if sanitized: command.append('--sanitized')
                with target.with_suffix('.log').open('w') as log:
                    try:
                        done = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=60)
                        row = dict(name=name, early_mode=mode, sanitized=sanitized, exit_code=done.returncode,
                            execution='completed' if done.returncode == 0 else 'process-failure')
                    except subprocess.TimeoutExpired:
                        row = dict(name=name, early_mode=mode, sanitized=sanitized, execution='timeout')
                if row['execution'] == 'completed':
                    row.update(result=target.name, sha256=sha(target))
                report['rows'].append(row)
                save(args.output/'report.json', report)
                print(name, mode, sanitized, row['execution'], flush=True)
    report['status'] = 'RECORDED_PENDING_AUDIT'
    save(args.output/'report.json', report)


if __name__ == '__main__':
    main()
