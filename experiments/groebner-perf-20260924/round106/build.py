"""Fresh reference and selected-row producer libraries, with source custody."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import ModuleType

HERE = Path(__file__).resolve().parent
P = HERE.parent
spec = importlib.util.spec_from_file_location('build105_for106', P/'round105/build.py')
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
seen = set()


def redirect(module):
    if id(module) in seen:
        return
    seen.add(id(module))
    module.HERE = HERE
    for name in ('previous', 'baseline', 'native'):
        child = getattr(module, name, None)
        if isinstance(child, ModuleType):
            redirect(child)


redirect(previous)
original_sources = previous.source_paths


def source_paths():
    paths = original_sources()+[P/'round105'/name for name in
        ('build.py', 'generate.py', 'query.py', 'normal_form.inc', 'normal_model.py')]
    return list(dict.fromkeys(paths+[HERE/'minimal_backsub.inc', HERE/'matrix_model.py']))


previous.previous.previous.previous.previous.baseline.native.source_paths = source_paths


def build():
    previous.build()
    from generate import minimal_source
    out = HERE/'build'
    source = out/'minimal_macaulay.cpp'
    source.write_text(minimal_source())
    receipt = json.loads((out/'receipt.json').read_text())
    receipt['schema'] = 'minimal-macaulay-build/1'
    receipt['generated'][source.name] = hashlib.sha256(source.read_bytes()).hexdigest()
    compiler = os.environ.get('CXX', 'clang++')
    shared = ['-dynamiclib'] if sys.platform == 'darwin' else ['-shared', '-fPIC']
    suffix = '.dylib' if sys.platform == 'darwin' else '.so'
    for tag, flags in (('', ['-O3']), ('-ubsan', ['-O1', '-g', '-fsanitize=undefined',
            '-fsanitize-undefined-trap-on-error', '-fno-sanitize-recover=all'])):
        binary = out/('minimal_macaulay'+tag+suffix)
        command = [compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', *flags, *shared,
                   '-I', str(P/'round11'), str(source), '-o', str(binary)]
        subprocess.run(command, check=True)
        receipt['commands'].append(command)
        receipt['binaries'][binary.name] = hashlib.sha256(binary.read_bytes()).hexdigest()
    (out/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print('MINIMAL_MACAULAY_BUILD_PASS', len(receipt['binaries']), flush=True)


if __name__ == '__main__':
    build()
