"""Build the opt-in independent Boolean field-pair obstruction probe."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference-root', type=Path)
    args = parser.parse_args()
    root = HERE.parents[2]
    for path in list(HERE.glob('*.py')) + list(HERE.glob('*.cpp')):
        relative = path.relative_to(root)
        assert path.read_bytes() == subprocess.check_output(
            ['git', 'show', 'HEAD:' + str(relative)], cwd=root)
    earlier = HERE.parent / 'round119'
    receipt_path = earlier / 'build/receipt.json'
    if not receipt_path.exists():
        command = [sys.executable, str(earlier / 'build.py')]
        if args.reference_root is not None:
            command += ['--reference-root', str(args.reference_root.resolve())]
        subprocess.run(command, check=True)
    prior = json.loads(receipt_path.read_text())
    for name, digest in prior['binaries'].items():
        assert sha(earlier / 'build' / name) == digest
    output = HERE / 'build'
    output.mkdir(exist_ok=True)
    compiler = os.environ.get('CXX', 'clang++')
    shared = ['-dynamiclib'] if sys.platform == 'darwin' else ['-shared', '-fPIC']
    suffix = '.dylib' if sys.platform == 'darwin' else '.so'
    commands, binaries = [], {}
    for tag, flags in (('', ['-O3']), ('-ubsan', ['-O1', '-g', '-fsanitize=undefined',
                                             '-fsanitize-undefined-trap-on-error',
                                             '-fno-sanitize-recover=all'])):
        binary = output / ('field_obstruction' + tag + suffix)
        command = [compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', *flags,
                   *shared, '-I', str(HERE.parent / 'round11'),
                   str(HERE / 'field_obstruction.cpp'), '-o', str(binary)]
        subprocess.run(command, check=True)
        commands.append(command)
        binaries[binary.name] = sha(binary)
    receipt = dict(schema='f4-field-obstruction-build/1',
                   source_commit=subprocess.check_output(
                       ['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
                   sources={p.name: sha(p) for p in list(HERE.glob('*.py')) +
                            list(HERE.glob('*.cpp'))},
                   reference_root=str((args.reference_root or root).resolve()),
                   previous_build=prior, compiler=subprocess.check_output(
                       [compiler, '--version'], text=True),
                   architecture=platform.machine(), platform=platform.platform(),
                   commands=commands, binaries=binaries, timing_eligible=False,
                   qualified_speedup=None)
    (output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('F4_FIELD_OBSTRUCTION_BUILD_PASS', len(binaries), flush=True)


if __name__ == '__main__':
    main()
