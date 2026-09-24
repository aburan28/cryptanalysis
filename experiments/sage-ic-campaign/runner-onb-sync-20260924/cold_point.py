"""One first runner-style point recovery in a fresh process."""

import json
import sys
import time

from common import old_curves, new_curves, OldRunnerField, NewRunnerField


variant, outcome = sys.argv[1:]
coords = {True: 2104348147882011174353649023374544053855,
          False: 2028981750298864234240433540056293830655}
is_valid = outcome == 'valid'
field_class, curve_class = (OldRunnerField, old_curves.Curve) if variant == 'incumbent' else \
    (NewRunnerField, new_curves.Curve)
f = field_class(131)
c = curve_class(f)
x = f.fromCoords(coords[is_valid])
start = time.perf_counter_ns()
point = c.pointFromX(x)
elapsed = time.perf_counter_ns() - start
assert (point is not None) == is_valid
print(json.dumps({'variant': variant, 'outcome': outcome,
                  'cold_point_from_x_ns': elapsed,
                  'cached_exponents_after': sorted(f.frobPositions)
                  if hasattr(f, 'frobPositions') else []}))
