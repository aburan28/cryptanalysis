"""One timed first trace call in a fresh Python process."""

import importlib.util
import json
import sys
import time
from pathlib import Path


source = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location('cold_field', source)
field = importlib.util.module_from_spec(spec)
spec.loader.exec_module(field)
f = field.Onb(131)
value = f.fromCoords((1 << 130) | (1 << 101) | (1 << 64) | 31)
start = time.perf_counter_ns()
answer = f.trace(value)
elapsed = time.perf_counter_ns() - start
assert answer in (0, 1)
print(json.dumps({'source': source.name, 'cold_trace_ns': elapsed,
                  'answer': answer,
                  'cached_exponents_after': sorted(f.frobPositions)}))
