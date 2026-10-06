"""Build the deferred-proof producer; use the unchanged round34 checker library."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metal', action='store_true')
    args = parser.parse_args()
    if args.metal and sys.platform != 'darwin':
        parser.error('Metal requires macOS')
    out = HERE/'build'
    out.mkdir(exist_ok=True)
    cxx = os.environ.get('CXX', 'clang++')
    shared = ['-dynamiclib'] if sys.platform == 'darwin' else ['-shared', '-fPIC']
    suffix = '.dylib' if sys.platform == 'darwin' else '.so'
    commands, binaries, generated = [], {}, {}

    def compile(name, tag, files, flags):
        target = out/(name+tag+suffix)
        command = [cxx, '-std=c++17', '-Wall', '-Wextra', '-Werror', *shared, *flags,
                   *(str(HERE/f) for f in files), '-o', str(target)]
        subprocess.run(command, check=True)
        commands.append(command)
        binaries[target.name] = hashlib.sha256(target.read_bytes()).hexdigest()

    for tag, flags in (('', ['-O3']), ('-ubsan', ['-O1', '-g', '-fsanitize=undefined',
                       '-fsanitize-undefined-trap-on-error', '-fno-sanitize-recover=all'])):
        for name in ('producer',):
            compile(name, tag, [name+'.cpp'], flags)
    compile('producer', '-budget', ['producer.cpp'], ['-O2', '-DQUADRATIC_ENUMERATION_BUDGET=8', '-DMULTIPLIER_WORK_BUDGET=8', '-DMULTIPLIER_BRANCH_BUDGET=8'])
    compile('producer', '-multiplier-budget', ['producer.cpp'], ['-O2', '-DMULTIPLIER_WORK_BUDGET=8', '-DMULTIPLIER_BRANCH_BUDGET=8'])
    compile('producer', '-copy-budget', ['producer.cpp'], ['-O2', '-DSYMMETRY_COPY_WORDS_BUDGET=0'])
    compile('producer', '-reconstruction-budget', ['producer.cpp'], ['-O2', '-DDEFERRED_RECONSTRUCTION_BUDGET=0'])
    if args.metal:
        shader = (HERE/'quadratic.metal').read_text()
        glue = 'static const char* quadratic_kernel = R"QUADRATIC('+shader+')QUADRATIC";\n'
        (out/'kernel.inc').write_text(glue)
        generated['kernel.inc'] = hashlib.sha256(glue.encode()).hexdigest()
        compile('producer', '-metal', ['producer.cpp', 'metal_backend.mm'],
                ['-O3', '-DQUADRATIC_METAL', '-fobjc-arc', '-framework', 'Foundation', '-framework', 'Metal'])
    sources = [p for ext in ('*.py', '*.cpp', '*.h', '*.mm', '*.metal') for p in HERE.glob(ext)]
    sources += [HERE.parent/f'round{v}/abi.h' for v in (31,32,33,34,35)] + [HERE.parent/'round27/interpolation.hpp']
    (out/'receipt.json').write_text(json.dumps({'commands': commands, 'binaries': binaries,
        'generated': generated, 'compiler': subprocess.check_output([cxx, '--version'], text=True),
        'architecture': platform.machine(), 'platform': platform.platform(),
        'sources': {str(p.relative_to(HERE.parent)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}},
        sort_keys=True, indent=2)+'\n')


if __name__ == '__main__':
    main()
