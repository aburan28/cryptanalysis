"""Exploratory paired API profiling; no isolated speedup is inferred.

The reference controller materializes diagnostic continuation/proof graphs. The
leased API instead returns owned binary proof bytes and does two curve replays.
Both solve fresh coefficients and independently certify the original equations.
"""
import argparse
import fcntl
import importlib.util
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time
from types import SimpleNamespace

from panel import Context, HERE, plan, save, sha

ORDERS = [('diagnostic', 'leased'), ('leased', 'diagnostic'),
          ('leased', 'diagnostic'), ('diagnostic', 'leased')]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def worker(args):
    reference = load('diagnostic110', HERE.parent/'round110/discover.py')
    audit = load('profile_audit111', HERE/'audit.py')
    _, frozen = audit.frozen()
    expected = frozen[args.case, False]
    baseline_ctx, native = reference.Context(sanitizer=False), reference.Native(False)
    ctx = Context(args.case)
    reference.Context = lambda **kwargs: baseline_ctx
    reference.Native = lambda *args: native
    saved = []
    reference.save = lambda path, value: saved.append(value)
    result = dict(name=args.case, orders=ORDERS, rows=[], timing_eligible=False, qualified_speedup=None)
    args.output.mkdir(parents=True, exist_ok=False)
    try:
        for repetition, order in [(-1, ('diagnostic', 'leased'))]+list(enumerate(ORDERS)):
            for arm in order:
                start = time.perf_counter_ns()
                if arm == 'diagnostic':
                    reference.worker(SimpleNamespace(case=args.case, sanitized=False, output=None))
                    row = saved.pop()
                else:
                    row = ctx.run(args.case, 'matrix-block4')
                wall = time.perf_counter_ns()-start
                # Every original record is retained; certification below is
                # outside the timed query and never substitutes a selected rerun.
                stem = arm+'-'+str(repetition)
                if arm == 'leased':
                    output = row['result']
                    if 'proof' in output:
                        owned = output.pop('proof')
                        path = args.output/(stem+'.gbp')
                        path.write_bytes(owned.serialized())
                        output['proof_artifact'] = dict(path=path.name, sha256=sha(path),
                            bytes=path.stat().st_size, nodes=owned.nodes, outputs=owned.outputs)
                    row.update(name=args.case, sanitized=False, fixture=ctx.cases[args.case],
                               timing_eligible=False, qualified_speedup=None)
                path = args.output/(stem+'.json')
                save(path, row)
                entry = dict(arm=arm, repetition=repetition, warmup=repetition < 0,
                    wall_ns=wall, result=path.name, sha256=sha(path), status='RECORDED')
                result['rows'].append(entry)
                save(args.output/'report.json', result)
                if arm == 'diagnostic':
                    assert row == expected
                else:
                    audit.one(row, expected, args.output)
                    entry['phases'] = row['result']['phases']
                entry['status'] = 'PASS'
                save(args.output/'report.json', result)
    finally:
        for context in (ctx, baseline_ctx):
            for layout in context.layouts.values(): layout.close()
    result['summary'] = {}
    for arm in ('diagnostic', 'leased'):
        values = [r['wall_ns']/1e6 for r in result['rows'] if r['arm'] == arm and not r['warmup']]
        median = statistics.median(values)
        summary = dict(n=len(values), median_ms=median,
                       mad_ms=statistics.median(abs(v-median) for v in values))
        if arm == 'leased':
            summary['phase_median_ms'] = {name: statistics.median(
                r['phases'][name]/1e6 for r in result['rows'] if r['arm'] == arm and not r['warmup'])
                for name in result['rows'][-1]['phases']}
        result['summary'][arm] = summary
    result['status'] = 'PASS'
    save(args.output/'report.json', result)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--case')
    args = parser.parse_args()
    if args.case:
        worker(args)
        return
    args.output.mkdir(parents=True, exist_ok=False)
    report = dict(status='RUNNING', source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=HERE, text=True).strip(),
        scripts={p.name: sha(p) for p in HERE.glob('*.py')},
        native_build=json.loads((HERE.parent/'round110/build/receipt.json').read_text()),
        orders=ORDERS, cases=plan()['cases'], rows=[], timing_eligible=False, qualified_speedup=None,
        scope='API comparison; diagnostic graph export versus owned binary transport; not an algorithmic or isolated speedup')
    save(args.output/'report.json', report)
    lock = Path('/private/tmp/cryptanalysis-overlap-evidence-20261003/local-heavy.lock' if sys.platform == 'darwin' else '/tmp/groebner-local-heavy.lock')
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open('a') as guard:
        fcntl.flock(guard, fcntl.LOCK_EX)
        for path in HERE.glob('*.py'):
            assert path.read_bytes() == subprocess.check_output(['git', 'show', 'HEAD:'+str(path.relative_to(HERE.parents[2]))], cwd=HERE)
        for name, value in report['native_build']['binaries'].items():
            assert sha(HERE.parent/'round110/build'/name) == value
        for group in ('binaries', 'generated', 'resources'):
            for name, value in report['native_build']['reference'][group].items():
                assert sha(HERE.parent/'round108/build'/name) == value
        for name in report['cases']:
            target = args.output/name
            command = [sys.executable, str(HERE/'profile.py'), '--case', name, '--output', str(target)]
            with (args.output/(name+'.log')).open('w') as log:
                try:
                    done = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=120)
                    row = dict(name=name, exit_code=done.returncode, execution='completed' if done.returncode == 0 else 'process-failure')
                except subprocess.TimeoutExpired:
                    row = dict(name=name, execution='timeout')
            if (target/'report.json').exists():
                row['report_sha256'] = sha(target/'report.json')
            report['rows'].append(row)
            save(args.output/'report.json', report)
            print(name, row['execution'], flush=True)
    report['status'] = 'PASS' if all(r['execution'] == 'completed' for r in report['rows']) else 'FAIL'
    save(args.output/'report.json', report)
    if report['status'] != 'PASS': raise SystemExit(1)


if __name__ == '__main__':
    main()
