"""Rebaseline installed CPU/Metal plans against native NTL Sage Frobenius."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
HARDWARE = ROOT / 'experiments/sage-binary-hardware'
sys.path.insert(0, str(HARDWARE))
from benchmark import summarize


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    intent = json.loads((HERE / 'intent.json').read_text())
    source = ROOT / 'third_party/sage-binary/src/sage/schemes/elliptic_curves'
    installed = (ROOT / 'third_party/sage-binary/local/var/lib/sage/venv-python3.14'
                 '/lib/python3.14/site-packages/sage/schemes/elliptic_curves')
    for name, digest in intent['source_sha256'].items():
        path = installed / name if name.endswith(('.so', '.dylib')) else source / name
        if sha(path) != digest:
            raise AssertionError(f'source changed after freezing intent: {path}')
    out = args.out
    out.mkdir(parents=True, exist_ok=False)
    (out / 'execution.json').write_text(json.dumps({
        'intent_sha256': sha(HERE / 'intent.json'),
        'benchmark_sha256': sha(HARDWARE / 'benchmark.py'),
        'runner_sha256': sha(__file__),
        'python': sys.executable,
        'installed_backend': True,
    }, indent=2) + '\n')
    env = os.environ.copy()
    env['SAGE_BINARY_USE_INSTALLED'] = '1'
    rows = []
    for i, case in enumerate(intent['cases']):
        path = out / f'cell-{i:02d}.json'
        command = [sys.executable, str(HARDWARE / 'benchmark.py'), '--worker',
                   '--out', str(path), '--phase', 'rebaseline', '--seed', str(case['seed']),
                   '--degree', str(case['degree']), '--points', str(case['points']),
                   '--power', str(case['power'])]
        started = time.perf_counter()
        status = None
        with (out / f'cell-{i:02d}.log').open('w') as log:
            try:
                completed = subprocess.run(command, env=env, stdout=log,
                                           stderr=subprocess.STDOUT, timeout=300)
                status = completed.returncode
            except subprocess.TimeoutExpired:
                status = 'timeout'
        (out / f'cell-{i:02d}-parent.json').write_text(json.dumps({
            'case': case, 'command': command, 'status': status,
            'parent_seconds': time.perf_counter() - started,
        }, indent=2) + '\n')
        if status != 0:
            print(f'FAILED cell {i}: {status}', flush=True)
            break
        row = summarize(json.loads(path.read_text()))
        rows.append(row)
        (out / 'summary.json').write_text(json.dumps({
            'rows': rows, 'complete': len(rows) == len(intent['cases']),
            'failed_cell': None if len(rows) == len(intent['cases']) else len(rows),
        }, indent=2) + '\n')
        print(f"GF(2^{case['degree']}) {case['points']} p={case['power']}: "
              f"CPU {row['full_speedup']['cpu']:.3f}x, "
              f"Metal {row['full_speedup']['metal']:.3f}x vs native Sage; "
              f"Metal/CPU {row['full_gpu_speedup_vs_native_cpu']:.3f}x", flush=True)
    if len(rows) != len(intent['cases']):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
