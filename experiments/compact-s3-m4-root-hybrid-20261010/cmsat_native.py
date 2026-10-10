"""Small, explicit ctypes bridge to CryptoMiniSat's incremental C API."""

from __future__ import annotations

import ctypes
from pathlib import Path

LIBRARY = Path("/opt/homebrew/lib/libcryptominisat5.dylib")


class CLit(ctypes.Structure):
    _fields_ = [("x", ctypes.c_uint32)]


class CBool(ctypes.Structure):
    _fields_ = [("x", ctypes.c_uint8)]


class BoolSlice(ctypes.Structure):
    _fields_ = [("vals", ctypes.POINTER(CBool)), ("num_vals", ctypes.c_size_t)]


class IncrementalSolver:
    def __init__(self, variables, *, verbosity=0):
        self.lib = ctypes.CDLL(str(LIBRARY))
        lib = self.lib
        lib.cmsat_new.restype = ctypes.c_void_p
        lib.cmsat_free.argtypes = [ctypes.c_void_p]
        lib.cmsat_new_vars.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        lib.cmsat_add_clause.argtypes = [ctypes.c_void_p, ctypes.POINTER(CLit),
                                         ctypes.c_size_t]
        lib.cmsat_add_clause.restype = ctypes.c_bool
        lib.cmsat_add_xor_clause.argtypes = [ctypes.c_void_p,
                                             ctypes.POINTER(ctypes.c_uint),
                                             ctypes.c_size_t, ctypes.c_bool]
        lib.cmsat_add_xor_clause.restype = ctypes.c_bool
        lib.cmsat_solve.argtypes = [ctypes.c_void_p]
        lib.cmsat_solve.restype = CBool
        lib.cmsat_get_model.argtypes = [ctypes.c_void_p]
        lib.cmsat_get_model.restype = BoolSlice
        lib.cmsat_set_num_threads.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        lib.cmsat_set_verbosity.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        lib.cmsat_set_max_time.argtypes = [ctypes.c_void_p, ctypes.c_double]
        lib.cmsat_set_max_confl.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
        lib.cmsat_interrupt_asap.argtypes = [ctypes.c_void_p]
        self.pointer = lib.cmsat_new()
        assert self.pointer
        lib.cmsat_set_num_threads(self.pointer, 1)
        lib.cmsat_set_verbosity(self.pointer, verbosity)
        lib.cmsat_new_vars(self.pointer, variables)
        self.variables = variables
        self.clauses_added = 0
        self.xors_added = 0

    def close(self):
        if self.pointer:
            self.lib.cmsat_free(self.pointer)
            self.pointer = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def new_var(self):
        self.lib.cmsat_new_vars(self.pointer, 1)
        self.variables += 1
        return self.variables

    def add_clause(self, literals):
        """Input DIMACS literals numbered from 1; return satisfiable-at-root."""
        assert all(0 < abs(lit) <= self.variables for lit in literals)
        encoded = (CLit * len(literals))(*(
            CLit(((abs(lit) - 1) << 1) | (lit < 0)) for lit in literals))
        self.clauses_added += 1
        return bool(self.lib.cmsat_add_clause(self.pointer, encoded, len(literals)))

    def add_xor(self, variables, rhs):
        assert all(0 < bit <= self.variables for bit in variables)
        encoded = (ctypes.c_uint * len(variables))(
            *(bit - 1 for bit in variables))
        self.xors_added += 1
        return bool(self.lib.cmsat_add_xor_clause(
            self.pointer, encoded, len(variables), bool(rhs)))

    def load_formula(self, formula):
        assert self.variables == formula.variables
        for clause in formula.clauses:
            assert self.add_clause(clause)
        for row, rhs in formula.xors:
            assert self.add_xor(row, rhs)

    def solve(self, *, seconds, conflicts):
        self.lib.cmsat_set_max_time(self.pointer, max(0.001, seconds))
        self.lib.cmsat_set_max_confl(self.pointer, conflicts)
        answer = self.lib.cmsat_solve(self.pointer).x
        if answer == 0:
            raw = self.lib.cmsat_get_model(self.pointer)
            assert raw.num_vals == self.variables
            model = {i + 1: raw.vals[i].x == 0
                     for i in range(raw.num_vals) if raw.vals[i].x != 2}
            return "SAT", model
        if answer == 1:
            return "UNSAT", None
        assert answer == 2
        return "BOUNDED_UNKNOWN", None

    def interrupt(self):
        self.lib.cmsat_interrupt_asap(self.pointer)
