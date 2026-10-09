"""Repeat source-frozen inner F4 measurements on audited queries."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys

HERE = Path(__file__).resolve().parent
CASES = [f'pdp-12-seed-{seed}' for seed in range(1, 6)]
PHASES = ('initial_ns', 'pairs_ns', 'matrix_ns', 'candidate_ns', 'final_ns',
          'compute_ns', 'compact_ns', 'symbolic_ns', 'column_ns', 'packed_ns')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference-root', type=Path, required=True)
    parser.add_argument('--reference-report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reps', type=int, default=5)
    parser.add_argument('--timeout', type=int, default=90)
    args = parser.parse_args()
    assert args.reps > 0 and args.timeout > 0
    root = HERE.parents[2]
    for path in HERE.glob('*.py'):
        assert path.read_bytes() == subprocess.check_output(
            ['git', 'show', 'HEAD:'+str(path.relative_to(root))], cwd=root)
    baseline = json.loads(args.reference_report.read_text())
    assert baseline['status'] == 'RECORDED_PENDING_AUDIT'
    audit_path = args.reference_report.parent.parent/'audit.json'
    audit = json.loads(audit_path.read_text())
    assert audit['status'] == 'PASS' and audit['rows'] == 52
    assert audit['native_binaries_loaded'] is False
    references = {}
    for entry in baseline['rows']:
        if entry['name'] in CASES and entry['early_mode'] == 1 and not entry['sanitized']:
            source = args.reference_report.parent/entry['result']
            assert sha(source) == entry['sha256']
            references[entry['name']] = source
    assert set(references) == set(CASES)
    build = json.loads((HERE/'build/receipt.json').read_text())
    for name, digest in build['sources'].items():
        assert sha(HERE/name) == digest, name
    for name, digest in build['binaries'].items():
        assert sha(HERE/'build'/name) == digest, name
    assert sha(HERE/'build/engine.inc') == build['generated_engine_sha256']
    assert sha(HERE/'build/seeded_inner.cpp') == build['generated_seeded_sha256']
    args.output.mkdir(parents=True, exist_ok=False)
    report = dict(status='RUNNING',
        source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
        source_sha256=sha(HERE/'profile.py'), reference_root=str(args.reference_root.resolve()),
        reference_report=str(args.reference_report),
        reference_sha256=sha(args.reference_report),
        reference_audit_sha256=sha(audit_path), build=build,
        repetitions=args.reps, rows=[], summary={},
        timing_eligible=False, qualified_speedup=None)
    save(args.output/'report.json', report)
    environment = os.environ.copy()
    environment['GROEBNER_F4_REFERENCE_ROOT'] = str(args.reference_root.resolve())
    lock = Path('/private/tmp/cryptanalysis-overlap-evidence-20261003/local-heavy.lock'
                if sys.platform == 'darwin' else '/tmp/groebner-local-heavy.lock')
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open('a') as guard:
      fcntl.flock(guard, fcntl.LOCK_EX)
      for repetition in range(-1, args.reps):
        for name in (CASES if repetition % 2 == 0 else list(reversed(CASES))):
            tag = name+('-warmup' if repetition < 0 else '-r'+str(repetition+1))
            target = args.output/(tag+'.json')
            command = [sys.executable, str(HERE/'panel.py'), '--case', name,
                       '--reference', str(references[name]), '--output', str(target)]
            with (args.output/(tag+'.log')).open('w') as log:
                try:
                    done = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                          timeout=args.timeout, env=environment)
                    execution = 'completed' if done.returncode == 0 else 'process-failure'
                    exit_code = done.returncode
                except subprocess.TimeoutExpired:
                    execution, exit_code = 'timeout', None
            row = dict(case=name, repetition=repetition+1, warmup=repetition < 0,
                       execution=execution, exit_code=exit_code, log=tag+'.log')
            if execution == 'completed':
                data = json.loads(target.read_text())
                attempt = next(a for a in data['result']['attempts']
                               if a['kind'] == 'seeded-f4')
                row.update(result=target.name, sha256=sha(target), phase=attempt['f4_inner'],
                           native_phase=attempt['native_phases'], query_ns=data['wall_ns'],
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
                mad_ms=mads, median_matrix_fraction=statistics.median(
                    r['phase']['matrix_ns']/r['phase']['compute_ns'] for r in rows),
                median_initial_fraction=statistics.median(
                    r['phase']['initial_ns']/r['phase']['compute_ns'] for r in rows),
                median_packed_fraction=statistics.median(
                    r['phase']['packed_ns']/r['phase']['compute_ns'] for r in rows),
                proof_sha256=rows[0]['proof_sha256'])
        report['status'] = 'PASS'
    else:
        report['status'] = 'INCOMPLETE'
    save(args.output/'report.json', report)
    print('F4_INNER_PROFILE_'+report['status'], len(report['rows']), flush=True)
    if report['status'] != 'PASS':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
