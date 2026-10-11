"""Build the original, ordered, and frontier producers with independent checking."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from cache_transform import cached_engine

HERE = Path(__file__).resolve().parent
PREVIOUS = HERE.parent / 'round11'
VARIANTS = ('baseline', 'ordered', 'frontier', 'indexed', 'cached', 'cached_indexed')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / 'build'
    output.mkdir(exist_ok=True)
    adapter = (PREVIOUS / 'packed_producer.cpp').read_text()
    marker = '#include "build/native_engine.inc"'
    assert adapter.count(marker) == 1
    baseline = HERE.parent / 'round5/native_f4.cpp'
    assert sha(baseline) == 'b05b351b46b8091f3ee75c2601fbca9b835da96d7dcf3c215f5bb93bfa347c45'
    (output / 'baseline.inc').write_text(baseline.read_text().split('\nstatic void print_success(')[0] + '\n')
    ordered = HERE.parent / 'round12/native_engine.cpp'
    assert sha(ordered) == '3153861f2fb9ecc0e07bdff29bf196bc4e7444e10c4989fc4e180afee3378c67'
    engine = ordered.read_text()
    assert engine.count('    Row normal(') == 2
    start = engine.index('    Row normal(')
    end = engine.index('#else', start)
    frontier = engine[:start] + (HERE / 'normal_frontier.inc').read_text() + engine[end:]
    (output / 'ordered.inc').write_text(engine)
    (output / 'frontier.inc').write_text(frontier)
    (output / 'indexed.inc').write_text(frontier)
    cached=cached_engine(frontier)
    (output / 'cached.inc').write_text(cached)
    (output / 'cached_indexed.inc').write_text(cached)
    suffix = '.dylib' if sys.platform == 'darwin' else '.so'
    shared = ['-dynamiclib'] if sys.platform == 'darwin' else ['-shared', '-fPIC']
    compiler = os.environ.get('CXX', 'clang++')
    commands = []
    for variant in VARIANTS:
        directory = output / variant / 'build'
        directory.mkdir(parents=True, exist_ok=True)
        engine = '../../' + variant + '.inc'
        source = directory / 'adapter.cpp'
        source.write_text(adapter.replace(marker, f'#include "{engine}"'))
        for tag, flags in [('', ['-O3']), ('-ubsan', ['-O1', '-g', '-fsanitize=undefined',
                             '-fsanitize-undefined-trap-on-error', '-fno-sanitize-recover=all'])]:
            command = [compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', *flags,
                       *shared, '-I', str(PREVIOUS), '-DPERSISTENT_ORDER=1', '-DPIVOT_KEYS=1', f'-DINDEXED_REDUCERS={int(variant in ("indexed", "cached_indexed"))}', str(source), '-o',
                       str(directory / ('packed_producer' + tag + suffix))]
            subprocess.run(command, check=True)
            commands.append(command)
    for tag, flags in [('', ['-O3']), ('-ubsan', ['-O1', '-g', '-fsanitize=undefined',
                         '-fsanitize-undefined-trap-on-error', '-fno-sanitize-recover=all'])]:
        command = [compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', *flags,
                   *shared, str(PREVIOUS / 'native_checker.cpp'), '-o',
                   str(output / ('native_checker' + tag + suffix))]
        subprocess.run(command, check=True)
        commands.append(command)
    for tag, flags in [('', ['-O3']), ('-ubsan', ['-O1', '-g', '-fsanitize=undefined',
                         '-fsanitize-undefined-trap-on-error', '-fno-sanitize-recover=all'])]:
        for name in ('charge', 'divisors', 'cache'):
            command = [compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', *flags,
                       '-DINDEXED_REDUCERS=1', str(HERE / ('test_' + name + '.cpp')),
                       '-o', str(output / ('test-' + name + tag))]
            subprocess.run(command, check=True)
            commands.append(command)
        for variant in VARIANTS:
            link = output / variant / 'build' / ('native_checker' + tag + suffix)
            if not link.exists():
                link.symlink_to('../../' + link.name)
    binaries = {str(p.relative_to(output)): sha(p) for p in output.rglob('*' + suffix)}
    (output / 'receipt.json').write_text(json.dumps({'commands': commands,
        'binaries': binaries, 'compiler': subprocess.check_output([compiler, '--version'], text=True),
        'baseline_sha256': sha(baseline), 'ordered_sha256': sha(ordered), 'frontier_sha256': sha(HERE / 'normal_frontier.inc'),
        'adapter_sha256': sha(PREVIOUS / 'packed_producer.cpp'),
        'checker_sha256': sha(PREVIOUS / 'native_checker.cpp')}, indent=2) + '\n')


if __name__ == '__main__':
    main()
