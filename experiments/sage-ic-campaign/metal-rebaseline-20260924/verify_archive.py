"""Check the native/CPU/Metal rebaseline receipts without running Sage."""
import hashlib
import json
import math
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


run = HERE / 'run-002'
execution = json.loads((run / 'execution.json').read_text())
assert execution['intent_sha256'] == digest(HERE / 'intent.json')
assert execution['benchmark_sha256'] == digest(ROOT / 'experiments/sage-binary-hardware/benchmark.py')
assert execution['runner_sha256'] == digest(HERE / 'run.py')
summary = json.loads((run / 'summary.json').read_text())
assert summary['complete'] and summary['failed_cell'] is None and len(summary['rows']) == 7
for index, row in enumerate(summary['rows']):
    cell = json.loads((run / f'cell-{index:02d}.json').read_text())
    parent = json.loads((run / f'cell-{index:02d}-parent.json').read_text())
    assert parent['status'] == 0
    assert cell['exact_output_agreement'] and cell['completed_points_per_call'] == row['points']
    for arm in ('sage', 'cpu', 'metal'):
        samples = cell['full_api'][arm]
        assert len(samples) == 12
        assert math.isclose(statistics.median(s['validated_seconds'] for s in samples),
                            row['full_medians_seconds'][arm], rel_tol=1e-10)
    for arm in ('cpu', 'metal'):
        ratio = row['full_medians_seconds']['sage'] / row['full_medians_seconds'][arm]
        assert math.isclose(ratio, row['full_speedup'][arm], rel_tol=1e-10)
print('PASS: seven exact native/CPU/Metal cells with twelve full-API rounds each.')
