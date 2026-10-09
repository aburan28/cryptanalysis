"""Repeat source-frozen continuation phase measurements on audited queries."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys

HERE = Path(__file__).resolve().parent
CASES = [f'pdp-12-seed-{seed}' for seed in range(1, 6)]
PHASES = ('preparation_ns', 'f4_ns', 'packing_ns', 'composition_ns',
          'finalization_ns', 'total_ns')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference-report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reps', type=int, default=5)
    parser.add_argument('--timeout', type=int, default=90)
    args = parser.parse_args()
    assert args.reps > 0 and args.timeout > 0
    root = HERE.parents[2]
    assert HERE.joinpath('phase_profile.py').read_bytes() == subprocess.check_output(
        ['git', 'show', 'HEAD:'+str((HERE/'phase_profile.py').relative_to(root))], cwd=root)
    baseline = json.loads(args.reference_report.read_text())
    assert baseline['status'] == 'RECORDED_PENDING_AUDIT'
    references = {}
    for entry in baseline['rows']:
        if entry['name'] in CASES and entry['early_mode'] == 1 and not entry['sanitized']:
            source = args.reference_report.parent/entry['result']
            assert sha(source) == entry['sha256']
            references[entry['name']] = source
    assert set(references) == set(CASES)
    args.output.mkdir(parents=True, exist_ok=False)
    report = dict(status='RUNNING',
        source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
        source_sha256=sha(HERE/'phase_profile.py'),
        reference_report=str(args.reference_report),
        reference_sha256=sha(args.reference_report),
        build=json.loads((HERE/'build/receipt.json').read_text()),
        repetitions=args.reps, rows=[], summary={},
        timing_eligible=False, qualified_speedup=None)
    save(args.output/'report.json', report)
    for repetition in range(-1, args.reps):
        for name in (CASES if repetition % 2 == 0 else list(reversed(CASES))):
            tag = name+('-warmup' if repetition < 0 else '-r'+str(repetition+1))
            target = args.output/(tag+'.json')
            command = [sys.executable, str(HERE/'panel.py'), '--case', name,
                       '--reference', str(references[name]), '--output', str(target)]
            with (args.output/(tag+'.log')).open('w') as log:
                try:
                    done = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                          timeout=args.timeout)
                    execution = 'completed' if done.returncode == 0 else 'process-failure'
                    exit_code = done.returncode
                except subprocess.TimeoutExpired:
                    execution, exit_code = 'timeout', None
            row = dict(case=name, repetition=repetition+1, warmup=repetition < 0,
                       execution=execution, exit_code=exit_code, log=tag+'.log')
            if execution == 'completed':
                data = json.loads(target.read_text())
                phase = next(a['native_phases'] for a in data['result']['attempts']
                             if a['kind'] == 'seeded-f4')
                row.update(result=target.name, sha256=sha(target), phase=phase,
                           proof_sha256=data['reference_match']['proof_sha256'])
            report['rows'].append(row)
            save(args.output/'report.json', report)
            print(tag, execution, flush=True)
    if all(row['execution'] == 'completed' for row in report['rows']):
        for name in CASES:
            rows = [r for r in report['rows'] if r['case'] == name and not r['warmup']]
            medians = {field: statistics.median(r['phase'][field]/1e6 for r in rows)
                       for field in PHASES}
            mads = {field: statistics.median(abs(r['phase'][field]/1e6-medians[field])
                    for r in rows) for field in PHASES}
            report['summary'][name] = dict(n=len(rows), median_ms=medians,
                mad_ms=mads, median_f4_fraction=statistics.median(
                    r['phase']['f4_ns']/r['phase']['total_ns'] for r in rows),
                proof_sha256=rows[0]['proof_sha256'])
        report['status'] = 'PASS'
    else:
        report['status'] = 'INCOMPLETE'
    save(args.output/'report.json', report)
    print('PHASE_PROFILE_'+report['status'], len(report['rows']), flush=True)
    if report['status'] != 'PASS':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
