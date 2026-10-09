"""Paired early/late compression on the same leased API and complete-query boundary."""
import argparse
import fcntl
import importlib.util
import json
from pathlib import Path
import statistics
import subprocess
import sys

from early_query import HERE, Query


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


panel = load('panel112_profile', HERE/'panel.py')
audit = load('audit112_profile', HERE/'audit.py')
ORDERS = [[0, 1], [1, 0], [1, 0], [0, 1]]


def stable(value):
    if isinstance(value, dict):
        return {k: stable(v) for k, v in value.items()
                if not k.endswith('seconds') and k not in ('wall_ns', 'phases', 'proof_artifact')}
    if isinstance(value, list): return [stable(v) for v in value]
    return value


def worker(args):
    baseline_report = json.loads(args.reference_report.read_text())
    expected = {}
    for r in baseline_report['rows']:
        if r['name'] == args.case and not r['sanitized']:
            path = args.reference_report.parent/r['result']
            assert panel.sha(path) == r['sha256']
            expected[r['early_mode']] = json.loads(path.read_text())
    contexts = {}
    for mode in (0, 1):
        panel.previous.Query = lambda mode=mode, **kwargs: Query(early_mode=mode, **kwargs)
        contexts[mode] = panel.previous.Context(args.case)
    _, frozen = audit.reference_audit.frozen()
    args.output.mkdir(parents=True, exist_ok=False)
    result = dict(name=args.case, rows=[], orders=ORDERS, timing_eligible=False, qualified_speedup=None)
    try:
        for repetition, order in [(-1, [0, 1])]+list(enumerate(ORDERS)):
            for mode in order:
                row = contexts[mode].run(args.case, 'matrix-block4')
                row.update(name=args.case, sanitized=False, early_mode=mode,
                    fixture=contexts[mode].cases[args.case], timing_eligible=False, qualified_speedup=None)
                query = row['result']
                stem = str(mode)+'-'+str(repetition)
                if 'proof' in query:
                    owned = query.pop('proof')
                    path = args.output/(stem+'.gbp')
                    path.write_bytes(owned.serialized())
                    query['proof_artifact'] = dict(path=path.name, sha256=panel.sha(path),
                        bytes=path.stat().st_size, nodes=owned.nodes, outputs=owned.outputs)
                path = args.output/(stem+'.json')
                panel.save(path, row)
                item = dict(early_mode=mode, repetition=repetition, warmup=repetition < 0,
                    wall_ns=row['wall_ns'], phases=query['phases'], result=path.name,
                    sha256=panel.sha(path), status='RECORDED')
                result['rows'].append(item)
                panel.save(args.output/'report.json', result)
                assert stable(row) == stable(expected[mode])
                if 'proof_artifact' in query:
                    assert query['proof_artifact']['sha256'] == expected[mode]['result']['proof_artifact']['sha256']
                audit.one(row, frozen[args.case, False], args.output)
                item['status'] = 'PASS'
                panel.save(args.output/'report.json', result)
    finally:
        for context in contexts.values():
            for layout in context.layouts.values(): layout.close()
    result['summary'] = {}
    for mode in (0, 1):
        rows = [r for r in result['rows'] if r['early_mode'] == mode and not r['warmup']]
        values = [r['wall_ns']/1e6 for r in rows]
        median = statistics.median(values)
        result['summary'][str(mode)] = dict(n=len(values), median_ms=median,
            mad_ms=statistics.median(abs(v-median) for v in values),
            phase_median_ms={key: statistics.median(r['phases'][key]/1e6 for r in rows)
                             for key in rows[0]['phases']})
    result['status'] = 'PASS'
    panel.save(args.output/'report.json', result)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reference-report', type=Path, required=True)
    parser.add_argument('--case')
    args = parser.parse_args()
    if args.case:
        worker(args)
        return
    args.output.mkdir(parents=True, exist_ok=False)
    report = dict(status='RUNNING', source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=HERE, text=True).strip(),
        scripts={p.name: panel.sha(p) for p in HERE.glob('*.py')},
        reference_report_sha256=panel.sha(args.reference_report), reference_report=str(args.reference_report),
        build=json.loads((HERE/'build/receipt.json').read_text()), orders=ORDERS,
        cases=panel.plan()['cases'], rows=[], timing_eligible=False, qualified_speedup=None)
    panel.save(args.output/'report.json', report)
    lock = Path('/private/tmp/cryptanalysis-overlap-evidence-20261003/local-heavy.lock' if sys.platform == 'darwin' else '/tmp/groebner-local-heavy.lock')
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open('a') as guard:
        fcntl.flock(guard, fcntl.LOCK_EX)
        for p in HERE.glob('*.py'):
            assert p.read_bytes() == subprocess.check_output(['git', 'show', 'HEAD:'+str(p.relative_to(HERE.parents[2]))], cwd=HERE)
        for name, value in report['build']['binaries'].items():
            assert panel.sha(HERE/'build'/name) == value
        for name in report['cases']:
            command = [sys.executable, str(HERE/'profile.py'), '--case', name,
                '--output', str(args.output/name), '--reference-report', str(args.reference_report)]
            with (args.output/(name+'.log')).open('w') as log:
                try:
                    done = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=180)
                    row = dict(name=name, exit_code=done.returncode, execution='completed' if done.returncode == 0 else 'process-failure')
                except subprocess.TimeoutExpired:
                    row = dict(name=name, execution='timeout')
            path = args.output/name/'report.json'
            if path.exists(): row['report_sha256'] = panel.sha(path)
            report['rows'].append(row)
            panel.save(args.output/'report.json', report)
            print(name, row['execution'], flush=True)
    report['status'] = 'PASS' if all(r['execution'] == 'completed' for r in report['rows']) else 'FAIL'
    panel.save(args.output/'report.json', report)
    if report['status'] != 'PASS': raise SystemExit(1)


if __name__ == '__main__':
    main()
