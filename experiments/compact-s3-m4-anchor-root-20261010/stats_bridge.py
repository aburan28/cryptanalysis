"""Incremental CryptoMiniSat assumptions plus exact last-call counters."""

from __future__ import annotations

import ctypes
from pathlib import Path

from cmsat_native import CBool, CLit, IncrementalSolver

STATS_LIBRARY = Path(__file__).with_name("libq1427_cmsat_stats.dylib")


class StatsSolver(IncrementalSolver):
    def __init__(self, variables):
        super().__init__(variables)
        self.stats = ctypes.CDLL(str(STATS_LIBRARY))
        for key in ("conflicts", "propagations", "decisions"):
            fn = getattr(self.stats, "q1427_last_" + key)
            fn.argtypes = [ctypes.c_void_p]
            fn.restype = ctypes.c_uint64
        self.lib.cmsat_solve_with_assumptions.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(CLit), ctypes.c_size_t]
        self.lib.cmsat_solve_with_assumptions.restype = CBool

    def solve_assuming(self, literals, *, seconds, conflicts):
        assert all(0 < abs(value) <= self.variables for value in literals)
        encoded = (CLit * len(literals))(*(
            CLit(((abs(value) - 1) << 1) | (value < 0))
            for value in literals))
        self.lib.cmsat_set_max_time(self.pointer, max(0.001, seconds))
        self.lib.cmsat_set_max_confl(self.pointer, conflicts)
        answer = self.lib.cmsat_solve_with_assumptions(
            self.pointer, encoded, len(literals)).x
        counters = {key: int(getattr(self.stats, "q1427_last_" + key)(
            self.pointer)) for key in ("conflicts", "propagations", "decisions")}
        if answer == 0:
            raw = self.lib.cmsat_get_model(self.pointer)
            assert raw.num_vals == self.variables
            model = {i + 1: raw.vals[i].x == 0
                     for i in range(raw.num_vals) if raw.vals[i].x != 2}
            return "SAT", model, counters
        if answer == 1:
            return "UNSAT", None, counters
        assert answer == 2
        return "BOUNDED_UNKNOWN", None, counters
