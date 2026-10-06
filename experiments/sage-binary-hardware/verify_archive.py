"""Audit the portable Sage patch and preserved complete-operation receipts."""
import hashlib
import json
import math
import shutil
import statistics
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BATCH = ROOT / 'experiments/sage-binary-batch'
MANIFEST = json.loads((HERE / 'package-manifest.json').read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


assert digest(HERE / 'sage-binary-hardware.patch') == MANIFEST['hardware_patch_sha256']
with tempfile.TemporaryDirectory() as temporary:
    sage = Path(temporary)
    for name in MANIFEST['upstream_base_files']:
        dest = sage / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(BATCH / 'upstream-base' / name, dest)
    for patch in (BATCH / 'sage-binary-batch.patch', HERE / 'sage-binary-hardware.patch'):
        subprocess.run(['git', 'apply', '--check', str(patch)], cwd=sage, check=True)
        subprocess.run(['git', 'apply', str(patch)], cwd=sage, check=True)
    for name, expected in MANIFEST['patched_files'].items():
        assert digest(sage / name) == expected, name
    for name in MANIFEST['hardware_files']:
        assert (sage / name).read_bytes() == (HERE / 'source' / Path(name).name).read_bytes()

summary = json.loads((HERE / 'run-003/summary.json').read_text())
assert summary['complete'] and not summary['failures'] and len(summary['rows']) == 22
plan = json.loads((HERE / 'run-003/execution-plan.json').read_text())
assert summary['execution_plan_sha256'] == digest(HERE / 'run-003/execution-plan.json')
assert plan['loaded_artifacts']['installed']
assert plan['loaded_artifacts']['files']['module']['sha256'] == digest(HERE / 'source/binary_hardware.py')
validation = json.loads((HERE / 'installed-tests-002/validation.json').read_text())
assert validation['successful'] and validation['tests_run'] == 6
assert validation['loaded_artifacts'] == plan['loaded_artifacts']
for index, row in enumerate(summary['rows']):
    receipt = json.loads((HERE / f'run-003/cell-{index:02d}.json').read_text())
    parent = json.loads((HERE / f'run-003/cell-{index:02d}-parent.json').read_text())
    assert parent['status'] == 0
    assert receipt['loaded_artifacts'] == plan['loaded_artifacts']
    assert receipt['exact_output_agreement'] and receipt['completed_points_per_call'] == row['points']
    assert (receipt['phase'], receipt['degree'], receipt['points'], receipt['power_requested']) == (
        row['phase'], row['degree'], row['points'], row['power'])
    for arm in ('sage', 'cpu', 'metal'):
        samples = receipt['full_api'][arm]
        assert len(samples) == 12
        values = [item['validated_seconds'] for item in samples]
        assert all(math.isclose(item['validated_seconds'],
                                item['operation_seconds'] + item['verification_seconds'] + item['cleanup_seconds'],
                                rel_tol=1e-10, abs_tol=1e-10) for item in samples)
        assert math.isclose(statistics.median(values), row['full_medians_seconds'][arm], rel_tol=1e-10)
    for arm in ('cpu', 'metal'):
        ratio = row['full_medians_seconds']['sage'] / row['full_medians_seconds'][arm]
        assert math.isclose(ratio, row['full_speedup'][arm], rel_tol=1e-10)

print('PASS: hardware patch reconstructs five sources; 22 installed-build cells have exact outputs and complete 12-round timing receipts.')
