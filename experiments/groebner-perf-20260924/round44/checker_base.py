"""Bounded affine-multiplier proofs and independently checked Boolean identities."""
import ctypes as ct
import hashlib
from pathlib import Path
import sys
import threading

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'round31'))
from quadratic import Native, U32, U64, P32, P64


def dimensions(x, y, equations):
    if any(type(v) is not int for v in (x, y, equations)) or not (
            1 <= x <= 20 and 1 <= y <= 10 and x+y <= 30 and 1 <= equations <= 128):
        raise ValueError('x 1..20; y 1..10; x+y<=30; equations 1..128')


class CheckStats(ct.Structure):
    _fields_ = [(name, U64) for name in ('branches', 'contradictions', 'enumerated_branches', 'assignments',
        'roots', 'standard', 'work', 'workspace_bytes', 'proof_bytes', 'transform_xors')]
    _fields_ += [(name, ct.c_double) for name in ('specialization', 'contradiction_check', 'enumeration', 'basis_check')]
    _fields_ += [(name, U64) for name in ('extended_contradictions', 'multiplier_parities', 'multiplier_words')]
    _fields_ += [('multiplier_check', ct.c_double)]

    def record(self):
        return {name: getattr(self, name) for name, _ in self._fields_}


class PartialCheckStats(ct.Structure):
    _fields_ = [(name, U64) for name in ('records', 'checked_rows', 'witness_parities',
        'row_xors', 'rank_sum', 'inconsistent', 'assignments', 'work', 'stack_bytes')]
    _fields_ += [('seconds', ct.c_double)]

    def record(self):
        return {name: getattr(self, name) for name, _ in self._fields_}


class Checker(Native):
    def __init__(self, x, y, equations, *, sanitizer=False, budget_test=False, partial_budget_test=False):
        dimensions(x, y, equations)
        if sum(bool(v) for v in (sanitizer, budget_test, partial_budget_test)) > 1:
            raise ValueError('select one checker test build')
        self.x, self.y, self.nvars, self.equations = x, y, x+y, equations
        self._lock, self._handle = threading.Lock(), None
        tag = '-partial-budget' if partial_budget_test else '-budget' if budget_test else '-ubsan' if sanitizer else ''
        self.path = HERE/'build'/('checker'+tag+('.dylib' if sys.platform == 'darwin' else '.so'))
        self.binary_sha256 = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.lib = lib = ct.CDLL(str(self.path))
        lib.check_stats_size.restype = U64
        if lib.check_stats_size() != ct.sizeof(CheckStats):
            raise RuntimeError('checker ABI mismatch')
        lib.check_partial_stats_size.restype = U64
        if lib.check_partial_stats_size() != ct.sizeof(PartialCheckStats):
            raise RuntimeError('partial checker metadata ABI mismatch')
        for name, result, args in (
            ('check_last_partial_stats', ct.POINTER(PartialCheckStats), []),
            ('check_coefficient_bits', U32, [ct.c_void_p]),
            ('check_create', ct.c_void_p, [U32, U32, U32]), ('check_destroy', None, [ct.c_void_p]),
            ('branch_check', ct.c_int, [ct.c_void_p, ct.c_void_p, U32, P64, U32,
                P64, U64, P64, U32, P64, U32, P32, U32, ct.POINTER(CheckStats)]),
            ('branch_evaluate', ct.c_int, [ct.c_void_p, ct.c_void_p, U32, P64, U32, U64, P64])):
            fn = getattr(lib, name)
            fn.restype, fn.argtypes = result, args
        self._handle = lib.check_create(x, y, equations)
        if not self._handle:
            raise ValueError('checker allocation or table limit')
        self.coefficient_bits = int(lib.check_coefficient_bits(self._handle))
        if self.coefficient_bits != (32 if equations <= 32 else 64):
            raise RuntimeError('checker coefficient-width mismatch')

    def certify(self, anf, roots, basis, proof):
        masks, width, coefficients = self.views(anf)
        if isinstance(proof, bytes):
            if len(proof)%8:
                raise ValueError('proof byte extent')
            proof = (U64*(len(proof)//8)).from_buffer_copy(proof)
        if not isinstance(proof, ct.Array) or proof._type_ is not U64:
            raise ValueError('uint64 proof array required')
        prefix = (1 << self.x)*((self.equations+63)//64)
        entry = 1+(self.y+1)*((self.equations+63)//64)
        if len(proof) < prefix or len(proof) > (64<<20)//8 or (len(proof)-prefix)%entry or len(roots)>256 or len(basis)>4096:
            raise ValueError('certificate extents')
        terms, offsets = [], [0]
        for row in basis:
            terms.extend(row)
            offsets.append(len(terms))
        if len(terms)>1000000 or any(type(v) is not int or not 0<=v<1<<self.nvars for v in [*roots, *terms]):
            raise ValueError('certificate mask or extent')
        rb, tb, ob = (U64*len(roots))(*roots), (U64*len(terms))(*terms), (U32*len(offsets))(*offsets)
        stats = CheckStats()
        with self._lock:
            if not self._handle:
                raise RuntimeError('checker is closed')
            code = self.lib.branch_check(self._handle, masks, width, coefficients, len(masks),
                proof, len(proof), rb, len(roots), tb, len(terms), ob, len(basis), ct.byref(stats))
            partial = self.lib.check_last_partial_stats().contents.record()
        if code == 6:
            raise ValueError('invalid packed certificate')
        if code == 8:
            raise RuntimeError('checker internal failure')
        result = {'verified': code == 0, 'code': code,
                  'backend': 'independent-tagged-affine-proof',
                  'partial_stats': partial,
                  'method': 'constant-and-affine-identities+certified-affine-space+complete-residual-enumeration+Boolean-staircase',
                  'root_count': stats.roots if code != 5 else None,
                  'standard_monomials': stats.standard if code == 0 else None,
                  'coefficient_word_bits': self.coefficient_bits, 'stats': stats.record()}
        if code:
            result['reason'] = {1: 'noncanonical basis', 2: 'invalid or repeated root',
                3: 'incomplete root list', 4: 'invalid reduced Boolean basis',
                5: 'proof budget or root limit', 7: 'nonquadratic residual',
                9: 'invalid contradiction identity or nonlinear affine consequence'}[code]
        else:
            result.update(ideal_equality=True, reduced_groebner_basis=True, solutions=list(roots))
        return result

    def evaluate(self, anf, assignment):
        masks, width, coefficients = self.views(anf)
        if type(assignment) is not int or not 0 <= assignment < 1 << self.nvars:
            raise ValueError('assignment outside ring')
        out = (U64*2)()
        with self._lock:
            if not self._handle:
                raise RuntimeError('checker is closed')
            code = self.lib.branch_evaluate(self._handle, masks, width, coefficients, len(masks), assignment, out)
        if code:
            raise ValueError('invalid equation input') if code == 6 else RuntimeError('evaluation failure')
        return out[0] | out[1]<<64

    def close(self):
        with self._lock:
            if self._handle:
                self.lib.check_destroy(self._handle)
                self._handle = None
