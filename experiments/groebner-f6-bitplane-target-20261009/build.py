"""Build a source-bound bitplane separator against the exact compact engine."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'groebner-f6-boundary-compact-20261009'))
from generate import PARENT_SHA256, generate as generate_compact  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root = HERE.parents[1]
    sources = {}
    for path in list(HERE.glob('*.py')) + list(HERE.glob('*.cpp')):
        assert path.read_bytes() == subprocess.check_output(
            ['git', 'show', 'HEAD:' + str(path.relative_to(root))], cwd=root)
        sources[path.name] = sha(path)
    parent = HERE.parent / 'groebner-f6-message-20261009/message_separator.cpp'
    assert sha(parent) == PARENT_SHA256
    compact_receipt = json.loads((HERE.parent /
        'groebner-f6-boundary-compact-20261009/evidence/build-receipt.json').read_text())
    output = HERE / 'build'
    output.mkdir(exist_ok=True)
    generated = output / 'compact_separator.cpp'
    generated.write_text(generate_compact(parent.read_text()))
    assert sha(generated) == compact_receipt['generated_sha256']
    compiler = os.environ.get('CXX', 'clang++')
    shared = ['-dynamiclib'] if sys.platform == 'darwin' else ['-shared', '-fPIC']
    suffix = '.dylib' if sys.platform == 'darwin' else '.so'
    commands, binaries = [], {}
    for tag, flags in (('', ['-O3']), ('-ubsan', ['-O1', '-g', '-fsanitize=undefined',
                                             '-fsanitize-undefined-trap-on-error',
                                             '-fno-sanitize-recover=all'])):
        binary = output / ('bitplane_separator' + tag + suffix)
        command = [compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror',
                   *flags, *shared, str(HERE / 'bitplane_separator.cpp'),
                   '-o', str(binary)]
        subprocess.run(command, check=True)
        commands.append(command)
        binaries[binary.name] = sha(binary)
    receipt = dict(schema='f6-bitplane-target-build/1',
                   source_commit=subprocess.check_output(
                       ['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
                   sources=sources, predecessor_source_sha256=PARENT_SHA256,
                   compact_generated_sha256=sha(generated),
                   compiler=subprocess.check_output([compiler, '--version'], text=True),
                   platform=platform.platform(), architecture=platform.machine(),
                   commands=commands, binaries=binaries,
                   timing_eligible=False, qualified_speedup=None)
    (output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('F6_BITPLANE_BUILD_PASS', len(binaries), flush=True)


if __name__ == '__main__':
    main()
