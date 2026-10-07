"""Build the early transform with unchanged native-reference custody."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

from generate import HERE, source


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reuse-reference', action='store_true')
    args = parser.parse_args()
    root = HERE.parents[2]
    for path in HERE.glob('*.py'):
        assert path.read_bytes() == subprocess.check_output(['git', 'show', 'HEAD:'+str(path.relative_to(root))], cwd=root)
    if not args.reuse_reference:
        subprocess.run([sys.executable, str(HERE.parent/'round110/build.py')], check=True)
    reference = json.loads((HERE.parent/'round110/build/receipt.json').read_text())
    for name, value in reference['sources'].items():
        assert sha(HERE.parent/'round110'/name) == value
    for name, value in reference['reference']['sources'].items():
        assert sha(root/'experiments'/name) == value
    for group in ('binaries', 'generated', 'resources'):
        for name, value in reference['reference'][group].items():
            assert sha(HERE.parent/'round108/build'/name) == value
    for name, value in reference['binaries'].items():
        assert sha(HERE.parent/'round110/build'/name) == value
    out = HERE/'build'
    out.mkdir(exist_ok=True)
    generated = out/'early_macaulay.cpp'
    generated.write_text(source())
    compiler = os.environ.get('CXX', 'clang++')
    shared = ['-dynamiclib'] if sys.platform == 'darwin' else ['-shared', '-fPIC']
    suffix = '.dylib' if sys.platform == 'darwin' else '.so'
    commands, binaries = [], {}
    for tag, flags in (('', ['-O3']), ('-ubsan', ['-O1', '-g', '-fsanitize=undefined',
            '-fsanitize-undefined-trap-on-error', '-fno-sanitize-recover=all'])):
        path = out/('early_macaulay'+tag+suffix)
        command = [compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', *flags, *shared,
            '-I', str(HERE.parent/'round11'), str(generated), '-o', str(path)]
        subprocess.run(command, check=True)
        commands.append(command)
        binaries[path.name] = sha(path)
    receipt = dict(schema='early-parity-build/1', source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
        sources={p.name: sha(p) for p in HERE.glob('*.py')},
        query_sources={p.name: sha(p) for p in (HERE.parent/'round111').glob('*.py')},
        reference=reference, generated={generated.name: sha(generated)}, commands=commands,
        binaries=binaries, reused_reference_build=args.reuse_reference,
        compiler=subprocess.check_output([compiler, '--version'], text=True), architecture=platform.machine(),
        platform=platform.platform(), timing_eligible=False, qualified_speedup=None)
    (out/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print('EARLY_PARITY_BUILD_PASS', len(binaries), flush=True)


if __name__ == '__main__':
    main()
