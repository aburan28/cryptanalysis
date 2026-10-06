"""Alternating fresh-process cold point-recovery measurements."""

import json
import statistics
import subprocess
import sys
from pathlib import Path


here = Path(__file__).resolve().parent
raw = {'valid': {'incumbent': [], 'candidate': []},
       'invalid': {'incumbent': [], 'candidate': []}}
for outcome in ('valid', 'invalid'):
    for i in range(7):
        for variant in (('incumbent', 'candidate') if i % 2 == 0 else
                        ('candidate', 'incumbent')):
            result = subprocess.check_output([
                sys.executable, str(here / 'cold_point.py'), variant, outcome], text=True)
            raw[outcome][variant].append(json.loads(result))
medians = {outcome: {variant: statistics.median(
    row['cold_point_from_x_ns'] for row in runs)
    for variant, runs in groups.items()} for outcome, groups in raw.items()}
print(json.dumps({'raw': raw, 'median_ns': medians}, indent=2))
