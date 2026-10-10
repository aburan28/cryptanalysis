"""Build source-bound optimized and UBSan cutset-bitplane libraries."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEPENDENCIES = (
    'experiments/groebner-f6-packed-20261009/packed_separator.cpp',
    'experiments/groebner-f6-prepared-20261009/prepared_separator.cpp',
    'experiments/groebner-f6-message-20261009/message_separator.cpp',
    'experiments/groebner-f6-grouped-factor-20261009/grouped_separator.cpp',
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT).strip():
        raise AssertionError('candidate source checkout must be clean')
    sources = {}
    for path in [*HERE.glob('*.cpp'), *HERE.glob('*.py'),
                 HERE / 'PROTOCOL.md',
                 ROOT / '.github/workflows/groebner-f6-cutset-bitplane.yml',
                 *(ROOT / name for name in DEPENDENCIES)]:
        name = str(path.relative_to(ROOT))
        actual = path.read_bytes()
        assert actual == subprocess.check_output(
            ['git', 'show', 'HEAD:' + name], cwd=ROOT), name
        sources[name] = sha(actual)
    output = HERE / 'build'
    output.mkdir(exist_ok=True)
    compiler = os.environ.get('CXX', 'clang++')
    shared = ['-dynamiclib'] if sys.platform == 'darwin' else ['-shared', '-fPIC']
    suffix = '.dylib' if sys.platform == 'darwin' else '.so'
    binaries, commands = {}, []
    for tag, flags in (('', ['-O3']), ('-ubsan', ['-O1', '-g',
        '-fsanitize=undefined', '-fsanitize-undefined-trap-on-error',
        '-fno-sanitize-recover=all'])):
        name = 'cutset_bitplane' + tag + suffix
        command = [compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror',
                   *flags, *shared, 'cutset_bitplane.cpp',
                   '-o', 'build/' + name]
        subprocess.run(command, cwd=HERE, check=True)
        commands.append(command)
        binaries[name] = sha((output / name).read_bytes())
    receipt = dict(schema='f6-cutset-bitplane-build/1',
                   source_commit=subprocess.check_output(
                       ['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                       text=True).strip(),
                   sources=sources, compiler=subprocess.check_output(
                       [compiler, '--version'], text=True),
                   platform=platform.platform(), architecture=platform.machine(),
                   commands=commands, binaries=binaries,
                   timing_eligible=False, qualified_speedup=None)
    (output / 'receipt.json').write_text(json.dumps(receipt, sort_keys=True,
                                                     indent=2) + '\n')
    print('F6_CUTSET_BITPLANE_BUILD_PASS', len(binaries), flush=True)


if __name__ == '__main__':
    main()
