"""Fresh builds, exact-prefix unit tests, frozen panel and independent audit."""
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
    parser.add_argument('--reuse-reference', action='store_true')
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    record = dict(status='RUNNING', source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=HERE, text=True).strip(),
        source_tree=subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=HERE, text=True).strip(),
        ci={k: os.environ.get(k) for k in ('GITHUB_SHA', 'GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT', 'GITHUB_EVENT_NAME', 'RUNNER_OS', 'RUNNER_ARCH')},
        started=datetime.datetime.now(datetime.timezone.utc).isoformat(), steps=[],
        reused_reference=args.reuse_reference, timing_eligible=False, qualified_speedup=None)
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
        run('build', [sys.executable, str(HERE/'build.py')]+(['--reuse-reference'] if args.reuse_reference else []))
        build = json.loads((HERE/'build/receipt.json').read_text())
        (out/'build-receipt.json').write_text(json.dumps(build, indent=2)+'\n')
        for label, base, receipt in [('early', HERE, build),
                ('native', HERE.parent/'round110', build['reference']),
                ('reference', HERE.parent/'round108', build['reference']['reference'])]:
            groups = ('sources', 'binaries', 'generated', 'resources') if label == 'reference' else ('sources', 'binaries', 'generated') if label == 'early' else ('sources', 'binaries')
            for group in groups:
                for name, digest in receipt[group].items():
                    source = ROOT/'experiments'/name if label == 'reference' and group == 'sources' else base/name if group == 'sources' else base/'build'/name
                    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
                    target = out/label/group/name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
        for name, digest in build['query_sources'].items():
            source = HERE.parent/'round111'/name
            assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
            target = out/'query'/name
            target.parent.mkdir(exist_ok=True)
            shutil.copyfile(source, target)
        run('unit-tests', [sys.executable, '-m', 'unittest', 'discover', '-s', str(HERE), '-v'])
        run('panel', [sys.executable, str(HERE/'panel.py'), '--output', str(out/'panel')])
        run('audit', [sys.executable, str(HERE/'audit.py'), str(out/'panel/report.json'), '--output', str(out/'audit.json')])
        run('artifact-controls', [sys.executable, str(HERE/'test_artifact.py'), str(out/'panel/report.json'), str(out/'artifact-controls.json')])
    record.update(status='PASS', finished=datetime.datetime.now(datetime.timezone.utc).isoformat())
    save()


if __name__ == '__main__':
    main()
