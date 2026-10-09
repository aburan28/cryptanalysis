"""Build the opt-in compact message against a source-pinned F6 predecessor."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

from generate import PARENT_SHA256, generate

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root = HERE.parents[1]
    for path in HERE.glob('*.py'):
        assert path.read_bytes() == subprocess.check_output(
            ['git', 'show', 'HEAD:' + str(path.relative_to(root))], cwd=root)
    previous = HERE.parent / 'groebner-f6-message-20261009'
    source = previous / 'message_separator.cpp'
    assert sha(source) == PARENT_SHA256
    prior = json.loads((previous / 'build/receipt.json').read_text())
    assert prior['sources']['message_separator.cpp'] == PARENT_SHA256
    for name, digest in prior['binaries'].items():
        assert sha(previous / 'build' / name) == digest
    output = HERE / 'build'
    output.mkdir(exist_ok=True)
    generated = output / 'compact_separator.cpp'
    generated.write_text(generate(source.read_text()))
    compiler = os.environ.get('CXX', 'clang++')
    shared = ['-dynamiclib'] if sys.platform == 'darwin' else ['-shared', '-fPIC']
    suffix = '.dylib' if sys.platform == 'darwin' else '.so'
    commands, binaries = [], {}
    for tag, flags in (('', ['-O3']), ('-ubsan', ['-O1', '-g', '-fsanitize=undefined',
                                             '-fsanitize-undefined-trap-on-error',
                                             '-fno-sanitize-recover=all'])):
        binary = output / ('compact_separator' + tag + suffix)
        command = [compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror',
                   *flags, *shared, str(generated), '-o', str(binary)]
        subprocess.run(command, check=True)
        commands.append(command)
        binaries[binary.name] = sha(binary)
    receipt = dict(schema='f6-compact-boundary-build/1',
                   source_commit=subprocess.check_output(
                       ['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
                   sources={path.name: sha(path) for path in HERE.glob('*.py')},
                   predecessor=prior, generated_sha256=sha(generated),
                   compiler=subprocess.check_output([compiler, '--version'], text=True),
                   platform=platform.platform(), architecture=platform.machine(),
                   commands=commands, binaries=binaries,
                   timing_eligible=False, qualified_speedup=None)
    (output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('F6_COMPACT_BUILD_PASS', len(binaries), flush=True)


if __name__ == '__main__':
    main()
