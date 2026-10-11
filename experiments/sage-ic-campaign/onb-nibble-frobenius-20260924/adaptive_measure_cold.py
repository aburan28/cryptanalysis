"""Seven alternating fresh-process measurements per variant and outcome."""

import json
import statistics
import subprocess
import sys
from pathlib import Path


here = Path(__file__).resolve().parent
raw = {'valid': {'parent': [], 'adaptive': []},
       'invalid': {'parent': [], 'adaptive': []}}
for outcome in ('valid', 'invalid'):
    for i in range(7):
        for variant in (('parent', 'adaptive') if i % 2 == 0 else
                        ('adaptive', 'parent')):
            result = subprocess.check_output([
                sys.executable, str(here / 'adaptive_cold_point.py'), variant, outcome], text=True)
            raw[outcome][variant].append(json.loads(result))
medians = {outcome: {variant: statistics.median(row['cold_ns'] for row in rows)
                     for variant, rows in groups.items()} for outcome, groups in raw.items()}
print(json.dumps({'raw': raw, 'median_ns': medians}, indent=2))
