"""Build the full independent checker with opt-in prepared constant witnesses."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from generate_checker import generate

HERE = Path(__file__).resolve().parent
OLD = HERE.parent/'round65'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metal', action='store_true')
    args = parser.parse_args()
    if args.metal and sys.platform != 'darwin': parser.error('Metal requires macOS')
    out = HERE/'build'
    out.mkdir(exist_ok=True)
    source = out/'checker.cpp'
    source.write_text(generate())
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
        '-constant-audit': ['-O2', '-DCHECKER_CONSTANT_AUDIT=1', *ubsan],
        '-constant-workspace': ['-O2', '-DCONSTANT_WORKSPACE_TEST_BYTES=0', *ubsan],
    }
    backend = 'metal_transform.mm' if args.metal else 'metal_unavailable.cpp'
    metal_flags = ['-fobjc-arc', '-framework', 'Foundation', '-framework', 'Metal']
    commands, binaries = [], {}
    for tag, flags in [*variants.items(), ('-unavailable', ['-O3'])]:
        selected = 'metal_unavailable.cpp' if tag == '-unavailable' else backend
        target = out/('checker'+tag+suffix)
        command = [compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', '-pthread',
                   '-I', str(OLD), *shared, *flags,
                   *(metal_flags if selected.endswith('.mm') else []),
                   str(source), str(OLD/selected), '-o', str(target)]
        subprocess.run(command, check=True)
        commands.append(command); binaries[target.name] = sha(target)
        print('BUILT', target.name, flush=True)
    prior = json.loads((OLD/'build/receipt.json').read_text())
    assert not args.metal or prior['metal_enabled'], 'Rebuild the Metal dependency first.'
    sources = dict(prior['sources'])
    for name, digest in sources.items(): assert sha(HERE.parent/name) == digest, name
    for pattern in ('*.py', '*.cpp', '*.h'):
        for path in HERE.glob(pattern): sources[str(path.relative_to(HERE.parent))] = sha(path)
    receipt = {'commands': commands, 'sources': sources, 'binaries': binaries,
               'generated': {'checker.cpp': sha(source)}, 'metal_enabled': args.metal,
               'compiler': subprocess.check_output([compiler, '--version'], text=True),
               'architecture': platform.machine(), 'platform': platform.platform()}
    (out/'native-receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')


if __name__ == '__main__':
    main()
