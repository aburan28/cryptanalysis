"""Build the fixed-layout contraction with portable optimized and UBSan code."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def main():
    directory = HERE / 'build'
    directory.mkdir(exist_ok=True)
    cxx = os.environ.get('CXX', 'clang++')
    suffix = '.dylib' if sys.platform == 'darwin' else '.so'
    shared = ['-dynamiclib'] if sys.platform == 'darwin' else ['-shared', '-fPIC']
    commands, binaries = [], {}
    for tag, flags in [('', ['-O3']), ('-ubsan', ['-O1', '-g', '-fsanitize=undefined',
                       '-fsanitize-undefined-trap-on-error', '-fno-sanitize-recover=all'])]:
        path = directory / ('contraction' + tag + suffix)
        cmd = [cxx, '-std=c++17', '-Wall', '-Wextra', '-Werror', '-pthread', *shared,
               *flags, str(HERE / 'contraction.cpp'), '-o', str(path)]
        subprocess.run(cmd, check=True)
        commands.append(cmd)
        binaries[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (directory / 'receipt.json').write_text(json.dumps({'commands': commands,
        'binaries': binaries, 'compiler': subprocess.check_output([cxx, '--version'], text=True),
        'source_sha256': hashlib.sha256((HERE / 'contraction.cpp').read_bytes()).hexdigest()}, indent=2)+'\n')


if __name__ == '__main__':
    main()
