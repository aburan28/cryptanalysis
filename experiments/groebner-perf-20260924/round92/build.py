"""Fresh builds of reusable Macaulay layouts, frozen round62 F4, and round11 checking."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

HERE = Path(__file__).resolve().parent
P = HERE.parent

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def source_paths():
    dependencies = {
        4: ['packed_dual.cpp'], 5: ['algebraic_certificate.py', 'workloads.py'],
        11: ['proof_abi.h', 'packed_producer.cpp', 'native_checker.cpp', 'packed_proof.py'],
        12: ['native_engine.cpp'], 13: ['cache_transform.py', 'normal_frontier.inc'],
        55: ['build.py', 'checked_chains.inc', 'chain_stats.h'],
        56: ['build.py', 'top_normal.inc'], 58: ['build.py', 'column_matrix.inc'],
        61: ['native_build.py', 'scratch_add.inc'], 62: ['native_build.py', 'packed_matrix.inc'],
    }
    paths = [P/f'round{n}'/name for n, names in dependencies.items() for name in names]
    paths += [P.parent/'pdp-scaling'/name for name in ('boolean_f5b.py', 'macaulay_cache.py', 'boolean_basis.py')]
    paths += [p for p in HERE.iterdir() if p.suffix in ('.py', '.cpp')]
    return paths + [HERE/'panel.json']

def build():
    out = HERE / 'build'
    out.mkdir(exist_ok=True)
    spec = importlib.util.spec_from_file_location('f4_source91', P/'round62/native_build.py')
    previous = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(previous)
    source = previous.source(8388608)
    old = '#include "../../../../../round55/chain_stats.h"'
    assert source.count(old) == 1
    (out/'engine.inc').write_text(source.replace(old, '#include "chain_stats.h"'))
    adapter = (P/'round11/packed_producer.cpp').read_text()
    adapter = previous.change(adapter, '#include "build/native_engine.inc"', '#include "engine.inc"')
    adapter = previous.change(adapter, 'auto start=Clock::now();failure.clear();',
        'auto start=Clock::now();failure.clear();top_stats={};column_stats={};scratch_stats={};packed_stats={};chain_stats={};chain_stats.mode=1;')
    (out/'adapter.cpp').write_text(adapter)
    compiler = os.environ.get('CXX', 'clang++')
    shared = ['-dynamiclib'] if sys.platform == 'darwin' else ['-shared', '-fPIC']
    suffix = '.dylib' if sys.platform == 'darwin' else '.so'
    commands = []
    modes = [('', ['-O3']), ('-ubsan', ['-O1', '-g', '-fsanitize=undefined',
              '-fsanitize-undefined-trap-on-error', '-fno-sanitize-recover=all'])]
    for tag, flags in modes:
        for name, path in [('packed_producer', out/'adapter.cpp'),
                           ('native_checker', P/'round11/native_checker.cpp'),
                           ('macaulay', HERE/'macaulay.cpp'),
                           ('packed_dual', P/'round4/packed_dual.cpp')]:
            command = [compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', *flags,
                       *shared, '-I', str(P/'round11'), '-I', str(P/'round55'),
                       '-DPERSISTENT_ORDER=1', '-DPIVOT_KEYS=1', '-DINDEXED_REDUCERS=0',
                       str(path), '-o', str(out/(name+tag+suffix))]
            subprocess.run(command, check=True)
            commands.append(command)
    reference = P.parent/'pdp-scaling/boolean_f5b.py'
    text = reference.read_text()
    native_import = 'try:\n    from boolean_native import interreduce as native_interreduce\nexcept ImportError:\n    native_interreduce = None'
    assert text.count(native_import) == 1
    (out/'f5_reference.py').write_text(text.replace(native_import, 'native_interreduce = None'))
    paths = source_paths()
    receipt = dict(schema='reusable-macaulay-build/1', commands=commands,
        compiler=subprocess.check_output([compiler, '--version'], text=True),
        platform=platform.platform(), architecture=platform.machine(),
        sources={str(p.relative_to(P.parent)):sha(p) for p in paths},
        generated={p.name:sha(p) for p in (out/'engine.inc', out/'adapter.cpp', out/'f5_reference.py')},
        binaries={p.name:sha(p) for p in out.glob('*'+suffix)},
        timing_eligible=False, qualified_speedup=None)
    (out/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print('BUILD_PASS', len(receipt['binaries']), flush=True)

if __name__ == '__main__':
    build()
