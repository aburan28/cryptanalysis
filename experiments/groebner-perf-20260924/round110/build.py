"""Fresh reference/native continuation builds with complete source receipts."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REFERENCE = HERE.parent/'round108'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    for path in HERE.glob('*'):
        if path.suffix in ('.py', '.cpp', '.h'):
            assert path.read_bytes() == subprocess.check_output(['git', 'show', 'HEAD:'+str(path.relative_to(HERE.parents[2]))], cwd=HERE)
    subprocess.run([sys.executable, str(REFERENCE/'build.py')], check=True)
    reference = json.loads((REFERENCE/'build/receipt.json').read_text())
    out = HERE/'build'
    out.mkdir(exist_ok=True)
    compiler = os.environ.get('CXX', 'clang++')
    shared = ['-dynamiclib'] if sys.platform == 'darwin' else ['-shared', '-fPIC']
    suffix = '.dylib' if sys.platform == 'darwin' else '.so'
    commands, binaries = [], {}
    for tag, flags in (('', ['-O3']), ('-ubsan', ['-O1', '-g', '-fsanitize=undefined',
            '-fsanitize-undefined-trap-on-error', '-fno-sanitize-recover=all'])):
        binary = out/('seeded'+tag+suffix)
        command = [compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', *flags, *shared,
            '-I', str(REFERENCE/'build'), '-I', str(HERE.parent/'round11'), '-I', str(HERE.parent/'round55'),
            '-DPERSISTENT_ORDER=1', '-DPIVOT_KEYS=1', '-DINDEXED_REDUCERS=0', str(HERE/'seeded.cpp'), '-o', str(binary)]
        subprocess.run(command, check=True)
        commands.append(command)
        binaries[binary.name] = sha(binary)
    receipt = dict(schema='native-seeded-build/1', source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=HERE, text=True).strip(),
        sources={p.name: sha(p) for p in HERE.iterdir() if p.suffix in ('.cpp', '.h', '.py')},
        reference=reference, engine_sha256=sha(REFERENCE/'build/engine.inc'), commands=commands, binaries=binaries,
        compiler=subprocess.check_output([compiler, '--version'], text=True), architecture=platform.machine(),
        platform=platform.platform(), timing_eligible=False, qualified_speedup=None)
    (out/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print('NATIVE_SEEDED_BUILD_PASS', len(binaries), flush=True)


if __name__ == '__main__':
    main()
