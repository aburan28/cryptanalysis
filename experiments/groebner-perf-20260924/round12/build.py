"""Build a frozen baseline and three isolated reduction ablations."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
PREVIOUS = HERE.parent / 'round11'
VARIANTS = {'baseline': (0, 0), 'pivots': (0, 1),
            'ordered': (1, 0), 'combined': (1, 1)}


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
    suffix = '.dylib' if sys.platform == 'darwin' else '.so'
    shared = ['-dynamiclib'] if sys.platform == 'darwin' else ['-shared', '-fPIC']
    compiler = os.environ.get('CXX', 'clang++')
    commands = []
    for variant, (ordered, pivots) in VARIANTS.items():
        directory = output / variant / 'build'
        directory.mkdir(parents=True, exist_ok=True)
        engine = '../../baseline.inc' if variant == 'baseline' else '../../../native_engine.cpp'
        source = directory / 'adapter.cpp'
        source.write_text(adapter.replace(marker, f'#include "{engine}"'))
        for tag, flags in [('', ['-O3']), ('-ubsan', ['-O1', '-g', '-fsanitize=undefined',
                             '-fsanitize-undefined-trap-on-error', '-fno-sanitize-recover=all'])]:
            command = [compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', *flags,
                       *shared, '-I', str(PREVIOUS), f'-DPERSISTENT_ORDER={ordered}',
                       f'-DPIVOT_KEYS={pivots}', str(source), '-o',
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
    binaries = {str(p.relative_to(output)): sha(p) for p in output.rglob('*' + suffix)}
    (output / 'receipt.json').write_text(json.dumps({'commands': commands,
        'binaries': binaries, 'compiler': subprocess.check_output([compiler, '--version'], text=True),
        'baseline_sha256': sha(baseline), 'engine_sha256': sha(HERE / 'native_engine.cpp'),
        'adapter_sha256': sha(PREVIOUS / 'packed_producer.cpp'),
        'checker_sha256': sha(PREVIOUS / 'native_checker.cpp')}, indent=2) + '\n')


if __name__ == '__main__':
    main()
