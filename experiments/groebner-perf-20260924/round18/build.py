"""Build a separately implemented packed evaluator with frozen exact basis checks."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REFERENCE = HERE.parent / 'round15/reference/boolean_certificate.cpp'
PINNED = '2f0a9df64e77edf2d24d3946b7e52cef8323c2a2c2bcc88726215941edd7d697'


def main():
    source = REFERENCE.read_text()
    if hashlib.sha256(source.encode()).hexdigest() != PINNED:
        raise ValueError('basis-check reference changed')
    output = HERE / 'build'
    output.mkdir(exist_ok=True)
    helpers, _ = source.split('extern "C" int boolean_certificate(', 1)
    checks = source.split('        out->roots = alive;', 1)[1].split(
        '    } catch (const std::invalid_argument&)', 1)[0]
    (output / 'certificate_helpers.inc').write_text(helpers)
    (output / 'basis_checks.inc').write_text('        out->roots = alive;' + checks)
    compiler = os.environ.get('CXX', 'clang++')
    shared = ['-dynamiclib'] if sys.platform == 'darwin' else ['-shared', '-fPIC']
    suffix = '.dylib' if sys.platform == 'darwin' else '.so'
    commands, binaries = [], {}
    for tag, flags in (('', ['-O3']), ('-ubsan', ['-O1', '-g', '-fsanitize=undefined',
                       '-fsanitize-undefined-trap-on-error', '-fno-sanitize-recover=all'])):
        path = output / ('packed-verifier' + tag + suffix)
        command = [compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', *shared,
                   *flags, str(HERE / 'packed_verifier.cpp'), '-o', str(path)]
        subprocess.run(command, check=True)
        commands.append(command)
        binaries[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (output / 'receipt.json').write_text(json.dumps({
        'commands': commands, 'binaries': binaries,
        'compiler': subprocess.check_output([compiler, '--version'], text=True),
        'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in (HERE / 'packed_verifier.cpp', REFERENCE)},
        'generated_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in sorted(output.glob('*.inc'))}}, indent=2) + '\n')


if __name__ == '__main__': main()
