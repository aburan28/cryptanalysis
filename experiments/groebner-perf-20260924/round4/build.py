"""Build the opt-in packed solver and independent verifier, with UBSan variants."""
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def build():
    output = HERE / 'build'
    output.mkdir(exist_ok=True)
    compiler = os.environ.get('CXX', 'clang++')
    suffix = '.dylib' if sys.platform == 'darwin' else '.so'
    shared = ['-dynamiclib'] if sys.platform == 'darwin' else ['-shared', '-fPIC']
    for tag, flags in [('', ['-O3']), ('-ubsan', ['-O1', '-g', '-fsanitize=undefined', '-fno-sanitize-recover=all'])]:
        for name in ('packed_dual', 'packed_certificate'):
            subprocess.run([compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            *flags, *shared, str(HERE / (name+'.cpp')),
                            '-o', str(output / (name+tag+suffix))], check=True)


if __name__ == '__main__':
    build()
