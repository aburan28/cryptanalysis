"""Per-call parity metadata with unchanged query, proof and checker boundaries."""
import ctypes as C
import hashlib
import importlib.util
from pathlib import Path
import sys
import threading

HERE = Path(__file__).resolve().parent
P = HERE.parent
spec = importlib.util.spec_from_file_location('query106_for107', P/'round106/query.py')
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
ARMS = ('f4-quotient', 'matrix-minimal', 'matrix-parity')


class ParityStats(C.Structure):
    _fields_ = [(name, abi.U64) for name in ('mode', 'selected', 'fallback_outputs',
        'fallback_bytes', 'fallback_size', 'fallback_shape', 'input_nodes', 'outputs',
        'peak_metadata_bytes', 'visited_nodes', 'parity_edges', 'leaves', 'incidences',
        'emitted_nodes', 'work')]+[('total_seconds', C.c_double)]


class Query(previous.Query):
    def __init__(self, *, sanitizer=False, arm='matrix-parity', parity_bytes=8388608,
                 parity_mode=1, **kwargs):
        if arm not in ARMS:
            raise ValueError('unknown parity witness arm')
        abi.integer(parity_bytes, 0, 1 << 64)
        abi.integer(parity_mode, 0, 2)
        self.parity_arm = arm
        self.parity_bytes, self.parity_mode = parity_bytes, parity_mode
        self._parity_local = threading.local()
        super().__init__(sanitizer=sanitizer,
            arm='f4-quotient' if arm.startswith('f4-') else 'matrix-minimal', **kwargs)
        if arm == 'matrix-parity':
            suffix = ('-ubsan' if sanitizer else '')+('.dylib' if sys.platform == 'darwin' else '.so')
            path = HERE/'build'/('parity_macaulay'+suffix)
            library = C.CDLL(str(path))
            for name in ('macaulay_layout_create', 'macaulay_layout_destroy',
                         'macaulay_layout_support', 'macaulay_apply', 'macaulay_view',
                         'macaulay_result_destroy', 'macaulay_error', 'macaulay_stats_size',
                         'macaulay_layout_stats_size'):
                new, old = getattr(library, name), getattr(self.lib, name)
                new.argtypes, new.restype = old.argtypes, old.restype
            assert library.macaulay_stats_size() == self.lib.macaulay_stats_size()
            assert library.macaulay_layout_stats_size() == self.lib.macaulay_layout_stats_size()
            library.macaulay_apply_parity.argtypes = library.macaulay_apply.argtypes+[
                abi.U32, abi.U64, C.POINTER(ParityStats)]
            library.macaulay_apply_parity.restype = C.c_void_p
            library.macaulay_parity_stats_size.restype = abi.U64
            assert library.macaulay_parity_stats_size() == C.sizeof(ParityStats)

            def apply(*args):
                stats = ParityStats()
                handle = library.macaulay_apply_parity(*args, self.parity_mode,
                    self.parity_bytes, C.byref(stats))
                self._parity_local.stats = abi.fields(stats)
                return handle

            # Keep the prior internal call signature while collecting per-call
            # metadata; each thread and each native call gets a fresh record.
            apply.argtypes, apply.restype = library.macaulay_apply.argtypes, C.c_void_p
            library.macaulay_apply = apply
            self.lib = library
            self.binary_sha256[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()

    def compute(self, *args, **kwargs):
        self._parity_local.stats = None
        result = super().compute(*args, **kwargs)
        result['parity_witness_policy'] = self.parity_arm
        if self.parity_arm == 'matrix-parity':
            for attempt in result['attempts']:
                if attempt['kind'] == 'macaulay':
                    assert self._parity_local.stats is not None
                    attempt['parity'] = self._parity_local.stats
        return result
