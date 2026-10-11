"""First public-ONB point recovery in a fresh Python process."""

import importlib.util
import json
import sys
import time
from pathlib import Path


here = Path(__file__).resolve().parent
root = here.parents[2]
variant, outcome = sys.argv[1:]
source = here / 'baseline/field.py' if variant == 'parent' else \
    root / 'ecc2k130/codegen/field.py'
spec = importlib.util.spec_from_file_location('field', source)
field = importlib.util.module_from_spec(spec)
spec.loader.exec_module(field)
sys.modules['field'] = field
spec = importlib.util.spec_from_file_location('curves', root / 'ecc2k130/codegen/curves.py')
curves = importlib.util.module_from_spec(spec)
spec.loader.exec_module(curves)
f = field.Onb(131)
c = curves.Curve(f)
coords = {'valid': 2104348147882011174353649023374544053855,
          'invalid': 2028981750298864234240433540056293830655}
x = f.fromCoords(coords[outcome])
start = time.perf_counter_ns()
result = c.pointFromX(x)
elapsed = time.perf_counter_ns() - start
assert (result is not None) == (outcome == 'valid')
print(json.dumps({'variant': variant, 'outcome': outcome, 'cold_ns': elapsed,
                  'cached_exponents_after': sorted(f.frobPositions)}))
