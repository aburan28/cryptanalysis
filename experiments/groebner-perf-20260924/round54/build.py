"""Build the independent checker on this host; retain exact dependency bindings."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

HERE = Path(__file__).resolve().parent
out = HERE / 'build'
out.mkdir(exist_ok=True)
compiler = os.environ.get('CXX', 'clang++')
shared = ['-dynamiclib'] if sys.platform == 'darwin' else ['-shared', '-fPIC']
suffix = '.dylib' if sys.platform == 'darwin' else '.so'
ubsan = ['-fsanitize=undefined', '-fsanitize-undefined-trap-on-error', '-fno-sanitize-recover=all']
variants = {
    '-reservation-budget': ['-O2', '-DCHECKER_RESERVATION_TEST_BUDGET=1', *ubsan],
    '': ['-O3'], '-ubsan': ['-O1', '-g', *ubsan],
    '-locality-audit': ['-O2', '-DCHECKER_PARTIAL_LOCALITY_AUDIT=1', *ubsan],
    '-identity-audit': ['-O2', '-DCHECKER_IDENTITY_AUDIT=1', *ubsan],
    '-transform-audit': ['-O2', '-DCHECKER_TRANSFORM_AUDIT=1', *ubsan],
    '-budget': ['-O2', '-DBRANCH_CHECK_ENUMERATION_BUDGET=8'],
    '-partial-budget': ['-O2', '-DPARTIAL_CHECK_WORK_BUDGET=8'],
    '-symmetry-budget': ['-O2', '-DSYMMETRY_CHECK_WORK_BUDGET=8'],
    '-symmetry-workspace': ['-O2', '-DSYMMETRY_CHECK_AUX_BYTES=0'],
    '-symmetry-late-budget': ['-O2', '-DSYMMETRY_CHECK_WORK_BUDGET=60'],
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


commands, binaries = [], {}
for tag, flags in variants.items():
    path = out / ('checker' + tag + suffix)
    command = [compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', '-pthread',
               *shared, *flags, str(HERE/'checker.cpp'), '-o', str(path)]
    subprocess.run(command, check=True)
    commands.append(command)
    binaries[path.name] = sha(path)
    print('BUILT', path.name, flush=True)
sources = {}
for version in (53,):
    receipt = json.loads((HERE.parent/f'round{version}/build/receipt.json').read_text())
    for name, expected in receipt['sources'].items():
        assert sha(HERE.parent/name) == expected, name
        sources[name] = expected
for glob in ('*.py', '*.cpp', '*.h', '*.json'):
    for path in HERE.glob(glob):
        sources[str(path.relative_to(HERE.parent))] = sha(path)
(out/'receipt.json').write_text(json.dumps({
    'commands': commands, 'binaries': binaries, 'generated': {}, 'sources': sources,
    'compiler': subprocess.check_output([compiler, '--version'], text=True),
    'architecture': platform.machine(), 'platform': platform.platform(),
}, indent=2)+'\n')
