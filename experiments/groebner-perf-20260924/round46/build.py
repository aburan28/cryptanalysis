"""Portable standalone kernel; never used for producing or accepting a basis."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

HERE = Path(__file__).resolve().parent
out = HERE/'build'
out.mkdir(exist_ok=True)
compiler = os.environ.get('CXX', 'clang++')
shared = ['-dynamiclib'] if sys.platform == 'darwin' else ['-shared', '-fPIC']
suffix = '.dylib' if sys.platform == 'darwin' else '.so'
commands, binaries = [], {}
for tag, flags in (('', ['-O3']), ('-ubsan', ['-O1', '-g', '-fsanitize=undefined',
        '-fsanitize-undefined-trap-on-error', '-fno-sanitize-recover=all'])):
    path = out/('transform'+tag+suffix)
    command = [compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', *shared,
               *flags, str(HERE/'kernels.cpp'), '-o', str(path)]
    subprocess.run(command, check=True)
    commands.append(command)
    binaries[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    print('BUILT', path, flush=True)
sources = [p for pattern in ('*.py', '*.cpp', '*.h') for p in HERE.glob(pattern)]
report = {'commands': commands, 'binaries': binaries,
          'architecture': platform.machine(), 'platform': platform.platform(),
          'compiler': subprocess.check_output([compiler, '--version'], text=True),
          'sources': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}}
(out/'receipt.json').write_text(json.dumps(report, indent=2)+'\n')
