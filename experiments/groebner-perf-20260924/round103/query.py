"""Profile and compare owned proof transport without changing numerical kernels."""
from contextvars import ContextVar
import importlib.util
from pathlib import Path
import sys
import time
from capture import capture, OwnedProof

HERE = Path(__file__).resolve().parent
P = HERE.parent
spec = importlib.util.spec_from_file_location('query102_for103', P/'round102/query.py')
previous = importlib.util.module_from_spec(spec)
_path = sys.path[:]
try:
    spec.loader.exec_module(previous)
finally:
    sys.path[:] = _path
module = previous
while module is not None:
    module.HERE = HERE
    if hasattr(module, 'abi'):
        module.abi.HERE = HERE
    module = getattr(module, 'previous', None)
abi = previous.abi
PackedDescentPlan = previous.PackedDescentPlan
ARMS = ('f4-hash', 'f4-dense', 'matrix-list', 'matrix-packed')
_materialization = ContextVar('owned_proof_materialization', default=None)


class Query(previous.Query):
    def __init__(self, *, sanitizer=False, arm='matrix-packed', **kwargs):
        if arm not in ARMS:
            raise ValueError('unknown proof transport arm')
        self.transport_arm = arm
        super().__init__(sanitizer=sanitizer,
            arm=arm if arm.startswith('f4-') else 'matrix-dense', **kwargs)

    def _answer(self, view, cert, export_proof):
        start = time.perf_counter_ns()
        result = super()._answer(view, cert, False)
        basis_end = time.perf_counter_ns()
        if export_proof:
            if self.transport_arm == 'matrix-packed':
                result['proof'] = capture(view, abi.Node)
            else:
                # Preserve the reference's exact list-materialization path.
                _, result['proof'] = abi.export(view)
        end = time.perf_counter_ns()
        record = _materialization.get()
        if record is not None:
            record['calls'] += 1
            record['basis_ns'] += basis_end-start
            record['proof_ns'] += end-basis_end
            record['total_ns'] += end-start
            record['nodes'] += view.nodes if export_proof else 0
            record['outputs'] += view.rows if export_proof else 0
            if isinstance(result.get('proof'), OwnedProof):
                record['raw_payload_bytes'] += result['proof'].payload_bytes
        return result

    def compute(self, *args, **kwargs):
        record = dict(calls=0, basis_ns=0, proof_ns=0, total_ns=0,
                      nodes=0, outputs=0, raw_payload_bytes=0)
        token = _materialization.set(record)
        try:
            result = super().compute(*args, **kwargs)
            result.update(proof_transport_policy=self.transport_arm,
                          materialization=record)
            return result
        finally:
            _materialization.reset(token)
