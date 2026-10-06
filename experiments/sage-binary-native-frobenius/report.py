"""Recompute suite estimates and paired-round bootstrap intervals from raw cells."""
import json
import math
import random
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
rng = random.Random(20260924)
report = {'bootstrap_samples': 10000, 'seed': 20260924, 'suites': {}}
for suite in ('primary', 'confirmation'):
    rows = [json.loads(path.read_text()) for path in
            sorted((HERE / (suite + '-001')).glob('cell-*.json'))]
    cells = [[math.log(sample['seconds']['incumbent'] /
                       sample['seconds']['candidate']) for sample in row['rounds']]
             for row in rows]
    draws = sorted(math.exp(statistics.mean(
        statistics.median(rng.choices(cell, k=len(cell))) for cell in cells))
        for _ in range(report['bootstrap_samples']))
    report['suites'][suite] = {
        'geomean_speedup': math.exp(statistics.mean(statistics.median(cell)
                                                    for cell in cells)),
        'bootstrap_95': [draws[250], draws[9750]],
        'verified_outputs': sum(row['verified_outputs'] for row in rows),
        'all_outputs_exact': all(row['all_outputs_exact'] for row in rows),
    }
(HERE / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
