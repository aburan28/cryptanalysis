"""Measure first trace calls in alternating fresh Python processes."""

import json
import statistics
import subprocess
import sys
from pathlib import Path


here = Path(__file__).resolve().parent
root = here.parents[2]
sources = {'incumbent': here / 'baseline/field.py',
           'candidate': root / 'ecc2k130/codegen/field.py'}
raw = {'incumbent': [], 'candidate': []}
for i in range(7):
    for name in (('incumbent', 'candidate') if i % 2 == 0 else
                 ('candidate', 'incumbent')):
        result = subprocess.check_output([
            sys.executable, str(here / 'cold_trace.py'), str(sources[name])], text=True)
        raw[name].append(json.loads(result))
print(json.dumps({'raw': raw,
                  'median_ns': {name: statistics.median(
                      row['cold_trace_ns'] for row in runs)
                      for name, runs in raw.items()}}, indent=2))
