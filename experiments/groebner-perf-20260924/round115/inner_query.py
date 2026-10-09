"""Read inner F4 clocks under the same certified leased query boundary."""
import ctypes as C
import hashlib
import os
from pathlib import Path
import sys
import threading

HERE = Path(__file__).resolve().parent
REFERENCE_ROOT = Path(os.environ.get("GROEBNER_F4_REFERENCE_ROOT", HERE.parents[2])).resolve()
P = REFERENCE_ROOT / "experiments/groebner-perf-20260924"
sys.path.insert(0, str(P / "round112"))
sys.path.insert(0, str(P / "round110"))
from early_query import Query as EarlyQuery, abi
from native import Native


class PhaseStats(C.Structure):
    _fields_ = [(name, abi.U64) for name in
                ("preparation_ns", "f4_ns", "packing_ns", "composition_ns",
                 "finalization_ns", "total_ns")] + [
                ("completed", abi.U32), ("stage_at_exit", abi.U32)]


class InnerStats(C.Structure):
    _fields_ = [(name, abi.U64) for name in
                ("initial_ns", "pairs_ns", "matrix_ns", "candidate_ns", "final_ns",
                 "compute_ns", "compact_ns", "symbolic_ns", "column_ns", "packed_ns")]


class InnerNative(Native):
    def __init__(self, sanitized=False):
        super().__init__(sanitized)
        original = self.lib
        suffix = ("-ubsan" if sanitized else "") + (".dylib" if sys.platform == "darwin" else ".so")
        self.path = HERE / "build" / ("seeded_inner" + suffix)
        lib = C.CDLL(str(self.path))
        for name in ("seeded_compose", "seeded_produce", "seeded_view",
                     "seeded_continuation_view", "seeded_destroy", "seeded_error",
                     "seeded_stats_size", "seeded_composition_stats_size"):
            old, new = getattr(original, name), getattr(lib, name)
            new.argtypes, new.restype = old.argtypes, old.restype
        assert lib.seeded_stats_size() == original.seeded_stats_size()
        assert lib.seeded_composition_stats_size() == original.seeded_composition_stats_size()
        lib.seeded_last_phases.argtypes = []
        lib.seeded_last_phases.restype = C.POINTER(PhaseStats)
        lib.seeded_last_inner.argtypes = []
        lib.seeded_last_inner.restype = C.POINTER(InnerStats)
        self.lib = lib
        self._local = threading.local()
        raw = lib.seeded_produce

        def produce(*args):
            handle = raw(*args)
            phases = abi.fields(lib.seeded_last_phases().contents)
            assert phases["completed"] == 1
            assert phases["total_ns"] == sum(phases[name] for name in (
                "preparation_ns", "f4_ns", "packing_ns", "composition_ns", "finalization_ns"))
            inner = abi.fields(lib.seeded_last_inner().contents)
            assert inner["compute_ns"] >= sum(inner[name] for name in
                   ("initial_ns", "pairs_ns", "matrix_ns", "candidate_ns", "final_ns"))
            assert inner["matrix_ns"] >= inner["symbolic_ns"] + inner["column_ns"]
            assert inner["column_ns"] >= inner["packed_ns"]
            assert phases["f4_ns"] >= inner["compute_ns"] + inner["compact_ns"]
            self._local.samples.append((phases, inner))
            return handle

        lib.seeded_produce = produce

    def reset(self):
        self._local.samples = []

    def samples(self):
        return list(self._local.samples)


class Query(EarlyQuery):
    def __init__(self, *, sanitizer=False, **kwargs):
        super().__init__(sanitizer=sanitizer, **kwargs)
        self.native = InnerNative(sanitizer)
        self.binary_sha256[self.native.path.name] = hashlib.sha256(self.native.path.read_bytes()).hexdigest()

    def compute(self, *args, **kwargs):
        self.native.reset()
        result = super().compute(*args, **kwargs)
        seeded = [attempt for attempt in result["attempts"] if attempt["kind"] == "seeded-f4"]
        samples = self.native.samples()
        assert len(seeded) == len(samples)
        for attempt, (phase, inner) in zip(seeded, samples):
            attempt["native_phases"] = phase
            attempt["f4_inner"] = inner
        return result
