"""Build producer and independent checker as separate native libraries."""
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
        for name in ('producer', 'checker'):
            compile(name, tag, [name+'.cpp'], flags)
        compile('contraction', tag, ['wide_contraction.cpp'], flags)
    compile('producer', '-budget', ['producer.cpp'], ['-O2', '-DQUADRATIC_ENUMERATION_BUDGET=8'])
    compile('checker', '-budget', ['checker.cpp'], ['-O2', '-DBRANCH_CHECK_ENUMERATION_BUDGET=8',
                                                  '-DBRANCH_BASIS_PROOF_BUDGET=128'])
    if args.metal:
        shader = (HERE/'quadratic.metal').read_text()
        glue = 'static const char* quadratic_kernel = R"QUADRATIC('+shader+')QUADRATIC";\n'
        (out/'kernel.inc').write_text(glue)
        generated['kernel.inc'] = hashlib.sha256(glue.encode()).hexdigest()
        compile('producer', '-metal', ['producer.cpp', 'metal_backend.mm'],
                ['-O3', '-DQUADRATIC_METAL', '-fobjc-arc', '-framework', 'Foundation', '-framework', 'Metal'])
    sources = [p for ext in ('*.py', '*.cpp', '*.h', '*.mm', '*.metal') for p in HERE.glob(ext)]
    sources += [HERE.parent/'round31/abi.h', HERE.parent/'round27/interpolation.hpp']
    (out/'receipt.json').write_text(json.dumps({'commands': commands, 'binaries': binaries,
        'generated': generated, 'compiler': subprocess.check_output([cxx, '--version'], text=True),
        'architecture': platform.machine(), 'platform': platform.platform(),
        'sources': {str(p.relative_to(HERE.parent)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}},
        sort_keys=True, indent=2)+'\n')


if __name__ == '__main__':
    main()
