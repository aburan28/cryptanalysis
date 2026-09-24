"""Collect paired first-use and allocation measurements in fresh processes."""

import json
import statistics
import subprocess
import sys
from pathlib import Path


here = Path(__file__).resolve().parent
sources = {'incumbent': here / 'baseline/field.py',
           'candidate': here.parents[2] / 'ecc2k130/codegen/field.py'}
raw = {name: [] for name in sources}
for _ in range(5):
    for name, source in sources.items():
        out = subprocess.check_output([sys.executable, str(here / 'cold_memory.py'),
                                       '--field', str(source)], text=True)
        raw[name].append(json.loads(out))
traced = {}
for name, source in sources.items():
    out = subprocess.check_output([sys.executable, str(here / 'cold_memory.py'),
                                   '--field', str(source), '--trace-memory'], text=True)
    traced[name] = json.loads(out)
medians = {}
for name, runs in raw.items():
    medians[name] = {k: statistics.median(run['first_frob_ns'][str(k)] for run in runs)
                     for k in (1, 2)}
print(json.dumps({'raw': raw, 'median_first_frob_ns': medians,
                  'traced_memory': traced}, indent=2))
