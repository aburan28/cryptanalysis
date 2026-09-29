"""Build the bounded quadratic producer and retain compiler/source identities."""
import hashlib
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metal', action='store_true', help='Also build the explicit Metal variant on macOS')
    args = parser.parse_args()
    if args.metal and sys.platform != 'darwin':
        parser.error('Metal build requires macOS')
    out = HERE/'build'
    out.mkdir(exist_ok=True)
    cxx = os.environ.get('CXX', 'clang++')
    shared = ['-dynamiclib'] if sys.platform=='darwin' else ['-shared', '-fPIC']
    suffix = '.dylib' if sys.platform=='darwin' else '.so'
    commands, binaries = [], {}
    for tag, flags in (('', ['-O3']), ('-ubsan', ['-O1', '-g', '-fsanitize=undefined',
                        '-fsanitize-undefined-trap-on-error', '-fno-sanitize-recover=all']),
                       ('-budget', ['-O2', '-DQUADRATIC_ENUMERATION_BUDGET=8'])):
        target = out/('producer'+tag+suffix)
        command = [cxx, '-std=c++17', '-Wall', '-Wextra', '-Werror', *shared, *flags,
                   str(HERE/'producer.cpp'), '-o', str(target)]
        subprocess.run(command, check=True)
        commands.append(command)
        binaries[target.name] = hashlib.sha256(target.read_bytes()).hexdigest()
    generated = {}
    if args.metal:
        shader = (HERE/'quadratic.metal').read_text()
        (out/'kernel.inc').write_text('static const char* quadratic_kernel = R"QUADRATIC('+shader+')QUADRATIC";\n')
        generated['kernel.inc'] = hashlib.sha256((out/'kernel.inc').read_bytes()).hexdigest()
        target = out/('producer-metal'+suffix)
        command = [cxx, '-std=c++17', '-Wall', '-Wextra', '-Werror', *shared, '-O3',
                   '-DQUADRATIC_METAL', '-fobjc-arc', str(HERE/'producer.cpp'),
                   str(HERE/'metal_backend.mm'), '-framework', 'Foundation', '-framework', 'Metal', '-o', str(target)]
        subprocess.run(command, check=True)
        commands.append(command)
        binaries[target.name] = hashlib.sha256(target.read_bytes()).hexdigest()
    sources = [p for ext in ('*.py', '*.cpp', '*.h', '*.mm', '*.metal') for p in HERE.glob(ext)]
    sources += [HERE.parent/'round27/interpolation.hpp']
    (out/'receipt.json').write_text(json.dumps({'commands': commands, 'binaries': binaries,
        'compiler': subprocess.check_output([cxx, '--version'], text=True),
        'architecture': platform.machine(), 'platform': platform.platform(), 'generated': generated,
        'sources': {str(p.relative_to(HERE.parent)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}},
        sort_keys=True, indent=2)+'\n')


if __name__ == '__main__':
    main()
