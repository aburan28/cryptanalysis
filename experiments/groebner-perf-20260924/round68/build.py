"""Build the shared-buffer producer locally; retain unchanged checker dependencies."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

from generate import generate, PINS

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metal', action='store_true')
    args = parser.parse_args()
    if args.metal and sys.platform != 'darwin': parser.error('Metal requires macOS')
    out = HERE / 'build'
    generate(out)
    compiler = os.environ.get('CXX', 'clang++')
    shared = ['-dynamiclib'] if sys.platform == 'darwin' else ['-shared', '-fPIC']
    suffix = '.dylib' if sys.platform == 'darwin' else '.so'
    ubsan = ['-fsanitize=undefined', '-fsanitize-undefined-trap-on-error', '-fno-sanitize-recover=all']
    variants = {
        '': ['-O3'], '-ubsan': ['-O1', '-g', *ubsan],
        '-budget': ['-O2', '-DQUADRATIC_ENUMERATION_BUDGET=8', '-DMULTIPLIER_WORK_BUDGET=8', '-DMULTIPLIER_BRANCH_BUDGET=8'],
        '-multiplier-budget': ['-O2', '-DMULTIPLIER_WORK_BUDGET=8', '-DMULTIPLIER_BRANCH_BUDGET=8'],
        '-copy-budget': ['-O2', '-DSYMMETRY_COPY_WORDS_BUDGET=0'],
        '-reconstruction-budget': ['-O2', '-DDEFERRED_RECONSTRUCTION_BUDGET=0'],
        '-enumeration-budget': ['-O2', '-DQUADRATIC_ENUMERATION_BUDGET=8'],
        '-partial-commit-budget': ['-O2', '-DMULTIPLIER_BRANCH_BUDGET=44'],
    }
    if args.metal:
        for name, path, variable, marker in (
            ('kernel.inc', HERE.parent / 'round51/quadratic.metal', 'quadratic_kernel', 'QUADRATIC'),
            ('transform_kernel.inc', HERE.parent / 'round67/producer_transform.metal', 'producer_transform_kernel', 'PRODUCER')):
            (out / name).write_text('static const char* ' + variable + ' = R"' + marker + '(' + path.read_text() + ')' + marker + '";\n')
    commands, binaries = [], {}
    include = ['-I', str(HERE), '-I', str(HERE.parent / 'round51'), '-I', str(HERE.parent / 'round67')]
    metal_flags = ['-DQUADRATIC_METAL', '-fobjc-arc', '-framework', 'Foundation', '-framework', 'Metal']

    def compile(name, files, flags, library):
        target = out / (name + (suffix if library else ''))
        command = [compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', '-pthread', *include,
                   *(shared if library else []), *flags, *(str(path) for path in files), '-o', str(target)]
        subprocess.run(command, check=True)
        commands.append(command)
        binaries[target.name] = sha(target)
        print('BUILT', target.name, flush=True)

    for metal in (False, True) if args.metal else (False,):
        for tag, flags in variants.items():
            files = [out / 'producer.cpp'] + ([out / 'backend.mm', out / 'transform.mm'] if metal else [])
            compile('producer' + ('-metal' if metal else '') + tag, files,
                    [*flags, *(metal_flags if metal else [])], True)
    if args.metal:
        for tag, flags in (('', ['-O3']), ('-ubsan', ['-O1', *ubsan]),
                           ('-setup-failure', ['-O2', '-DPRODUCER_TRANSFORM_TEST_FAIL_MODE=2', *ubsan])):
            compile('test-backend' + tag, [HERE / 'test_backend.mm', out / 'backend.mm', out / 'transform.mm'],
                    [*flags, *metal_flags], False)
    sources = {str(path.relative_to(HERE.parent)): sha(path) for pattern in ('*.py', '*.h', '*.mm', '*.inc') for path in HERE.glob(pattern)}
    for name in (*PINS, 'round67/transform.h', 'round67/producer_transform.metal', 'round51/quadratic.metal'):
        sources[name] = sha(HERE.parent / name)
    prior = json.loads((HERE.parent / 'round51/build/receipt.json').read_text())
    for name, digest in prior['sources'].items():
        assert sha(HERE.parent / name) == digest, name
        sources[name] = digest
    generated = {name: sha(out / name) for name in ('producer.cpp', 'backend.mm', 'transform.mm', 'normalized.py')}
    if args.metal:
        for name in ('kernel.inc', 'transform_kernel.inc'): generated[name] = sha(out / name)
    (out / 'receipt.json').write_text(json.dumps({
        'commands': commands, 'sources': sources, 'generated': generated, 'binaries': binaries,
        'metal_enabled': args.metal, 'compiler': subprocess.check_output([compiler, '--version'], text=True),
        'architecture': platform.machine(), 'platform': platform.platform(),
    }, indent=2) + '\n')


if __name__ == '__main__':
    main()
