"""Build portable, separately linked producer/checker, optimized and UBSan."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def main():
    output = HERE/'build'
    output.mkdir(exist_ok=True)
    compiler = os.environ.get('CXX', 'clang++')
    shared = ['-dynamiclib'] if sys.platform == 'darwin' else ['-shared', '-fPIC']
    suffix = '.dylib' if sys.platform == 'darwin' else '.so'
    commands, binaries = [], {}
    for tag, flags in (('', ['-O3']), ('-ubsan', ['-O1', '-g', '-fsanitize=undefined',
                     '-fsanitize-undefined-trap-on-error', '-fno-sanitize-recover=all']),
                     ('-budget', ['-O2', '-DCONDITIONAL_PROOF_BUDGET=8'])):
        for name in ('producer', 'checker'):
            if tag == '-budget' and name != 'checker':
                continue
            target = output/(name+tag+suffix)
            command = [compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror',
                       *shared, *flags, str(HERE/(name+'.cpp')), '-o', str(target)]
            subprocess.run(command, check=True)
            commands.append(command)
            binaries[target.name] = hashlib.sha256(target.read_bytes()).hexdigest()
    (output/'receipt.json').write_text(json.dumps({
        'commands': commands, 'binaries': binaries, 'platform': platform.platform(),
        'architecture': platform.machine(), 'python': platform.python_version(),
        'compiler': subprocess.check_output([compiler, '--version'], text=True),
        'sources': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(HERE.iterdir()) if p.suffix in ('.h', '.hpp', '.cpp', '.py')},
    }, indent=2)+'\n')


if __name__ == '__main__':
    main()
