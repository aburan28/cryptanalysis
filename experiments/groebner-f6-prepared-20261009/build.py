"""Build the prepared-factor candidate from a frozen source snapshot."""
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
    root = HERE.parents[1]
    sources = list(HERE.glob('*.py')) + list(HERE.glob('*.cpp'))
    for path in sources:
        assert path.read_bytes() == subprocess.check_output(
            ['git', 'show', 'HEAD:' + str(path.relative_to(root))], cwd=root)
    previous = HERE.parent / 'groebner-f6-packed-20261009'
    baseline = json.loads((previous / 'build/receipt.json').read_text())
    for name, digest in baseline['binaries'].items():
        assert sha(previous / 'build' / name) == digest
    output = HERE / 'build'
    output.mkdir(exist_ok=True)
    compiler = os.environ.get('CXX', 'clang++')
    shared = ['-dynamiclib'] if sys.platform == 'darwin' else ['-shared', '-fPIC']
    suffix = '.dylib' if sys.platform == 'darwin' else '.so'
    binaries, commands = {}, []
    for tag, flags in (('', ['-O3']), ('-ubsan', ['-O1', '-g', '-fsanitize=undefined',
                                             '-fsanitize-undefined-trap-on-error',
                                             '-fno-sanitize-recover=all'])):
        binary = output / ('prepared_separator' + tag + suffix)
        command = [compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror',
                   *flags, *shared, str(HERE / 'prepared_separator.cpp'),
                   '-o', str(binary)]
        subprocess.run(command, check=True)
        commands.append(command)
        binaries[binary.name] = sha(binary)
    receipt = dict(schema='f6-prepared-factor-build/1',
                   source_commit=subprocess.check_output(
                       ['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
                   sources={path.name: sha(path) for path in sources},
                   baseline_build=baseline,
                   compiler=subprocess.check_output([compiler, '--version'], text=True),
                   platform=platform.platform(), architecture=platform.machine(),
                   commands=commands, binaries=binaries,
                   timing_eligible=False, qualified_speedup=None)
    (output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('F6_PREPARED_BUILD_PASS', len(binaries), flush=True)


if __name__ == '__main__':
    main()
