"""Exact reusable boundary bitplanes with fresh target-bit combination."""
import ctypes as C
import hashlib
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'groebner-f6-packed-target-20261009'))
from packed_query import PackedContext, MessageResult, PackedResult, STATUS, STAGE  # noqa: E402
from compact_query import U32, U64, canonical, satisfies, point_replay  # noqa: E402
from prepared_query import pack  # noqa: E402


class BitplaneResult(C.Structure):
    _fields_ = [('message', MessageResult)] + [(name, U64) for name in
        ('setup_static_assignments', 'setup_template_evaluations', 'plane_words',
         'query_xor_words', 'query_and_words', 'query_ns')]


class BitplaneLayout:
    def __init__(self, nvars, static_equations, boundary_mask, target_bits,
                 template_rows, *, max_bag=21, max_states=100_000_000,
                 sanitized=False):
        start = time.perf_counter_ns()
        if not 1 <= target_bits <= 31 or len(template_rows) != target_bits * (target_bits + 1):
            raise ValueError('template must have one field-width row block per target bit')
        suffix = '.dylib' if sys.platform == 'darwin' else '.so'
        self.path = HERE / 'build' / ('bitplane_separator' +
                                     ('-ubsan' if sanitized else '') + suffix)
        self.lib = C.CDLL(str(self.path))
        ptr = C.POINTER(U64)
        self.lib.bitplane_separator_create.argtypes = [
            U32, U64, U64, ptr, ptr, U64, U32, U64, U32, U32,
            U64, ptr, ptr, C.POINTER(BitplaneResult)]
        self.lib.bitplane_separator_create.restype = C.c_void_p
        self.lib.bitplane_separator_run.argtypes = [C.c_void_p, U64, U64,
                                                     C.POINTER(BitplaneResult)]
        self.lib.bitplane_separator_run.restype = C.c_int
        self.lib.bitplane_separator_destroy.argtypes = [C.c_void_p]
        self.lib.bitplane_separator_destroy.restype = None
        static_offsets, static_terms, static_count = pack(static_equations)
        template_offsets, template_terms, template_count = pack(template_rows)
        self.max_states, self.target_bits = max_states, target_bits
        self.boundary_mask = boundary_mask
        result = BitplaneResult()
        self.handle = self.lib.bitplane_separator_create(
            nvars, len(static_equations), static_count,
            static_offsets, static_terms, boundary_mask, max_bag, max_states,
            target_bits, target_bits, template_count,
            template_offsets, template_terms, C.byref(result))
        if not self.handle or result.message.result.status != 1:
            raise RuntimeError(f'bitplane setup failed: {result.message.result.status}')
        self.setup_ns = time.perf_counter_ns() - start
        self.library_sha256 = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.setup = dict(setup_ns=self.setup_ns,
            static_assignments=result.setup_static_assignments,
            template_evaluations=result.setup_template_evaluations,
            plane_words=result.plane_words,
            factor_states=result.message.setup_factor_states,
            elimination_states=result.message.setup_elimination_states,
            residual_factor_words=result.message.residual_factor_words,
            cached_witness_words=result.message.cached_witness_words,
            library_sha256=self.library_sha256)

    def run(self, target_x):
        if not self.handle:
            raise ValueError('bitplane layout is closed')
        if not isinstance(target_x, int) or not 0 <= target_x < 1 << self.target_bits:
            raise ValueError('target abscissa outside the field encoding')
        start = time.perf_counter_ns()
        result = BitplaneResult()
        code = self.lib.bitplane_separator_run(self.handle, target_x,
                                                self.max_states, C.byref(result))
        assert code == result.message.result.status and code in STATUS
        assignment = result.message.result.assignment if code == 1 else None
        fields = {name: getattr(result.message.result, name)
                  for name, _ in PackedResult._fields_}
        fields.update(status=STATUS[code], assignment=assignment,
                      stage=STAGE[result.message.result.stage],
                      setup_factor_states=result.message.setup_factor_states,
                      setup_elimination_states=result.message.setup_elimination_states,
                      residual_factor_words=result.message.residual_factor_words,
                      cached_witness_words=result.message.cached_witness_words,
                      query_xor_words=result.query_xor_words,
                      query_and_words=result.query_and_words,
                      query_ns=result.query_ns,
                      library_sha256=self.library_sha256,
                      wall_ns=time.perf_counter_ns() - start,
                      timing_eligible=False, qualified_speedup=None)
        return fields

    def close(self):
        if self.handle:
            self.lib.bitplane_separator_destroy(self.handle)
            self.handle = None


class BitplaneContext:
    def __init__(self, case, *, sanitized=False):
        start = time.perf_counter_ns()
        self.baseline = PackedContext(case, sanitized=sanitized)
        template = self.baseline.affine.template
        rows = template.build(0)
        for bit in range(template.n):
            rows.extend(template.build(1 << bit))
        compact = self.baseline.compact
        self.index = BitplaneLayout(case['nvars'], compact.static_equations,
                                    compact.boundary_mask, template.n, rows,
                                    sanitized=sanitized)
        self.static = [canonical(row) for row in compact.static_equations]
        self.setup_ns = time.perf_counter_ns() - start

    def run(self, target_x, arm):
        if arm != 'bitplane':
            return self.baseline.run(target_x, arm)
        start = time.perf_counter_ns()
        result = self.index.run(target_x)
        solved = time.perf_counter_ns()
        assignment = result['assignment']
        verified = None
        if assignment is not None:
            verified = (all(satisfies(row, assignment) for row in self.static)
                        and self.baseline._original_s3_zero(assignment, target_x))
            assert verified
        checked = time.perf_counter_ns()
        prepared = self.baseline.prepared
        point_verified = (point_replay(prepared.curve, assignment,
                                       prepared.case['m'], prepared.case['ell'], target_x)
                          if assignment is not None else None)
        finished = time.perf_counter_ns()
        return dict(arm=arm, target_x=target_x, status=result['status'],
                    assignment=assignment, point_verified=point_verified,
                    equation_verified=verified, online_ns=finished - start,
                    native_ns=solved - start, verify_ns=checked - solved,
                    point_replay_ns=finished - checked, solver=result,
                    timing_eligible=False, qualified_speedup=None)

    def close(self):
        self.index.close()
        self.baseline.close()
