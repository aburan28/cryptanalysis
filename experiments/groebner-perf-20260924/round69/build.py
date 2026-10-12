"""Build independent multiplier identity controls and diagnostic programs."""
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
    commands, binaries, generated = [], {}, {}
    if args.metal:
        (out / 'kernel.inc').write_text('static const char* multiplier_identity_kernel = R"IDENTITY('
                                      + (HERE / 'identity.metal').read_text() + ')IDENTITY";\n')
        generated['kernel.inc'] = sha(out / 'kernel.inc')
    metal_flags = ['-fobjc-arc', '-framework', 'Foundation', '-framework', 'Metal']
    ubsan = ['-fsanitize=undefined', '-fsanitize-undefined-trap-on-error', '-fno-sanitize-recover=all']
    for suffix, flags in (('', ['-O3']), ('-ubsan', ['-O1', '-g', *ubsan])):
        for name in ('test', 'bench') if (HERE / 'bench.cpp').exists() else ('test',):
            target = out / (name + suffix)
            command = [compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', '-pthread', *flags,
                       *(metal_flags if args.metal else ['-DEXPECT_UNAVAILABLE']),
                       str(HERE / (name + '.cpp')), str(HERE / 'cpu.cpp'),
                       str(HERE / ('metal.mm' if args.metal else 'unavailable.cpp')), '-o', str(target)]
            subprocess.run(command, check=True)
            commands.append(command)
            binaries[target.name] = sha(target)
        target = out / ('test-unavailable' + suffix)
        command = [compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', '-pthread', *flags,
                   '-DEXPECT_UNAVAILABLE', str(HERE / 'test.cpp'), str(HERE / 'cpu.cpp'),
                   str(HERE / 'unavailable.cpp'), '-o', str(target)]
        subprocess.run(command, check=True)
        commands.append(command)
        binaries[target.name] = sha(target)
    sources = {str(p.relative_to(HERE.parent)): sha(p)
               for pattern in ('*.cpp', '*.h', '*.mm', '*.metal', '*.py') for p in HERE.glob(pattern)}
    sources['round48/multiplier.h'] = sha(HERE.parent / 'round48/multiplier.h')
    (out / 'receipt.json').write_text(json.dumps({
        'commands': commands, 'sources': sources, 'binaries': binaries, 'generated': generated,
        'metal_enabled': args.metal, 'compiler': subprocess.check_output([compiler, '--version'], text=True),
        'architecture': platform.machine(), 'platform': platform.platform(),
    }, indent=2) + '\n')


if __name__ == '__main__':
    main()
