"""Replay every frozen isolated-manifest arm without promoting local timings."""
import argparse
import json
from pathlib import Path
import subprocess


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    assert manifest['schema'] == 1 and manifest['cases'] and manifest['pair_fields']
    assert args.output.is_absolute() and not args.output.exists()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = dict(status='RUNNING', manifest=str(args.manifest.resolve()),
                  source_commit=manifest['build']['source_commit'],
                  rows=[], qualified_speedup=None)
    save(args.output, report)
    for index, case in enumerate(manifest['cases']):
        pair = {}
        order = ('reference', 'candidate') if index % 2 == 0 else ('candidate', 'reference')
        for arm in order:
            command = case[arm]
            try:
                done = subprocess.run(command, cwd=manifest['workdir'], text=True,
                                      capture_output=True, timeout=manifest['timeout_s'])
                execution = 'completed' if done.returncode == 0 else 'process-failure'
                output, error, exit_code = done.stdout, done.stderr, done.returncode
            except subprocess.TimeoutExpired as failure:
                execution, exit_code = 'timeout', None
                output = failure.stdout.decode(errors='replace') if isinstance(failure.stdout, bytes) else (failure.stdout or '')
                error = failure.stderr.decode(errors='replace') if isinstance(failure.stderr, bytes) else (failure.stderr or '')
            fields = {}
            if execution == 'completed':
                try:
                    fields = dict(token.split('=', 1) for token in output.split())
                    assert fields['verified'] == '1' and fields['status'] == 'solved'
                    assert float(fields['online_ms']) > 0
                except (AssertionError, KeyError, ValueError):
                    execution = 'invalid-output'
            row = dict(case=case['id'], arm=arm, execution=execution,
                       exit_code=exit_code, stdout=output, stderr=error, fields=fields)
            report['rows'].append(row)
            save(args.output, report)
            if execution == 'completed':
                pair[arm] = fields
        if len(pair) != 2 or any(pair['reference'][field] != pair['candidate'][field]
                                 for field in manifest['pair_fields']):
            report['status'] = 'INCOMPLETE'
            save(args.output, report)
            raise SystemExit(1)
    report['status'] = 'PASS'
    save(args.output, report)
    print('ISOLATED_MANIFEST_SMOKE_PASS', len(report['rows']), flush=True)


if __name__ == '__main__':
    main()
