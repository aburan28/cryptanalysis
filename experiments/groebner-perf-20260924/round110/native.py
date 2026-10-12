"""Ownership-aware binding; native candidate production never certifies itself."""
import ctypes as C
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'round108'))
from query import abi


class CompositionStats(C.Structure):
    _fields_ = [(name, abi.U64) for name in ('work', 'seed_nodes', 'continuation_nodes',
        'combined_nodes', 'retained_nodes', 'retained_outputs')]


class SeededStats(C.Structure):
    _fields_ = [(name, abi.U64) for name in ('work', 'bridge_work', 'scan_work', 'f4_started',
        'composition_started', 'reserved_seed_nodes', 'status')]+[
        ('producer', abi.ProducerStats), ('composition', CompositionStats), ('total_seconds', C.c_double)]


class Native:
    def __init__(self, sanitized=False):
        suffix = ('-ubsan' if sanitized else '')+('.dylib' if sys.platform == 'darwin' else '.so')
        self.lib = C.CDLL(str(HERE/'build'/('seeded'+suffix)))
        v = C.POINTER(abi.ProofView)
        self.lib.seeded_compose.argtypes = [v, v, abi.U32, abi.U64, abi.U32, C.POINTER(CompositionStats), C.POINTER(abi.U32)]
        self.lib.seeded_compose.restype = C.c_void_p
        self.lib.seeded_produce.argtypes = [C.POINTER(abi.PackedInput), v, abi.U64, abi.U32, abi.U32, abi.U32, abi.U32, C.POINTER(SeededStats)]
        self.lib.seeded_produce.restype = C.c_void_p
        for name in ('seeded_view', 'seeded_continuation_view'):
            fn = getattr(self.lib, name)
            fn.argtypes, fn.restype = [C.c_void_p], v
        self.lib.seeded_destroy.argtypes, self.lib.seeded_destroy.restype = [C.c_void_p], None
        self.lib.seeded_error.argtypes, self.lib.seeded_error.restype = [], C.c_char_p
        for name, structure in [('seeded_stats_size', SeededStats), ('seeded_composition_stats_size', CompositionStats)]:
            fn = getattr(self.lib, name)
            fn.argtypes, fn.restype = [], abi.U64
            assert fn() == C.sizeof(structure)

    def compose(self, seed, continuation, originals, max_work=1000000, max_nodes=100000):
        stats, status = CompositionStats(), abi.U32()
        handle = self.lib.seeded_compose(C.byref(seed.view), C.byref(continuation.view), originals,
            max_work, max_nodes, C.byref(stats), C.byref(status))
        result = dict(status={0: 'composed-unverified', 1: 'invalid', 2: 'inconclusive', 3: 'internal'}[status.value],
            stats=abi.fields(stats), proof=None)
        try:
            if handle:
                _, result['proof'] = abi.export(self.lib.seeded_view(handle).contents)
            else:
                result['reason'] = self.lib.seeded_error().decode()
        finally:
            if handle:
                self.lib.seeded_destroy(handle)
        return result
