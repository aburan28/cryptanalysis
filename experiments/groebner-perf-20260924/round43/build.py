"""Build separate partial-affine producer/checker libraries on the current CPU."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def main():
    out = HERE / 'build'
    out.mkdir(exist_ok=True)
    cxx = os.environ.get('CXX', 'clang++')
    shared = ['-dynamiclib'] if sys.platform == 'darwin' else ['-shared', '-fPIC']
    suffix = '.dylib' if sys.platform == 'darwin' else '.so'
    commands, binaries = [], {}
    for tag, flags in (('', ['-O3']), ('-ubsan', ['-O1', '-g', '-fsanitize=undefined',
                                               '-fsanitize-undefined-trap-on-error', '-fno-sanitize-recover=all'])):
        for kind in ('producer', 'checker'):
            target = out / (kind + tag + suffix)
            command = [cxx, '-std=c++17', '-Wall', '-Wextra', '-Werror', '-pthread', *shared,
                       *flags, str(HERE / (kind + '.cpp')), '-o', str(target)]
            subprocess.run(command, check=True)
            commands.append(command)
            binaries[target.name] = hashlib.sha256(target.read_bytes()).hexdigest()
    sources = [p for pattern in ('*.cpp', '*.h', '*.py') for p in HERE.glob(pattern)]
    result = {'commands': commands, 'binaries': binaries,
              'sources': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
              'compiler': subprocess.check_output([cxx, '--version'], text=True),
              'platform': platform.platform(), 'architecture': platform.machine(),
              'scope': 'Current physical CPU only; separate producer/checker binaries; no GPU or other-platform validation claim.'}
    (out / 'receipt.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print('BUILD_PASS', len(binaries), 'native libraries', flush=True)


if __name__ == '__main__':
    main()
