"""Opt-in early proof compression under the unchanged leased query boundary."""
import ctypes as C
import hashlib
from pathlib import Path
import sys
import threading

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'round111'))
from seeded_query import Query as PreviousQuery, abi
from query import ParityStats, BlockStats


class EarlyStats(C.Structure):
    _fields_ = [(name, abi.U64) for name in ('mode', 'attempted', 'active_nodes',
        'bound_checks', 'bound_selected', 'bound_fallback', 'prune_visits')]


class Query(PreviousQuery):
    def __init__(self, *, sanitizer=False, early_mode=1, **kwargs):
        abi.integer(early_mode, 0, 2)
        self.early_mode = early_mode
        self._early_local = threading.local()
        super().__init__(sanitizer=sanitizer, **kwargs)
        suffix = ('-ubsan' if sanitizer else '')+('.dylib' if sys.platform == 'darwin' else '.so')
        path = HERE/'build'/('early_macaulay'+suffix)
        lib = C.CDLL(str(path))
        for name in ('macaulay_layout_create', 'macaulay_layout_destroy',
                     'macaulay_layout_support', 'macaulay_apply', 'macaulay_view',
                     'macaulay_result_destroy', 'macaulay_error', 'macaulay_stats_size',
                     'macaulay_layout_stats_size'):
            old, new = getattr(self.lib, name), getattr(lib, name)
            new.argtypes, new.restype = old.argtypes, old.restype
        for name, structure in [('macaulay_early_stats_size', EarlyStats),
                                ('macaulay_parity_stats_size', ParityStats),
                                ('macaulay_block_stats_size', BlockStats)]:
            fn = getattr(lib, name)
            fn.argtypes, fn.restype = [], abi.U64
            assert fn() == C.sizeof(structure)
        assert lib.macaulay_stats_size() == self.lib.macaulay_stats_size()
        assert lib.macaulay_layout_stats_size() == self.lib.macaulay_layout_stats_size()
        lib.macaulay_apply_early.argtypes = lib.macaulay_apply.argtypes+[
            abi.U32, abi.U64, C.POINTER(ParityStats), abi.U32, abi.U64, C.POINTER(BlockStats),
            abi.U32, C.POINTER(EarlyStats)]
        lib.macaulay_apply_early.restype = C.c_void_p

        def apply(*args):
            parity, block, early = ParityStats(), BlockStats(), EarlyStats()
            handle = lib.macaulay_apply_early(*args, self.parity_mode, self.parity_bytes,
                C.byref(parity), self.block_bits, self.table_bytes, C.byref(block),
                self.early_mode, C.byref(early))
            self._parity_local.stats = abi.fields(parity)
            self._block_local.stats = abi.fields(block)
            self._early_local.stats = abi.fields(early)
            return handle

        apply.argtypes, apply.restype = lib.macaulay_apply.argtypes, C.c_void_p
        lib.macaulay_apply = apply
        self.lib = lib
        self.binary_sha256[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()

    def compute(self, *args, **kwargs):
        self._early_local.stats = None
        result = super().compute(*args, **kwargs)
        for attempt in result['attempts']:
            if attempt['kind'] == 'macaulay':
                assert self._early_local.stats is not None
                attempt['early'] = self._early_local.stats
        result['early_parity_mode'] = self.early_mode
        return result
