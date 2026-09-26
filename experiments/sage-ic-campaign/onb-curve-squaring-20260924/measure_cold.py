"""Collect seven fresh-process cold doubles per source."""

import json
import statistics
import subprocess
import sys
from pathlib import Path


here = Path(__file__).resolve().parent
raw = {'incumbent': [], 'candidate': []}
for _ in range(7):
    for variant in raw:
        out = subprocess.check_output([sys.executable, str(here / 'cold_dbl.py'),
                                       '--variant', variant], text=True)
        raw[variant].append(json.loads(out))
medians = {variant: statistics.median(run['cold_dbl_ns'] for run in rows)
           for variant, rows in raw.items()}
print(json.dumps({'raw': raw, 'median_ns': medians,
                  'incumbent_over_candidate': medians['incumbent'] / medians['candidate']},
                 indent=2))
