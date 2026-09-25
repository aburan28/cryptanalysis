"""Build current Boolean libraries without rewriting historical receipts.

No Sage installation is required. --metal needs macOS and pkg-config m4ri
(or M4RI_PREFIX). Historical build.py scripts retain the measured recipes.
"""
import argparse
import os
from pathlib import Path
import shlex
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def build(metal=False):
    compiler = os.environ.get('CXX', 'clang++')
    suffix = '.dylib' if sys.platform == 'darwin' else '.so'
    shared = ['-dynamiclib'] if sys.platform == 'darwin' else ['-shared', '-fPIC']
    certificate = HERE.parent/'pdp-scaling/boolean_certificate.cpp'
    dual = HERE/'round2/boolean_dual.cpp'
    for folder in ('round2', 'round3'):
        (HERE/folder/'build').mkdir(exist_ok=True)
    for tag, flags in [('', ['-O3']), ('-ubsan', ['-O1', '-g', '-fsanitize=undefined', '-fno-sanitize-recover=all'])]:
        subprocess.run([compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', *flags, *shared,
                        str(certificate), '-o', str(HERE/'round3/build'/('boolean-certificate'+tag+suffix))], check=True)
    common = [compiler, '-O3', '-std=c++17', str(dual)]
    subprocess.run([*common, '-o', str(HERE/'round2/build/boolean-dual')], check=True)
    subprocess.run([*common, *shared, '-DBOOLEAN_DUAL_LIBRARY', '-DBOOLEAN_DUAL_NO_MAIN',
                    '-o', str(HERE/'round2/build'/('boolean-dual'+suffix))], check=True)
    if metal:
        if sys.platform != 'darwin':
            raise RuntimeError('--metal requires macOS')
        prefix = os.environ.get('M4RI_PREFIX')
        flags = ([f'-I{prefix}/include', f'-L{prefix}/lib', '-lm4ri', f'-Wl,-rpath,{prefix}/lib'] if prefix else
                 shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'm4ri'], text=True)))
        for name, source in [('tiled-rref', HERE/'round3/tiled_rref.mm'),
                             ('capture-m4ri', HERE/'round2/capture/boolean_f5b_m4ri.cpp')]:
            objc = ['-fobjc-arc', '-framework', 'Foundation', '-framework', 'Metal'] if source.suffix == '.mm' else []
            subprocess.run([compiler, '-O3', '-std=c++17', str(source), *objc, *flags,
                            '-o', str(HERE/'round3/build'/name)], check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metal', action='store_true')
    args = parser.parse_args()
    build(args.metal)
