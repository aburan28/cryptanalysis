"""Fresh native/reference builds, unit and frozen-query checks, independent audits."""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REFERENCE = HERE.parent/'round108'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    record = dict(status='RUNNING', source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=HERE, text=True).strip(),
        source_tree=subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=HERE, text=True).strip(),
        ci={k: os.environ.get(k) for k in ('GITHUB_SHA', 'GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT', 'GITHUB_EVENT_NAME', 'RUNNER_OS', 'RUNNER_ARCH')},
        started=datetime.datetime.now(datetime.timezone.utc).isoformat(), steps=[], timing_eligible=False, qualified_speedup=None)
    def save():
        (out/'validation.json').write_text(json.dumps(record, indent=2)+'\n')
    def run(label, command):
        with (out/(label+'.log')).open('w') as log:
            result = subprocess.run(command, cwd=HERE.parents[2], stdout=log, stderr=subprocess.STDOUT)
        record['steps'].append(dict(label=label, command=command, exit_code=result.returncode))
        if result.returncode: record['status'] = 'FAIL'
        save()
        if result.returncode: raise SystemExit(result.returncode)
        print('PASS', label, flush=True)
    save()
    lock = Path('/private/tmp/cryptanalysis-overlap-evidence-20261003/local-heavy.lock' if sys.platform == 'darwin' else '/tmp/groebner-local-heavy.lock')
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open('a') as guard:
        fcntl.flock(guard, fcntl.LOCK_EX)
        run('build', [sys.executable, str(HERE/'build.py')])
        build = json.loads((HERE/'build/receipt.json').read_text())
        (out/'build-receipt.json').write_text(json.dumps(build, indent=2)+'\n')
        for group in ('sources', 'binaries'):
            for name, digest in build[group].items():
                source = HERE/name if group == 'sources' else HERE/'build'/name
                assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
                target = out/group/name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
        for group in ('sources', 'binaries', 'generated', 'resources'):
            for name, digest in build['reference'][group].items():
                source = HERE.parent.parent/name if group == 'sources' else REFERENCE/'build'/name
                assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
                target = out/'reference'/group/name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
        run('unit-tests', [sys.executable, '-m', 'unittest', 'discover', '-s', str(HERE), '-v'])
    run('discovery', [sys.executable, str(HERE/'discover.py'), '--output', str(out/'discovery')])
    with lock.open('a') as guard:
        fcntl.flock(guard, fcntl.LOCK_EX)
        run('audit', [sys.executable, str(HERE/'audit_native.py'), str(out/'discovery/report.json'), '--output', str(out/'audit.json')])
        run('artifact-controls', [sys.executable, str(HERE/'test_artifact.py'), str(out/'discovery/report.json'), str(out/'artifact-controls.json')])
    record.update(status='PASS', finished=datetime.datetime.now(datetime.timezone.utc).isoformat())
    save()


if __name__ == '__main__':
    main()
