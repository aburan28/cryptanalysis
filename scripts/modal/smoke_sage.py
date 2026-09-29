"""Small remote smoke calculation; writes its receipt to MODAL_JOB_OUTPUT."""
import json
import os
from pathlib import Path
import time

from sage.all import EllipticCurve, GF
from sage.schemes.elliptic_curves.binary_batch import add_pairs


field = GF(2**31, "smoke_z", impl="ntl")
curve = EllipticCurve(field, [1, 1, 0, 0, 1])
point = next(curve.lift_x(field.from_integer(i), all=True)[0]
             for i in range(2, 100) if curve.lift_x(field.from_integer(i), all=True))
start = time.perf_counter_ns()
batch_result = add_pairs(curve, [(point, point)])[0]
elapsed_ns = time.perf_counter_ns() - start
assert batch_result == point + point
out = Path(os.environ["MODAL_JOB_OUTPUT"])
out.mkdir(parents=True, exist_ok=True)
(out / "smoke.json").write_text(json.dumps({
    "status": "verified", "field_size": 2**31,
    "operation": "one batch point doubling", "operation_ns": elapsed_ns,
}, indent=2, sort_keys=True) + "\n")
