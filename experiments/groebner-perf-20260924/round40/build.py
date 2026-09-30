"""Build the opt-in CPU proof constructor; the round34 checker is unchanged."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    out = HERE / 'build'
    out.mkdir(exist_ok=True)
    compiler = os.environ.get('CXX', 'clang++')
    shared = ['-dynamiclib'] if sys.platform == 'darwin' else ['-shared', '-fPIC']
    suffix = '.dylib' if sys.platform == 'darwin' else '.so'
    variants = [('', ['-O3']), ('-ubsan', ['-O1', '-g', '-fsanitize=undefined',
                    '-fsanitize-undefined-trap-on-error', '-fno-sanitize-recover=all']),
                ('-budget', ['-O2', '-DQUADRATIC_ENUMERATION_BUDGET=8', '-DMULTIPLIER_WORK_BUDGET=8', '-DMULTIPLIER_BRANCH_BUDGET=8']),
                ('-multiplier-budget', ['-O2', '-DMULTIPLIER_WORK_BUDGET=8', '-DMULTIPLIER_BRANCH_BUDGET=8']),
                ('-copy-budget', ['-O2', '-DSYMMETRY_COPY_WORDS_BUDGET=0']),
                ('-reconstruction-budget', ['-O2', '-DDEFERRED_RECONSTRUCTION_BUDGET=0'])]
    commands, binaries = [], {}
    for tag, flags in variants:
        binary = out / ('producer' + tag + suffix)
        command = [compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', *shared, *flags,
                   str(HERE / 'producer.cpp'), '-o', str(binary)]
        subprocess.run(command, check=True)
        commands.append(command)
        binaries[str(binary.relative_to(HERE))] = sha(binary)
    sources = list(HERE.glob('*.py')) + list(HERE.glob('*.cpp')) + list(HERE.glob('*.h'))
    sources += [HERE.parent / f'round{v}/abi.h' for v in (31, 32, 33, 34, 35, 36)]
    sources += [HERE.parent / 'round27/interpolation.hpp', HERE / 'fixtures/inputs.json.gz']
    receipt = {'schema': 'quadratic-projection-native-build/1', 'source_sha256': sha(HERE / 'producer.cpp'),
               'dependency_sources': {str(path): sha(path) for path in sources},
               'repository_source_sha256': {str(path.relative_to(HERE.parents[2])): sha(path) for path in sources},
               'commands': commands, 'binaries': binaries,
               'compiler': subprocess.check_output([compiler, '--version'], text=True),
               'platform': platform.platform(), 'architecture': platform.machine(),
               'python': sys.version, 'timing_eligible': False}
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')


if __name__ == '__main__':
    main()
