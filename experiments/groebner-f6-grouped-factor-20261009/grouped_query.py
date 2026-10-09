"""Exact grouped static factors with the existing fresh message-query ABI."""
import ctypes as C
import hashlib
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'groebner-f6-message-20261009'))
from message_query import MessageLayout, MessageResult, U32, U64, pack  # noqa: E402


class GroupedLayout(MessageLayout):
    def __init__(self, nvars, static_equations, prefix_equations, group_rows,
                 boundary_mask, *, max_bag=24, max_states=200_000_000,
                 sanitized=False):
        start = time.perf_counter_ns()
        suffix = '.dylib' if sys.platform == 'darwin' else '.so'
        self.path = HERE / 'build' / ('grouped_separator' +
                                    ('-ubsan' if sanitized else '') + suffix)
        self.lib = C.CDLL(str(self.path))
        self.lib.grouped_message_separator_create.argtypes = [
            U32, U64, U64, C.POINTER(U64), C.POINTER(U64), U64, U32,
            U64, U32, U64, C.POINTER(MessageResult)]
        self.lib.grouped_message_separator_create.restype = C.c_void_p
        self.lib.message_separator_run.argtypes = [C.c_void_p, U64, U64,
            C.POINTER(U64), C.POINTER(U64), U64, C.POINTER(MessageResult)]
        self.lib.message_separator_run.restype = C.c_int
        self.lib.message_separator_destroy.argtypes = [C.c_void_p]
        self.lib.message_separator_destroy.restype = None
        self.static_equations = [list(row) for row in static_equations]
        self.max_states, self.boundary_mask = max_states, boundary_mask
        offsets, terms, count = pack(self.static_equations)
        result = MessageResult()
        self.handle = self.lib.grouped_message_separator_create(
            nvars, len(self.static_equations), count, offsets, terms,
            prefix_equations, group_rows, boundary_mask,
            max_bag, max_states, C.byref(result))
        if not self.handle or result.result.status != 1:
            raise RuntimeError(f'grouped setup failed: {result.result.status}')
        self.setup_ns = time.perf_counter_ns() - start
        self.library_sha256 = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.setup = dict(setup_ns=self.setup_ns,
            factor_states=result.setup_factor_states,
            elimination_states=result.setup_elimination_states,
            residual_factor_words=result.residual_factor_words,
            cached_witness_words=result.cached_witness_words,
            prefix_equations=prefix_equations, group_rows=group_rows,
            library_sha256=self.library_sha256)


class GroupedContext:
    def __init__(self, case, runtime, *, max_bag, max_states=200_000_000,
                 sanitized=False):
        start = time.perf_counter_ns()
        self.case, self.runtime = case, runtime
        self.field = runtime['GF2n'](case['n'])
        self.curve = runtime['Curve'](self.field, case['curve_b'])
        prefix, suffix = runtime['split_case'](case)
        self.static = prefix + suffix
        m, ell, n = case['m'], case['ell'], case['n']
        self.auxiliary = runtime['coordinate'](m * ell + (m - 3) * n, n)
        self.summand = runtime['coordinate']((m - 1) * ell, ell)
        boundary = 0
        for mask in [*self.auxiliary, *self.summand]:
            boundary |= mask
        self.boundary_mask = boundary
        self.layout = GroupedLayout(
            case['nvars'], self.static, len(prefix), n, boundary,
            max_bag=max_bag, max_states=max_states, sanitized=sanitized)
        self.setup_ns = time.perf_counter_ns() - start

    def run(self, target_x):
        start = time.perf_counter_ns()
        dynamic = self.runtime['equations'](
            self.field, self.runtime['s3'](
                self.field, self.case['curve_b'], self.auxiliary,
                self.summand, {0: target_x}))
        result = self.layout.run(dynamic)
        point_verified = (self.runtime['point_replay'](
            self.curve, result['assignment'], self.case['m'],
            self.case['ell'], target_x)
            if result['assignment'] is not None else None)
        return dict(target_x=target_x, status=result['status'],
                    assignment=result['assignment'],
                    equation_verified=result['independently_verified'],
                    point_verified=point_verified,
                    online_ns=time.perf_counter_ns() - start,
                    native=result)

    def close(self):
        self.layout.close()
