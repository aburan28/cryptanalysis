"""Build phase-only instrumentation without changing the round110 C ABI."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

from generate import HERE, SOURCE, generate


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference-root', type=Path, help='Source-matched existing reference build')
    args = parser.parse_args()
    root = HERE.parents[2]
    for path in (SOURCE, HERE/'phase.h', HERE/'generate.py', HERE/'build.py'):
        rel = path.relative_to(root)
        assert path.read_bytes() == subprocess.check_output(['git', 'show', 'HEAD:'+str(rel)], cwd=root)
    reference = args.reference_root or root
    if args.reference_root is None:
        subprocess.run([sys.executable, str(HERE.parent/'round110/build.py')], check=True)
    for rel in ('round108', 'round110'):
        local = HERE.parent/rel
        remote = reference/'experiments/groebner-perf-20260924'/rel
        receipt = json.loads((remote/'build/receipt.json').read_text())
        assert receipt['binaries']
        for name, digest in receipt['binaries'].items():
            assert sha(remote/'build'/name) == digest
        if rel == 'round110':
            assert receipt['sources']['seeded.cpp'] == sha(local/'seeded.cpp')
            assert receipt['sources']['seeded.h'] == sha(local/'seeded.h')
        else:
            assert receipt['generated']['engine.inc'] == sha(remote/'build/engine.inc')
    engine = reference/'experiments/groebner-perf-20260924/round108/build/engine.inc'
    assert engine.exists()
    out = HERE/'build'
    out.mkdir(exist_ok=True)
    source = out/'seeded_phases.cpp'
    source.write_text(generate())
    compiler = os.environ.get('CXX', 'clang++')
    shared = ['-dynamiclib'] if sys.platform == 'darwin' else ['-shared', '-fPIC']
    suffix = '.dylib' if sys.platform == 'darwin' else '.so'
    commands, binaries = [], {}
    for tag, flags in (('', ['-O3']), ('-ubsan', ['-O1', '-g', '-fsanitize=undefined',
            '-fsanitize-undefined-trap-on-error', '-fno-sanitize-recover=all'])):
        binary = out/('seeded_phases'+tag+suffix)
        command = [compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', *flags, *shared,
            '-I', str(engine.parent), '-I', str(HERE.parent/'round11'),
            '-I', str(HERE.parent/'round55'), '-I', str(HERE.parent/'round110'),
            '-I', str(HERE), '-DPERSISTENT_ORDER=1', '-DPIVOT_KEYS=1',
            '-DINDEXED_REDUCERS=0', str(source), '-o', str(binary)]
        subprocess.run(command, check=True)
        commands.append(command)
        binaries[binary.name] = sha(binary)
    receipt = dict(schema='seeded-phase-build/1',
        source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
        sources={p.name: sha(p) for p in HERE.glob('*') if p.suffix in ('.py', '.h')},
        parent_seeded_sha256=sha(SOURCE), engine_sha256=sha(engine),
        generated_sha256=sha(source), reference_root=str(reference),
        reference_reused=args.reference_root is not None,
        commands=commands, binaries=binaries,
        compiler=subprocess.check_output([compiler, '--version'], text=True),
        architecture=platform.machine(), platform=platform.platform(),
        timing_eligible=False, qualified_speedup=None)
    (out/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print('SEEDED_PHASE_BUILD_PASS', len(binaries), flush=True)


if __name__ == '__main__':
    main()
