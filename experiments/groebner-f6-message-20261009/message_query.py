"""Fresh S3 targets over one exact cached static-elimination message."""
import ctypes as C
import hashlib
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'groebner-f6-prepared-20261009'))
from prepared_query import (QueryContext, PackedResult, STATUS, STAGE, U32, U64,
                            pack, canonical, satisfies, equations, s3, point_replay)


class MessageResult(C.Structure):
    _fields_ = [('result', PackedResult)] + [(name, U64) for name in
        ('setup_factor_states', 'setup_elimination_states',
         'residual_factor_words', 'cached_witness_words',
         'copy_ns', 'dynamic_factor_ns', 'query_elimination_ns')]


class MessageLayout:
    def __init__(self, nvars, static_equations, boundary_mask, *, max_bag=21,
                 max_states=100_000_000, sanitized=False):
        start = time.perf_counter_ns()
        suffix = '.dylib' if sys.platform == 'darwin' else '.so'
        self.path = HERE / 'build' / ('message_separator' +
                                     ('-ubsan' if sanitized else '') + suffix)
        self.lib = C.CDLL(str(self.path))
        self.lib.message_separator_create.argtypes = [U32, U64, U64,
            C.POINTER(U64), C.POINTER(U64), U64, U32, U64, C.POINTER(MessageResult)]
        self.lib.message_separator_create.restype = C.c_void_p
        self.lib.message_separator_run.argtypes = [C.c_void_p, U64, U64,
            C.POINTER(U64), C.POINTER(U64), U64, C.POINTER(MessageResult)]
        self.lib.message_separator_run.restype = C.c_int
        self.lib.message_separator_destroy.argtypes = [C.c_void_p]
        self.lib.message_separator_destroy.restype = None
        self.static_equations = [list(row) for row in static_equations]
        self.max_states, self.boundary_mask = max_states, boundary_mask
        offsets, terms, count = pack(self.static_equations)
        result = MessageResult()
        self.handle = self.lib.message_separator_create(
            nvars, len(self.static_equations), count, offsets, terms,
            boundary_mask, max_bag, max_states, C.byref(result))
        if not self.handle or result.result.status != 1:
            raise RuntimeError(f'message setup failed: {result.result.status}')
        self.setup_ns = time.perf_counter_ns() - start
        self.library_sha256 = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.setup = dict(setup_ns=self.setup_ns,
            factor_states=result.setup_factor_states,
            elimination_states=result.setup_elimination_states,
            residual_factor_words=result.residual_factor_words,
            cached_witness_words=result.cached_witness_words,
            library_sha256=self.library_sha256)

    def run(self, dynamic):
        if not self.handle:
            raise ValueError('message layout is closed')
        start = time.perf_counter_ns()
        offsets, terms, count = pack(dynamic)
        result = MessageResult()
        code = self.lib.message_separator_run(self.handle, len(dynamic), count,
                                               offsets, terms, self.max_states,
                                               C.byref(result))
        assert code == result.result.status and code in STATUS
        assignment = result.result.assignment if code == 1 else None
        verified = None
        if assignment is not None:
            verified = all(satisfies(canonical(row), assignment)
                           for row in self.static_equations + list(dynamic))
            assert verified
        fields = {name: getattr(result.result, name) for name, _ in PackedResult._fields_}
        fields.update(status=STATUS[code], assignment=assignment,
                      stage=STAGE[result.result.stage], independently_verified=verified,
                      setup_factor_states=result.setup_factor_states,
                      setup_elimination_states=result.setup_elimination_states,
                      residual_factor_words=result.residual_factor_words,
                      cached_witness_words=result.cached_witness_words,
                      copy_ns=result.copy_ns,
                      dynamic_factor_ns=result.dynamic_factor_ns,
                      query_elimination_ns=result.query_elimination_ns,
                      library_sha256=self.library_sha256,
                      wall_ns=time.perf_counter_ns() - start,
                      timing_eligible=False, qualified_speedup=None)
        return fields

    def close(self):
        if self.handle:
            self.lib.message_separator_destroy(self.handle)
            self.handle = None


class MessageContext:
    def __init__(self, case, *, sanitized=False):
        start = time.perf_counter_ns()
        self.base = QueryContext(case, sanitized=sanitized)
        boundary_mask = 0
        for variable in list(self.base.auxiliary) + list(self.base.summand):
            boundary_mask |= variable
        self.message = MessageLayout(case['nvars'],
            self.base.prefix + self.base.suffix, boundary_mask,
            sanitized=sanitized)
        self.boundary_mask = boundary_mask
        self.setup_ns = time.perf_counter_ns() - start

    def run(self, target_x, arm):
        if arm != 'message':
            return self.base.run(target_x, arm)
        start = time.perf_counter_ns()
        dynamic = equations(self.base.field,
            s3(self.base.field, self.base.case['curve_b'],
               self.base.auxiliary, self.base.summand, {0: target_x}))
        result = self.message.run(dynamic)
        verified = (point_replay(self.base.curve, result['assignment'],
                                 self.base.case['m'], self.base.case['ell'], target_x)
                    if result['assignment'] is not None else None)
        return dict(arm=arm, target_x=target_x, status=result['status'],
                    assignment=result['assignment'], point_verified=verified,
                    equation_verified=result['independently_verified'],
                    online_ns=time.perf_counter_ns() - start, solver=result,
                    timing_eligible=False, qualified_speedup=None)

    def close(self):
        self.message.close()
        self.base.close()
