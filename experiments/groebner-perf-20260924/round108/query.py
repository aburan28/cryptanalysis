"""Per-call parity metadata with unchanged query, proof and checker boundaries."""
import ctypes as C
import hashlib
import importlib.util
from pathlib import Path
import sys
import threading

HERE = Path(__file__).resolve().parent
P = HERE.parent
spec = importlib.util.spec_from_file_location('query107_for108', P/'round107/query.py')
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
ARMS = ('f4-quotient', 'matrix-parity', 'matrix-block4')


ParityStats = previous.ParityStats


class BlockStats(C.Structure):
    _fields_ = [(name, abi.U64) for name in ('bits', 'groups', 'fallback_index_bytes',
        'index_bytes', 'table_bytes', 'peak_payload_bytes', 'pivot_updates', 'lookups',
        'incomplete', 'fallback_table_bytes', 'builds', 'combinations', 'copied_words',
        'table_word_xors', 'applications', 'applied_word_xors', 'scalar_pivots_replaced', 'work')]


class Query(previous.Query):
    def __init__(self, *, sanitizer=False, arm='matrix-block4', parity_bytes=8388608,
                 parity_mode=1, block_bits=4, table_bytes=4194304, **kwargs):
        if arm not in ARMS:
            raise ValueError('unknown block witness arm')
        abi.integer(parity_bytes, 0, 1 << 64)
        abi.integer(parity_mode, 0, 2)
        abi.integer(table_bytes, 0, 1 << 64)
        if type(block_bits) is not int or block_bits not in (0, 4):
            raise ValueError('block bits must be zero or four')
        self.block_arm = arm
        self.block_bits, self.table_bytes = block_bits, table_bytes
        self._block_local = threading.local()
        self.parity_bytes, self.parity_mode = parity_bytes, parity_mode
        self._parity_local = threading.local()
        super().__init__(sanitizer=sanitizer,
            arm='f4-quotient' if arm.startswith('f4-') else 'matrix-parity',
            parity_bytes=parity_bytes, parity_mode=parity_mode, **kwargs)
        if arm == 'matrix-block4':
            suffix = ('-ubsan' if sanitizer else '')+('.dylib' if sys.platform == 'darwin' else '.so')
            path = HERE/'build'/('block_macaulay'+suffix)
            library = C.CDLL(str(path))
            for name in ('macaulay_layout_create', 'macaulay_layout_destroy',
                         'macaulay_layout_support', 'macaulay_apply', 'macaulay_view',
                         'macaulay_result_destroy', 'macaulay_error', 'macaulay_stats_size',
                         'macaulay_layout_stats_size'):
                new, old = getattr(library, name), getattr(self.lib, name)
                new.argtypes, new.restype = old.argtypes, old.restype
            assert library.macaulay_stats_size() == self.lib.macaulay_stats_size()
            assert library.macaulay_layout_stats_size() == self.lib.macaulay_layout_stats_size()
            library.macaulay_apply_block.argtypes = library.macaulay_apply.argtypes+[
                abi.U32, abi.U64, C.POINTER(ParityStats), abi.U32, abi.U64, C.POINTER(BlockStats)]
            library.macaulay_apply_block.restype = C.c_void_p
            library.macaulay_parity_stats_size.restype = abi.U64
            assert library.macaulay_parity_stats_size() == C.sizeof(ParityStats)

            library.macaulay_block_stats_size.restype = abi.U64
            assert library.macaulay_block_stats_size() == C.sizeof(BlockStats)

            def apply(*args):
                stats, block = ParityStats(), BlockStats()
                handle = library.macaulay_apply_block(*args, self.parity_mode,
                    self.parity_bytes, C.byref(stats), self.block_bits, self.table_bytes, C.byref(block))
                self._parity_local.stats = abi.fields(stats)
                self._block_local.stats = abi.fields(block)
                return handle

            # Keep the prior internal call signature while collecting per-call
            # metadata; each thread and each native call gets a fresh record.
            apply.argtypes, apply.restype = library.macaulay_apply.argtypes, C.c_void_p
            library.macaulay_apply = apply
            self.lib = library
            self.binary_sha256[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()

    def compute(self, *args, **kwargs):
        self._block_local.stats = None
        result = super().compute(*args, **kwargs)
        result['block_witness_policy'] = self.block_arm
        if self.block_arm == 'matrix-block4':
            for attempt in result['attempts']:
                if attempt['kind'] == 'macaulay':
                    assert self._block_local.stats is not None
                    attempt['block'] = self._block_local.stats
        return result
