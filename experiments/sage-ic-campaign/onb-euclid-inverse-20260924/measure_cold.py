"""Alternating fresh-process first point recovery for parent and candidate."""

import json
import statistics
import subprocess
import sys
from pathlib import Path


here = Path(__file__).resolve().parent
raw = {'valid': {'parent': [], 'candidate': []},
       'invalid': {'parent': [], 'candidate': []}}
for outcome in ('valid', 'invalid'):
    for i in range(7):
        for variant in (('parent', 'candidate') if i % 2 == 0 else
                        ('candidate', 'parent')):
            result = subprocess.check_output([
                sys.executable, str(here / 'cold_public.py'), variant, outcome], text=True)
            raw[outcome][variant].append(json.loads(result))
medians = {outcome: {variant: statistics.median(row['cold_ns'] for row in rows)
                     for variant, rows in groups.items()} for outcome, groups in raw.items()}
print(json.dumps({'raw': raw, 'median_ns': medians}, indent=2))
