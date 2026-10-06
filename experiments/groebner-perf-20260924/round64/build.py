"""Bind the independent prepared field checker and rebuild native dependencies."""
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
    commands = [[sys.executable, str(P / 'round63/build.py')]]
    subprocess.run(commands[0], check=True)
    previous = json.loads((P / 'round63/build/receipt.json').read_text())
    compiler = os.environ.get('CXX', 'clang++')
    binaries = dict(previous['binaries'])
    sources = dict(previous['sources'])
    baseline = P / 'round63/results/preflight.json.gz'
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
