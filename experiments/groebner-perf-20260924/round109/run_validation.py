"""Fresh reference build, seeded controls, independent audit and failure retention."""
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
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    record = dict(status='RUNNING', source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=HERE, text=True).strip(),
                  source_tree=subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=HERE, text=True).strip(),
                  ci={n: os.environ.get(n) for n in ('GITHUB_SHA', 'GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT', 'GITHUB_EVENT_NAME', 'RUNNER_OS', 'RUNNER_ARCH')},
                  started=datetime.datetime.now(datetime.timezone.utc).isoformat(), steps=[],
                  timing_eligible=False, qualified_speedup=None)

    def save():
        (out/'validation.json').write_text(json.dumps(record, indent=2)+'\n')

    def run(label, command):
        with (out/(label+'.log')).open('w') as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, cwd=HERE.parents[2])
        record['steps'].append(dict(label=label, command=command, exit_code=result.returncode))
        if result.returncode:
            record['status'] = 'FAIL'
        save()
        if result.returncode:
            raise SystemExit(result.returncode)
        print('PASS', label, flush=True)

    save()
    lock = Path('/private/tmp/cryptanalysis-overlap-evidence-20261003/local-heavy.lock'
                if sys.platform == 'darwin' else '/tmp/groebner-local-heavy.lock')
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open('a') as guard:
        fcntl.flock(guard, fcntl.LOCK_EX)
        sys.path.insert(0, str(REFERENCE))
        try:
            from build import source_paths
            sources = source_paths()
        finally:
            sys.path.pop(0)
        for path in sources+list(HERE.glob('*.py')):
            relative = str(path.relative_to(HERE.parents[2]))
            assert subprocess.check_output(['git', 'show', 'HEAD:'+relative], cwd=HERE) == path.read_bytes()
        run('build', [sys.executable, str(REFERENCE/'build.py')])
        receipt = json.loads((REFERENCE/'build/receipt.json').read_text())
        (out/'build-receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
        for group in ('sources', 'binaries', 'generated', 'resources'):
            for name, digest in receipt[group].items():
                source = REFERENCE.parent.parent/name if group == 'sources' else REFERENCE/'build'/name
                assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
                destination = out/group/name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
        (out/'scripts').mkdir()
        for path in HERE.glob('*.py'):
            shutil.copyfile(path, out/'scripts'/path.name)
    # Discovery takes the same lock itself; never hold it across this call.
    run('discovery', [sys.executable, str(HERE/'discover.py'), '--reference', str(REFERENCE), '--output', str(out/'discovery')])
    with lock.open('a') as guard:
        fcntl.flock(guard, fcntl.LOCK_EX)
        run('audit', [sys.executable, str(HERE/'audit.py'), str(out/'discovery/report.json'), '--output', str(out/'audit.json')])
        run('artifact-controls', [sys.executable, str(HERE/'test_artifact.py'), str(out/'discovery/report.json'), str(out/'artifact-controls.json')])
    record.update(status='PASS', finished=datetime.datetime.now(datetime.timezone.utc).isoformat())
    save()


if __name__ == '__main__':
    main()
