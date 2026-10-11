"""Build portable constant-identity kernel controls with source/binary receipts."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    out = HERE / 'build'
    out.mkdir(exist_ok=True)
    compiler = os.environ.get('CXX', 'clang++')
    commands, binaries = [], {}
    sanitizer = ['-O1', '-g', '-fsanitize=undefined',
                 '-fsanitize-undefined-trap-on-error', '-fno-sanitize-recover=all']
    for name, source, flags in (
        ('test-constant', 'test_constant.cpp', ['-O3']),
        ('test-constant-ubsan', 'test_constant.cpp', sanitizer),
        ('bench-constant', 'bench_constant.cpp', ['-O3']),
        ('bench-constant-ubsan', 'bench_constant.cpp', sanitizer),
    ):
        command = [compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', *flags,
                   str(HERE/source), '-o', str(out/name)]
        subprocess.run(command, check=True)
        commands.append(command)
        binaries[name] = sha(out/name)
    receipt = {'commands': commands, 'binaries': binaries,
               'sources': {p.name: sha(p) for p in HERE.iterdir()
                           if p.suffix in ('.cpp', '.h', '.py')},
               'compiler': subprocess.check_output([compiler, '--version'], text=True),
               'architecture': platform.machine(), 'platform': platform.platform(),
               'timing_eligible': False, 'host_isolation_receipt': None}
    (out/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')


if __name__ == '__main__':
    main()
