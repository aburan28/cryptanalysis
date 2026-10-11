"""Build the sparse native Boolean F4 proof producer and UBSan variant."""
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent


def build():
    (HERE/'build').mkdir(exist_ok=True)
    for suffix, flags in [('', ['-O3']), ('-ubsan', ['-O1','-g','-fsanitize=undefined','-fno-sanitize-recover=all'])]:
        subprocess.run([os.environ.get('CXX','clang++'), '-std=c++17', '-Wall','-Wextra','-Werror',
                        *flags, str(HERE/'native_f4.cpp'), '-o', str(HERE/'build'/('native-f4'+suffix))],check=True)


if __name__ == '__main__':
    build()
