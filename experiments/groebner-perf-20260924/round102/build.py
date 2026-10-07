"""Fresh portable builds of both independent proof-value representations."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
P = HERE.parent
spec = importlib.util.spec_from_file_location('build101_for102', P/'round101/build.py')
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
previous.HERE = previous.baseline.HERE = previous.baseline.native.HERE = HERE
original_sources = previous.source_paths


def source_paths():
    paths = original_sources()+[P/'round101'/name for name in (
        'build.py', 'generate.py', 'query.py', 'common.py', 'panel.py', 'worker.py', 'audit.py')]
    return list(dict.fromkeys(paths+[HERE/'dense_values.inc']))


previous.baseline.native.source_paths = source_paths


def build():
    previous.build()
    from generate import dense_source
    out = HERE/'build'
    source = out/'dense_checker.cpp'
    source.write_text(dense_source())
    receipt = json.loads((out/'receipt.json').read_text())
    receipt['schema'] = 'dense-proof-build/1'
    receipt['generated'][source.name] = hashlib.sha256(source.read_bytes()).hexdigest()
    compiler = os.environ.get('CXX', 'clang++')
    shared = ['-dynamiclib'] if sys.platform == 'darwin' else ['-shared', '-fPIC']
    suffix = '.dylib' if sys.platform == 'darwin' else '.so'
    for tag, flags in (('', ['-O3']), ('-ubsan', ['-O1', '-g', '-fsanitize=undefined',
            '-fsanitize-undefined-trap-on-error', '-fno-sanitize-recover=all'])):
        binary = out/('dense_checker'+tag+suffix)
        command = [compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', *flags, *shared,
                   '-I', str(P/'round11'), str(source), '-o', str(binary)]
        subprocess.run(command, check=True)
        receipt['commands'].append(command)
        receipt['binaries'][binary.name] = hashlib.sha256(binary.read_bytes()).hexdigest()
    (out/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print('DENSE_PROOF_BUILD_PASS', len(receipt['binaries']), flush=True)


if __name__ == '__main__':
    build()
