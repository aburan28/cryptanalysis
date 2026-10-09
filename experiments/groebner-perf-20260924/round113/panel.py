"""Pair instrumented continuation with independently audited frozen queries."""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

from phased_query import HERE, Query

spec = importlib.util.spec_from_file_location('leased_context113', HERE.parent/'round111/panel.py')
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
sha, save = previous.sha, previous.save

CASES = [f'pdp-12-seed-{seed}' for seed in range(1, 6)]


def assert_reference(row, baseline):
    def counters(value):
        if value is None:
            return None
        return {key: item for key, item in value.items() if not key.endswith('_seconds')}

    actual, expected = row['result'], baseline['result']
    for key in ('status', 'verified', 'complete', 'basis', 'work', 'check_work',
                'assignment', 'curve_replay', 'reference_equations_and_curve_replay'):
        assert actual.get(key) == expected.get(key), key
    assert actual['proof_artifact']['sha256'] == expected['proof_artifact']['sha256']
    assert actual['proof_artifact']['nodes'] == expected['proof_artifact']['nodes']
    assert actual['proof_artifact']['outputs'] == expected['proof_artifact']['outputs']
    assert len(actual['attempts']) == len(expected['attempts'])
    for a, b in zip(actual['attempts'], expected['attempts']):
        for key in ('kind', 'verified', 'composition'):
            assert a.get(key) == b.get(key), (a['kind'], key)
        for key in ('stats', 'producer'):
            assert counters(a.get(key)) == counters(b.get(key)), (a['kind'], key)
        if a['kind'] == 'seeded-f4':
            phase = a['native_phases']
            assert phase['completed'] == 1 and phase['stage_at_exit'] == 4
            assert phase['f4_ns'] > 0 and phase['composition_ns'] > 0
            assert phase['total_ns'] == sum(phase[key] for key in (
                'preparation_ns', 'f4_ns', 'packing_ns', 'composition_ns', 'finalization_ns'))
    return dict(proof_sha256=actual['proof_artifact']['sha256'],
        original_equations_and_curve_verified=actual['reference_equations_and_curve_replay'])


def worker(args):
    previous.Query = lambda **kwargs: Query(early_mode=1, **kwargs)
    context = previous.Context(args.case, args.sanitized)
    try:
        row = context.run(args.case, 'matrix-block4')
    finally:
        for layout in context.layouts.values():
            layout.close()
    result = row['result']
    if 'proof' in result:
        owned = result.pop('proof')
        path = args.output.with_suffix('.gbp')
        path.write_bytes(owned.serialized())
        result['proof_artifact'] = dict(path=path.name, sha256=sha(path),
            bytes=path.stat().st_size, nodes=owned.nodes, outputs=owned.outputs)
    row.update(name=args.case, sanitized=args.sanitized, early_mode=1,
        fixture=context.cases[args.case], timing_eligible=False, qualified_speedup=None)
    baseline = json.loads(args.reference.read_text())
    row['reference_match'] = assert_reference(row, baseline)
    save(args.output, row)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reference-report', type=Path)
    parser.add_argument('--case', choices=CASES)
    parser.add_argument('--reference', type=Path)
    parser.add_argument('--sanitized', action='store_true')
    args = parser.parse_args()
    if args.case:
        assert args.reference is not None
        worker(args)
        return
    assert args.reference_report is not None
    args.output.mkdir(parents=True, exist_ok=False)
    reference = json.loads(args.reference_report.read_text())
    assert reference['status'] in ('RECORDED_PENDING_AUDIT', 'PASS')
    source = args.reference_report.parent
    report = dict(status='RUNNING',
        source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=HERE, text=True).strip(),
        build=json.loads((HERE/'build/receipt.json').read_text()),
        reference_report=str(args.reference_report), reference_sha256=sha(args.reference_report),
        rows=[], timing_eligible=False, qualified_speedup=None)
    save(args.output/'report.json', report)
    for sanitized in (False, True):
        for name in CASES:
            ref_name = name+'-early1'+('-ubsan' if sanitized else '')+'.json'
            target = args.output/ref_name
            command = [sys.executable, str(HERE/'panel.py'), '--case', name,
                '--reference', str(source/ref_name), '--output', str(target)]
            if sanitized:
                command.append('--sanitized')
            with target.with_suffix('.log').open('w') as log:
                try:
                    done = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=60)
                    row = dict(name=name, sanitized=sanitized, exit_code=done.returncode,
                        execution='completed' if done.returncode == 0 else 'process-failure')
                except subprocess.TimeoutExpired:
                    row = dict(name=name, sanitized=sanitized, execution='timeout')
            if row['execution'] == 'completed':
                row.update(result=target.name, sha256=sha(target))
            report['rows'].append(row)
            save(args.output/'report.json', report)
            print(name, sanitized, row['execution'], flush=True)
    report['status'] = 'PASS' if all(row['execution'] == 'completed' for row in report['rows']) else 'INCOMPLETE'
    save(args.output/'report.json', report)
    print('PHASE_PANEL_'+report['status'], len(report['rows']), flush=True)


if __name__ == '__main__':
    main()
