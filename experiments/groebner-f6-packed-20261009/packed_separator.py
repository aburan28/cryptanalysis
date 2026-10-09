"""Bounded packed-factor Boolean solver with independent equation replay."""
import ctypes as C
import hashlib
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'groebner-f6-20261008'))
from separator import canonical, satisfies

U64 = C.c_uint64
U32 = C.c_uint32
STATUS = {1: 'satisfiable', 2: 'unsatisfiable', 3: 'width-cap',
          4: 'state-cap', 5: 'invalid'}
STAGE = {0: 'none', 1: 'factor-construction', 2: 'elimination',
         3: 'reconstruction', 4: 'allocation'}


class PackedResult(C.Structure):
    _fields_ = [(name, U64) for name in
                ('status', 'assignment', 'width', 'bag_variables', 'stage',
                 'factor_states', 'elimination_states', 'transform_xors',
                 'membership_tests', 'eliminated', 'peak_factor_words',
                 'witness_words')]


def solve(nvars, equations, *, max_bag=21, max_states=100_000_000,
          sanitized=False, library=None):
    start = time.perf_counter_ns()
    if not 0 <= nvars <= 64 or not 0 <= max_bag <= 24 or not 0 <= max_states <= 200_000_000:
        raise ValueError('invalid ring or resource cap')
    offsets = [0]
    terms = []
    for equation in equations:
        for term in equation:
            if not isinstance(term, int) or not 0 <= term < 1 << 64:
                raise ValueError('invalid Boolean monomial')
            terms.append(term)
        offsets.append(len(terms))
    offset_buffer = (U64 * len(offsets))(*offsets)
    term_buffer = (U64 * max(1, len(terms)))(*terms)
    if library is None:
        suffix = '.dylib' if sys.platform == 'darwin' else '.so'
        tag = '-ubsan' if sanitized else ''
        library = HERE / 'build' / ('packed_separator' + tag + suffix)
    library = Path(library)
    native = C.CDLL(str(library))
    fn = native.packed_separator_solve
    fn.argtypes = [U32, U64, U64, C.POINTER(U64), C.POINTER(U64),
                   U32, U64, C.POINTER(PackedResult)]
    fn.restype = C.c_int
    result = PackedResult()
    code = fn(nvars, len(equations), len(terms), offset_buffer, term_buffer,
              max_bag, max_states, C.byref(result))
    assert code == result.status and code in STATUS
    assignment = result.assignment if code == 1 else None
    independently_verified = None
    if assignment is not None:
        independently_verified = all(satisfies(canonical(equation), assignment)
                                     for equation in equations)
        assert independently_verified
    fields = {name: getattr(result, name) for name, _ in result._fields_}
    fields.update(status=STATUS[code], assignment=assignment,
                  stage=STAGE[result.stage], independently_verified=independently_verified,
                  library_sha256=hashlib.sha256(library.read_bytes()).hexdigest(),
                  wall_ns=time.perf_counter_ns() - start,
                  timing_eligible=False, qualified_speedup=None)
    return fields
