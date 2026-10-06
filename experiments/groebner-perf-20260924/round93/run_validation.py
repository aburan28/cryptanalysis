"""Fresh portable correctness evidence, with one local heavy-work exclusion lock."""
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

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--diagnostics', action='store_true')
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    lock_path = Path(os.environ.get('GROEBNER_HEAVY_LOCK', '/private/tmp/cryptanalysis-overlap-evidence-20261003/local-heavy.lock')
                     if sys.platform=='darwin' else '/tmp/groebner-local-heavy.lock')
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    record = dict(status='RUNNING', started=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  steps=[], timing_eligible=False, qualified_speedup=None,
                  source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                  source_tree=subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], text=True).strip(),
                  ci={name:os.environ.get(name) for name in ('GITHUB_SHA', 'GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT', 'GITHUB_EVENT_NAME', 'RUNNER_OS', 'RUNNER_ARCH')})
    def save():
        (out/'validation.json').write_text(json.dumps(record, indent=2)+'\n')
    save()
    with lock_path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        from build import source_paths
        for source in source_paths():
            relative = str(source.resolve().relative_to(HERE.parents[2]))
            frozen = subprocess.check_output(['git', 'show', 'HEAD:'+relative])
            if frozen != source.read_bytes():
                record.update(status='FAIL', reason='uncommitted source: '+relative)
                save()
                raise SystemExit(record['reason'])
        def run(label, command):
            with (out/(label+'.log')).open('w') as log:
                p = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
            record['steps'].append(dict(label=label, command=command, exit_code=p.returncode))
            if p.returncode:
                record['status']='FAIL'
            save()
            if p.returncode:
                raise SystemExit(p.returncode)
            print('PASS', label, flush=True)
        run('build', [sys.executable, str(HERE/'build.py')])
        build = json.loads((HERE/'build/receipt.json').read_text())
        (out/'build-receipt.json').write_text(json.dumps(build, indent=2)+'\n')
        for name, digest in build['sources'].items():
            path = HERE.parent.parent/name
            assert hashlib.sha256(path.read_bytes()).hexdigest()==digest
            destination = out/'sources'/str(path.resolve().relative_to(HERE.parents[2]))
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
        for p in (HERE/'build').iterdir():
            if p.is_file() and p.suffix in ('.cpp', '.inc', '.py', '.so', '.dylib'):
                (out/'native').mkdir(exist_ok=True)
                shutil.copyfile(p, out/'native'/p.name)
        run('unit-tests', [sys.executable, '-m', 'unittest', 'discover', '-s', str(HERE), '-p', 'test_*.py', '-v'])
        run('controls', [sys.executable, str(HERE/'panel.py'), '--controls', '--output', str(out/'controls')])
        run('control-audit', [sys.executable, str(HERE/'audit.py'), str(out/'controls/report.json'), '--output', str(out/'control-audit.json')])
        run('artifact-controls', [sys.executable, str(HERE/'test_artifact.py'), str(out/'controls/report.json'), str(out/'artifact-controls.json')])
        if args.diagnostics:
            run('diagnostics', [sys.executable, str(HERE/'panel.py'), '--output', str(out/'diagnostics')])
            run('diagnostic-audit', [sys.executable, str(HERE/'audit.py'), str(out/'diagnostics/report.json'), '--output', str(out/'diagnostic-audit.json')])
        record.update(status='PASS', finished=datetime.datetime.now(datetime.timezone.utc).isoformat())
        save()

if __name__ == '__main__':
    main()
