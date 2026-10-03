"""Build and replay the portable CPU kernel with an independent field oracle.

This component test needs a C++17 compiler, not Sage. Translated execution
is recorded separately from native hardware; no full-Sage claim is made.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import subprocess
import sys
import traceback


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arch', choices=('native', 'arm64', 'x86_64'), default='native')
    parser.add_argument('--ubsan', action='store_true')
    parser.add_argument('--source', type=Path, help='directory containing the CPU source and header')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.arch != 'native' and sys.platform != 'darwin':
        parser.error('explicit --arch uses Apple clang; use --arch native on other hosts')
    args.out.mkdir(parents=True, exist_ok=False)
    here = Path(__file__).resolve().parent
    source = (args.source or here/'compatibility-20260928/sources').resolve()
    files = [source/'binary_hardware_cpu.cpp', source/'binary_hardware_native.h', here/'native_selftest.cpp']
    binary = (args.out/'native_selftest').resolve()
    compiler = shlex.split(os.environ.get('CXX', 'c++'))
    command = compiler + ['-std=c++17', '-O2', '-pthread', '-I'+str(source),
                          str(source/'binary_hardware_cpu.cpp'), str(here/'native_selftest.cpp'), '-o', str(binary)]
    if args.arch != 'native':
        command += ['-arch', args.arch]
    if args.ubsan:
        command += ['-fsanitize=undefined', '-fno-sanitize-recover=all']
    translated = sys.platform == 'darwin' and platform.machine() == 'arm64' and args.arch == 'x86_64'
    report = {'status': 'fail', 'platform': platform.platform(), 'host_architecture': platform.machine(),
              'target_architecture': platform.machine() if args.arch == 'native' else args.arch,
              'execution': 'rosetta' if translated else 'native', 'ubsan': args.ubsan,
              'scope': 'portable CPU kernel only; not full Sage or a performance measurement',
              'source_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
              'command': command}
    try:
        report['compiler'] = subprocess.check_output(compiler+['--version'], text=True, timeout=30)
        built = subprocess.run(command, capture_output=True, text=True, timeout=120)
        (args.out/'build.txt').write_text(built.stdout+built.stderr)
        report['build_exit_code'] = built.returncode
        if built.returncode == 0:
            report['binary_sha256'] = hashlib.sha256(binary.read_bytes()).hexdigest()
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=60)
            (args.out/'run.txt').write_text(run.stdout+run.stderr)
            report['run_exit_code'] = run.returncode
            if run.returncode == 0:
                report['result'] = json.loads(run.stdout)
                if report['result']['status'] == 'pass':
                    report['status'] = 'pass'
    except Exception:
        report['error'] = traceback.format_exc()
    (args.out/'receipt.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))
    return 0 if report['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
