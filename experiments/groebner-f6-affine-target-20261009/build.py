"""Bind the Python target template to a frozen compact separator binary."""
import hashlib
import json
from pathlib import Path
import platform
import subprocess

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root = HERE.parents[1]
    sources = {}
    for path in HERE.glob('*.py'):
        assert path.read_bytes() == subprocess.check_output(
            ['git', 'show', 'HEAD:' + str(path.relative_to(root))], cwd=root)
        sources[path.name] = sha(path)
    previous = HERE.parent / 'groebner-f6-boundary-compact-20261009'
    prior = json.loads((previous / 'build/receipt.json').read_text())
    for name, digest in prior['binaries'].items():
        assert sha(previous / 'build' / name) == digest
    receipt = dict(schema='f6-affine-target-build/1',
                   source_commit=subprocess.check_output(
                       ['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
                   sources=sources, predecessor=prior,
                   platform=platform.platform(), architecture=platform.machine(),
                   timing_eligible=False, qualified_speedup=None)
    output = HERE / 'build'
    output.mkdir(exist_ok=True)
    (output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('F6_AFFINE_BUILD_PASS', len(sources), flush=True)


if __name__ == '__main__':
    main()
