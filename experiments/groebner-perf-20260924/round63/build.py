"""Rebuild portable native replay and the unchanged packed F4 dependencies."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

HERE = Path(__file__).resolve().parent
P = HERE.parent
ROOT = HERE.parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    out = HERE / 'build'
    out.mkdir(exist_ok=True)
    commands = [[sys.executable, str(P / 'round62/build.py')],
                [sys.executable, str(HERE / 'freeze_public_targets.py')]]
    for command in commands:
        subprocess.run(command, check=True)
    previous = json.loads((P / 'round62/build/receipt.json').read_text())
    compiler = os.environ.get('CXX', 'clang++')
    suffix = '.dylib' if sys.platform == 'darwin' else '.so'
    shared = ['-dynamiclib'] if sys.platform == 'darwin' else ['-shared', '-fPIC']
    modes = (('', ['-O3']), ('_ubsan', ['-O1', '-g', '-fsanitize=undefined',
             '-fsanitize-undefined-trap-on-error', '-fno-sanitize-recover=all']))
    binaries = dict(previous['binaries'])
    for tag, flags in modes:
        binary = out / ('replay' + tag + suffix)
        command = [compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', *flags,
                   *shared, str(HERE / 'curve_replay.cpp'), '-o', str(binary)]
        subprocess.run(command, check=True)
        commands.append(command)
        binaries[str(binary.relative_to(ROOT))] = sha(binary)
    sources = dict(previous['sources'])
    baseline = P / 'round62/results/preflight.json.gz'
    sources[str(baseline.relative_to(ROOT))] = sha(baseline)
    for pattern in ('*.py', '*.cpp', '*.json'):
        for path in HERE.glob(pattern):
            sources[str(path.relative_to(ROOT))] = sha(path)
    receipt = dict(previous, commands=commands, sources=sources, binaries=binaries,
                   compiler=subprocess.check_output([compiler, '--version'], text=True),
                   plan_sha256=sha(HERE / 'measurement_plan.json'),
                   platform=platform.platform(), architecture=platform.machine())
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')


if __name__ == '__main__':
    main()
