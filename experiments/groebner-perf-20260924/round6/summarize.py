"""Audit retained single-matrix screens and summarize paired CPU/GPU costs."""
import hashlib
import json
import math
from pathlib import Path
import random
import statistics

HERE = Path(__file__).resolve().parent


def main():
    manifest = json.loads((HERE / 'results/manifest.json').read_text())
    for path, expected in manifest['retained_sha256'].items():
        assert hashlib.sha256((HERE / path).read_bytes()).hexdigest() == expected, path
    reports = []
    for run in manifest['runs']:
        report = json.loads((HERE / run['result']).read_text())
        assert report['exact_rref_and_rank'] is True
        assert report['checked_matrices'] == 848
        for cell in report['cells']:
            assert cell['batch'] == 1
            assert len(cell['samples']) == 10
            assert sum(s['warmup'] for s in cell['samples']) == 1
            samples = [s for s in cell['samples'] if not s['warmup']]
            assert all(s['cpu_ms'] > 0 and s['gpu_wall_ms'] > 0 for s in samples)
            ratios = [math.log(s['cpu_ms'] / s['gpu_wall_ms']) for s in samples]
            rng = random.Random(20260925)
            boot = sorted(math.exp(statistics.mean(rng.choices(ratios, k=len(ratios))))
                          for _ in range(2000))
            reports.append({
                'run': run['result'], 'label': cell['name'],
                'actual_input': run['captured_label_mapping'].get(cell['name'], cell['name']),
                'cpu_median_ms': statistics.median(s['cpu_ms'] for s in samples),
                'gpu_wall_median_ms': statistics.median(s['gpu_wall_ms'] for s in samples),
                'paired_cpu_over_gpu': math.exp(statistics.mean(ratios)),
                'bootstrap_95': [boot[49], boot[1949]],
            })
    print(json.dumps({'audit': 'PASS', 'scope': 'matrix diagnostics only',
                      'candidate_id': None, 'IC_online_ms': None,
                      'rho_online_ms': None, 'cells': reports}, indent=2))


if __name__ == '__main__':
    main()
