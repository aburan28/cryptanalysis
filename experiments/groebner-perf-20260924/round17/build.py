"""Build standalone public-point replay, including a UBSan trap build."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def main():
    output = HERE / 'build'
    output.mkdir(exist_ok=True)
    compiler = os.environ.get('CC', 'clang')
    shared = ['-dynamiclib'] if sys.platform == 'darwin' else ['-shared', '-fPIC']
    suffix = '.dylib' if sys.platform == 'darwin' else '.so'
    commands, binaries = [], {}
    for tag, flags in (('', ['-O3']), ('-ubsan', ['-O1', '-g', '-fsanitize=undefined',
                      '-fsanitize-undefined-trap-on-error', '-fno-sanitize-recover=all'])):
        path = output / ('replay' + tag + suffix)
        command = [compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', *shared, *flags,
                   str(HERE / 'replay.c'), '-o', str(path)]
        subprocess.run(command, check=True)
        commands.append(command)
        binaries[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    sources = [HERE / 'replay.c', HERE.parent.parent / 'pdp-degree-heuristics/pdpkernel.c']
    (output / 'receipt.json').write_text(json.dumps({
        'commands': commands, 'binaries': binaries,
        'compiler': subprocess.check_output([compiler, '--version'], text=True),
        'source_sha256': {str(p.relative_to(HERE.parents[2])): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in sources}}, indent=2) + '\n')


if __name__ == '__main__':
    main()
