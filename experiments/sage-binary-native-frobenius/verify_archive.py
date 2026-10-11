"""Audit the native Frobenius patch and recorded timing receipts without Sage."""
import collections
import hashlib
import json
import math
import random
import shutil
import statistics
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent / 'sage-binary-batch'


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_files():
    manifest = read(HERE / 'package-manifest.json')
    for name, digest in manifest['included_sha256'].items():
        assert sha(HERE / name) == digest, name
    for name, digest in manifest['omitted_native_binaries'].items():
        assert not (HERE / name).exists(), name
        assert len(digest) == 64
    return len(manifest['included_sha256'])


def verify_patch():
    intent = read(HERE / 'intent-v1.json')
    baseline = HERE / 'baseline'
    for name, key in (('binary_batch.py', 'python_sha256'),
                      ('binary_batch_ntl.pyx', 'native_sha256')):
        assert sha(baseline / name) == intent['incumbent'][key]
    with tempfile.TemporaryDirectory(prefix='sage-native-frobenius-') as directory:
        checkout = Path(directory)
        source = checkout / 'src/sage/schemes/elliptic_curves'
        source.mkdir(parents=True)
        for name in ('binary_batch.py', 'binary_batch_ntl.pyx'):
            shutil.copy2(baseline / name, source / name)
        subprocess.run(['git', 'apply', '--check', '--whitespace=error-all',
                        str(HERE / 'native-frobenius.patch')], cwd=checkout, check=True)
        subprocess.run(['git', 'apply', str(HERE / 'native-frobenius.patch')],
                       cwd=checkout, check=True)
        for name in ('binary_batch.py', 'binary_batch_ntl.pyx'):
            assert sha(source / name) == sha(PACKAGE / 'source' / name), name


def verify_held_storage():
    storage = HERE.parent / 'sage-binary-storage'
    pilot = read(storage / 'pilot-001/summary.json')
    assert pilot['all_outputs_exact']
    assert sha(storage / 'candidate/binary_batch_ntl.pyx') == pilot['candidate_source_sha256']
    with tempfile.TemporaryDirectory(prefix='sage-storage-hold-') as directory:
        checkout = Path(directory)
        source = checkout / 'src/sage/schemes/elliptic_curves'
        source.mkdir(parents=True)
        shutil.copy2(storage / 'baseline/binary_batch_ntl.pyx',
                     source / 'binary_batch_ntl.pyx')
        subprocess.run(['git', 'apply', str(storage / 'storage-candidate.patch')],
                       cwd=checkout, check=True)
        assert sha(source / 'binary_batch_ntl.pyx') == pilot['candidate_source_sha256']
    assert math.isclose(pilot['geomean_speedup'], math.exp(statistics.mean(
        math.log(cell['speedup']) for cell in pilot['cells'])), rel_tol=1e-12)


def verify_suite(suite, rng):
    intent = read(HERE / 'intent-v1.json')
    cases = intent['evaluation'][suite + '_cases']
    directory = HERE / (suite + '-001')
    summary = read(directory / 'summary.json')
    paths = sorted(directory.glob('cell-[0-9][0-9].json'))
    assert len(paths) == len(cases) == len(summary['cells'])
    assert summary['all_outputs_exact']
    assert summary['incumbent_python_sha256'] == intent['incumbent']['python_sha256']
    assert summary['candidate_python_sha256'] == sha(PACKAGE / 'source/binary_batch.py')
    assert summary['candidate_native_sha256'] == sha(PACKAGE / 'source/binary_batch_ntl.pyx')
    logs = []
    verified = 0
    for i, path in enumerate(paths):
        row = read(path)
        case = dict(cases[i], seed=2026092481 + i + (100 if suite == 'confirmation' else 0))
        assert row['case'] == case == summary['cells'][i]['case']
        assert row['all_outputs_exact'] and len(row['rounds']) == 12
        assert collections.Counter(tuple(r['order']) for r in row['rounds']) == {
            ('incumbent', 'candidate'): 6, ('candidate', 'incumbent'): 6}
        calls = max(4, math.ceil(4096 / case['size']))
        assert row['calls_per_sample'] == calls
        assert row['verified_outputs'] == case['size'] * calls * 24
        verified += row['verified_outputs']
        cell = [math.log(r['seconds']['incumbent'] / r['seconds']['candidate'])
                for r in row['rounds']]
        logs.append(cell)
        speedup = math.exp(statistics.median(cell))
        assert math.isclose(speedup, row['speedup'], rel_tol=1e-12)
        assert math.isclose(speedup, summary['cells'][i]['speedup'], rel_tol=1e-12)
    assert verified == summary['total_verified_outputs']
    geomean = math.exp(statistics.mean(statistics.median(cell) for cell in logs))
    assert math.isclose(geomean, summary['geomean_speedup'], rel_tol=1e-12)
    draws = sorted(math.exp(statistics.mean(statistics.median(rng.choices(
        cell, k=len(cell))) for cell in logs)) for _ in range(10000))
    report = read(HERE / 'report.json')['suites'][suite]
    assert math.isclose(geomean, report['geomean_speedup'], rel_tol=1e-12)
    assert report['bootstrap_95'] == [draws[250], draws[9750]]
    assert report['verified_outputs'] == verified and report['all_outputs_exact']
    return {'suite': suite, 'cells': len(paths), 'verified_recorded_outputs': verified,
            'geomean_speedup': geomean}


def main():
    count = verify_files()
    verify_patch()
    verify_held_storage()
    rng = random.Random(20260924)
    suites = [verify_suite(name, rng) for name in ('primary', 'confirmation')]
    assert all(row['speedup'] > 1 for row in read(HERE / 'high-power-diagnostic.json'))
    print(json.dumps({'patch': 'PASS', 'packaged_files': count, 'suites': suites}, indent=2))


if __name__ == '__main__':
    main()
