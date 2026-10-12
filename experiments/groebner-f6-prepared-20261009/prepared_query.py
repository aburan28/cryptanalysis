"""Fresh target equations over immutable prebuilt Boolean factor tables."""
import ctypes as C
import hashlib
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'groebner-f6-packed-20261009'))
from chain_fixture import Curve, GF2n, retarget
from chain_profile import coordinate, equations, s3
from packed_separator import PackedResult, STATUS, STAGE, canonical, satisfies, solve as cold_solve
from semantic_screen import point_replay

U64 = C.c_uint64
U32 = C.c_uint32


class PreparedResult(C.Structure):
    _fields_ = [('result', PackedResult)] + [(name, U64) for name in
        ('reused_factor_states', 'reused_transform_xors', 'cached_factor_words',
         'copy_ns', 'dynamic_factor_ns', 'elimination_ns')]


def pack(equations):
    offsets, terms = [0], []
    for equation in equations:
        for term in equation:
            if not isinstance(term, int) or not 0 <= term < 1 << 64:
                raise ValueError('invalid Boolean monomial')
            terms.append(term)
        offsets.append(len(terms))
    return (U64 * len(offsets))(*offsets), (U64 * max(1, len(terms)))(*terms), len(terms)


def split_case(case):
    prefix = case['equations'][:-case['n']]
    with_lifts = retarget(case, case['target_x'], require_liftable=True)
    suffix = with_lifts[len(case['equations']):]
    assert len(suffix) == 2 * case['m'] - 2
    return prefix, suffix


class PreparedLayout:
    def __init__(self, nvars, static_equations, insert_after, *, max_bag=21,
                 max_states=100_000_000, sanitized=False):
        start = time.perf_counter_ns()
        if not 0 <= nvars <= 64 or not 0 <= insert_after <= len(static_equations):
            raise ValueError('invalid static factor layout')
        suffix = '.dylib' if sys.platform == 'darwin' else '.so'
        tag = '-ubsan' if sanitized else ''
        self.path = HERE / 'build' / ('prepared_separator' + tag + suffix)
        self.lib = C.CDLL(str(self.path))
        self.lib.prepared_separator_create.argtypes = [U32, U64, U64, C.POINTER(U64),
            C.POINTER(U64), U64, U32, U64, C.POINTER(PreparedResult)]
        self.lib.prepared_separator_create.restype = C.c_void_p
        self.lib.prepared_separator_run.argtypes = [C.c_void_p, U64, U64,
            C.POINTER(U64), C.POINTER(U64), U64, C.POINTER(PreparedResult)]
        self.lib.prepared_separator_run.restype = C.c_int
        self.lib.prepared_separator_destroy.argtypes = [C.c_void_p]
        self.lib.prepared_separator_destroy.restype = None
        self.nvars, self.max_states = nvars, max_states
        self.static_equations = [list(row) for row in static_equations]
        self.insert_after = insert_after
        offsets, terms, count = pack(self.static_equations)
        result = PreparedResult()
        self.handle = self.lib.prepared_separator_create(
            nvars, len(self.static_equations), count, offsets, terms, insert_after,
            max_bag, max_states, C.byref(result))
        if not self.handle or result.result.status != 1:
            raise RuntimeError(f'prepared factor setup failed: {result.result.status}')
        self.setup_ns = time.perf_counter_ns() - start
        self.library_sha256 = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.setup = dict(static_factor_states=result.reused_factor_states,
                          static_transform_xors=result.reused_transform_xors,
                          cached_factor_words=result.cached_factor_words,
                          setup_ns=self.setup_ns, library_sha256=self.library_sha256)

    def run(self, dynamic):
        if not self.handle:
            raise ValueError('prepared factor layout is closed')
        start = time.perf_counter_ns()
        offsets, terms, count = pack(dynamic)
        result = PreparedResult()
        code = self.lib.prepared_separator_run(self.handle, len(dynamic), count,
                                               offsets, terms, self.max_states,
                                               C.byref(result))
        assert code == result.result.status and code in STATUS
        assignment = result.result.assignment if code == 1 else None
        original = (self.static_equations[:self.insert_after] + list(dynamic) +
                    self.static_equations[self.insert_after:])
        verified = None
        if assignment is not None:
            verified = all(satisfies(canonical(equation), assignment)
                           for equation in original)
            assert verified
        fields = {name: getattr(result.result, name) for name, _ in PackedResult._fields_}
        fields.update(status=STATUS[code], assignment=assignment,
                      stage=STAGE[result.result.stage], independently_verified=verified,
                      reused_factor_states=result.reused_factor_states,
                      reused_transform_xors=result.reused_transform_xors,
                      cached_factor_words=result.cached_factor_words,
                      copy_ns=result.copy_ns,
                      dynamic_factor_ns=result.dynamic_factor_ns,
                      elimination_ns=result.elimination_ns,
                      library_sha256=self.library_sha256,
                      wall_ns=time.perf_counter_ns() - start,
                      timing_eligible=False, qualified_speedup=None)
        return fields

    def close(self):
        if self.handle:
            self.lib.prepared_separator_destroy(self.handle)
            self.handle = None


class QueryContext:
    def __init__(self, case, *, max_bag=21, max_states=100_000_000,
                 sanitized=False):
        before = time.perf_counter_ns()
        self.case = case
        self.prefix, self.suffix = split_case(case)
        self.field = GF2n(case['n'])
        self.curve = Curve(self.field, case['curve_b'])
        self.auxiliary = coordinate(case['m'] * case['ell'] +
                                    (case['m'] - 3) * case['n'], case['n'])
        self.summand = coordinate((case['m'] - 1) * case['ell'], case['ell'])
        self.max_bag, self.max_states = max_bag, max_states
        self.layout = PreparedLayout(case['nvars'], self.prefix + self.suffix,
                                     len(self.prefix), max_bag=max_bag,
                                     max_states=max_states, sanitized=sanitized)
        self.setup_ns = time.perf_counter_ns() - before

    def run(self, target_x, arm):
        start = time.perf_counter_ns()
        dynamic = equations(self.field, s3(self.field, self.case['curve_b'],
                                           self.auxiliary, self.summand,
                                           {0: target_x}))
        if arm == 'cold':
            result = cold_solve(self.case['nvars'],
                                self.prefix + dynamic + self.suffix,
                                max_bag=self.max_bag, max_states=self.max_states)
        elif arm == 'prepared':
            result = self.layout.run(dynamic)
        else:
            raise ValueError('unknown arm')
        point_verified = (point_replay(self.curve, result['assignment'],
                                       self.case['m'], self.case['ell'], target_x)
                          if result['assignment'] is not None else None)
        elapsed = time.perf_counter_ns() - start
        return dict(arm=arm, target_x=target_x, status=result['status'],
                    assignment=result['assignment'], point_verified=point_verified,
                    equation_verified=result['independently_verified'],
                    online_ns=elapsed, solver=result,
                    timing_eligible=False, qualified_speedup=None)

    def close(self):
        self.layout.close()
