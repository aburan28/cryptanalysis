"""Portable fresh builds of the compact adapter and unchanged reference kernels."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
P = HERE.parent
spec = importlib.util.spec_from_file_location('baseline95_for101', P/'round95/build.py')
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)
baseline.HERE = HERE
baseline.native.HERE = HERE
original_sources = baseline.source_paths


def source_paths():
    paths = original_sources() + [P/'round95'/name for name in
        ('build.py', 'generate.py', 'query.py', 'common.py', 'audit.py')]
    return list(dict.fromkeys(paths))


baseline.native.source_paths = source_paths


def build():
    baseline.build()
    from generate import sparse_source
    out = HERE/'build'
    source = out/'sparse_macaulay.cpp'
    source.write_text(sparse_source())
    receipt = json.loads((out/'receipt.json').read_text())
    receipt.update(schema='leased-macaulay-build/1', executables={})
    receipt['generated'][source.name] = hashlib.sha256(source.read_bytes()).hexdigest()
    compiler = os.environ.get('CXX', 'clang++')
    shared = ['-dynamiclib'] if sys.platform == 'darwin' else ['-shared', '-fPIC']
    suffix = '.dylib' if sys.platform == 'darwin' else '.so'
    for tag, flags in (('', ['-O3']), ('-ubsan', ['-O1', '-g', '-fsanitize=undefined',
            '-fsanitize-undefined-trap-on-error', '-fno-sanitize-recover=all'])):
        binary = out/('sparse_macaulay'+tag+suffix)
        command = [compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', *flags, *shared,
                   '-I', str(P/'round11'), str(source), '-o', str(binary)]
        subprocess.run(command, check=True)
        receipt['commands'].append(command)
        receipt['binaries'][binary.name] = hashlib.sha256(binary.read_bytes()).hexdigest()
    (out/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print('LEASED_MACAULAY_BUILD_PASS', len(receipt['binaries']), flush=True)


if __name__ == '__main__':
    build()
