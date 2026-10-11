"""Build only the bounded tiled-shader correctness driver; no timing run."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def main():
    if sys.platform != 'darwin': raise SystemExit('Metal requires macOS')
    out = HERE/'build'
    out.mkdir(exist_ok=True)
    commands, binaries = [], {}
    for tag, flags in (('', ['-O3']), ('-ubsan', ['-O1', '-g', '-fsanitize=undefined',
                       '-fsanitize-undefined-trap-on-error', '-fno-sanitize-recover=all'])):
        binary = out/('test-tiles'+tag)
        command = ['clang++', '-std=c++17', *flags, '-Wall', '-Wextra', '-Werror',
                   '-fobjc-arc', '-framework', 'Foundation', '-framework', 'Metal',
                   str(HERE/'test_tiles.mm'), '-o', str(binary)]
        subprocess.run(command, check=True)
        commands.append(command)
        binaries[binary.name] = hashlib.sha256(binary.read_bytes()).hexdigest()
    receipt = {'commands': commands, 'binaries': binaries,
               'compiler': subprocess.check_output(['clang++','--version'], text=True),
               'source_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
                   (HERE/'test_tiles.mm', HERE/'tiled_truth.metal', HERE/'build_tiles.py')},
               'scope': 'Device kernel correctness only; timings and IC/GPU speedup null'}
    (out/'tile-build-receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')


if __name__ == '__main__': main()
