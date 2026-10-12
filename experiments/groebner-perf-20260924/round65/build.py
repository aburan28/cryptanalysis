"""Build the independent transform locally; Metal is an explicit capability."""
import argparse
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metal', action='store_true')
    args = parser.parse_args()
    if args.metal and sys.platform != 'darwin':
        parser.error('Metal requires macOS')
    out = HERE / 'build'
    out.mkdir(exist_ok=True)
    compiler = os.environ.get('CXX', 'clang++')
    shared = ['-dynamiclib'] if sys.platform == 'darwin' else ['-shared', '-fPIC']
    suffix = '.dylib' if sys.platform == 'darwin' else '.so'
    ubsan = ['-fsanitize=undefined', '-fsanitize-undefined-trap-on-error', '-fno-sanitize-recover=all']
    variants = {
        '': ['-O3'], '-ubsan': ['-O1', '-g', *ubsan],
        '-reservation-budget': ['-O2', '-DCHECKER_RESERVATION_TEST_BUDGET=1', *ubsan],
        '-locality-audit': ['-O2', '-DCHECKER_PARTIAL_LOCALITY_AUDIT=1', *ubsan],
        '-identity-audit': ['-O2', '-DCHECKER_IDENTITY_AUDIT=1', *ubsan],
        '-transform-audit': ['-O2', '-DCHECKER_TRANSFORM_AUDIT=1', *ubsan],
        '-budget': ['-O2', '-DBRANCH_CHECK_ENUMERATION_BUDGET=8'],
        '-partial-budget': ['-O2', '-DPARTIAL_CHECK_WORK_BUDGET=8'],
        '-symmetry-budget': ['-O2', '-DSYMMETRY_CHECK_WORK_BUDGET=8'],
        '-symmetry-workspace': ['-O2', '-DSYMMETRY_CHECK_AUX_BYTES=0'],
        '-symmetry-late-budget': ['-O2', '-DSYMMETRY_CHECK_WORK_BUDGET=60'],
    }
    commands, binaries, generated = [], {}, {}
    if args.metal:
        shader = (HERE/'independent_transform.metal').read_text()
        glue = 'static const char* independent_transform_kernel = R"INDEPENDENT('+shader+')INDEPENDENT";\n'
        (out/'kernel.inc').write_text(glue)
        generated['kernel.inc'] = sha(out/'kernel.inc')
    metal_flags = ['-fobjc-arc', '-framework', 'Foundation', '-framework', 'Metal']
    backend = 'metal_transform.mm' if args.metal else 'metal_unavailable.cpp'
    backend_flags = metal_flags if args.metal else []

    def compile(name, files, flags, library):
        target = out / (name + (suffix if library else ''))
        command = [compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', '-pthread',
                   *(shared if library else []), *flags,
                   *(str(HERE/f) for f in files), '-o', str(target)]
        subprocess.run(command, check=True)
        commands.append(command)
        binaries[target.name] = sha(target)
        print('BUILT', target.name, flush=True)

    for tag, flags in variants.items():
        compile('checker'+tag, ['checker.cpp', backend], [*flags, *backend_flags], True)
    compile('checker-unavailable', ['checker.cpp', 'metal_unavailable.cpp'], ['-O3'], True)
    for tag, flags in (('', ['-O3']), ('-ubsan', ['-O1', *ubsan])):
        compile('test-kernel'+tag, ['test_kernel.cpp', backend],
                [*flags, *backend_flags, *([] if args.metal else ['-DEXPECT_UNAVAILABLE'])], False)
    compile('test-kernel-unavailable', ['test_kernel.cpp', 'metal_unavailable.cpp'],
            ['-O2', '-DEXPECT_UNAVAILABLE'], False)
    sources = {}
    receipt = json.loads((HERE.parent/'round54/build/receipt.json').read_text())
    for name, expected in receipt['sources'].items():
        assert sha(HERE.parent/name) == expected, name
        sources[name] = expected
    for glob in ('*.py', '*.cpp', '*.h', '*.mm', '*.metal', '*.json'):
        for path in HERE.glob(glob):
            sources[str(path.relative_to(HERE.parent))] = sha(path)
    (out/'receipt.json').write_text(json.dumps({
        'commands': commands, 'binaries': binaries, 'generated': generated, 'sources': sources,
        'metal_enabled': args.metal,
        'compiler': subprocess.check_output([compiler, '--version'], text=True),
        'architecture': platform.machine(), 'platform': platform.platform(),
    }, indent=2)+'\n')


if __name__ == '__main__':
    main()
