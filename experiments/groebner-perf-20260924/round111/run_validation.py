"""Fresh portable build, query boundary tests and a native-free panel audit."""
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
ROOT = HERE.parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reuse-build', action='store_true', help='Local source-matched build reuse, recorded explicitly')
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    record = dict(status='RUNNING', source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=HERE, text=True).strip(),
        source_tree=subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=HERE, text=True).strip(),
        ci={k: os.environ.get(k) for k in ('GITHUB_SHA', 'GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT', 'GITHUB_EVENT_NAME', 'RUNNER_OS', 'RUNNER_ARCH')},
        started=datetime.datetime.now(datetime.timezone.utc).isoformat(), steps=[], reused_build=args.reuse_build,
        timing_eligible=False, qualified_speedup=None)
    def save():
        (out/'validation.json').write_text(json.dumps(record, indent=2)+'\n')
    def run(label, command):
        with (out/(label+'.log')).open('w') as log:
            done = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        record['steps'].append(dict(label=label, command=command, exit_code=done.returncode))
        if done.returncode: record['status'] = 'FAIL'
        save()
        if done.returncode: raise SystemExit(done.returncode)
        print('PASS', label, flush=True)
    save()
    lock = Path('/private/tmp/cryptanalysis-overlap-evidence-20261003/local-heavy.lock' if sys.platform == 'darwin' else '/tmp/groebner-local-heavy.lock')
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open('a') as guard:
        fcntl.flock(guard, fcntl.LOCK_EX)
        for path in HERE.glob('*.py'):
            assert path.read_bytes() == subprocess.check_output(['git', 'show', 'HEAD:'+str(path.relative_to(ROOT))], cwd=ROOT)
        native = HERE.parent/'round110'
        if not args.reuse_build:
            run('build', [sys.executable, str(native/'build.py')])
        build = json.loads((native/'build/receipt.json').read_text())
        (out/'build-receipt.json').write_text(json.dumps(build, indent=2)+'\n')
        groups = [(native/name, out/'native-sources'/name, value) for name, value in build['sources'].items()]
        groups += [(native/'build'/name, out/'native-binaries'/name, value) for name, value in build['binaries'].items()]
        for group in ('sources', 'binaries', 'generated', 'resources'):
            groups += [((ROOT/'experiments'/name if group == 'sources' else HERE.parent/'round108/build'/name),
                        out/'reference'/group/name, value) for name, value in build['reference'][group].items()]
        groups += [(p, out/'sources'/p.name, hashlib.sha256(p.read_bytes()).hexdigest()) for p in HERE.glob('*.py')]
        for source, target, value in groups:
            assert hashlib.sha256(source.read_bytes()).hexdigest() == value
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        run('unit-tests', [sys.executable, '-m', 'unittest', 'discover', '-s', str(HERE), '-v'])
        run('panel', [sys.executable, str(HERE/'panel.py'), '--output', str(out/'panel')])
        run('audit', [sys.executable, str(HERE/'audit.py'), str(out/'panel/report.json'), '--output', str(out/'audit.json')])
        run('artifact-controls', [sys.executable, str(HERE/'test_artifact.py'), str(out/'panel/report.json'), str(out/'artifact-controls.json')])
    record.update(status='PASS', finished=datetime.datetime.now(datetime.timezone.utc).isoformat())
    save()


if __name__ == '__main__':
    main()
