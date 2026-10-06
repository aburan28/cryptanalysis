"""Bounded affine-multiplier proofs and independently checked Boolean identities."""
import ctypes as ct
import hashlib
from pathlib import Path
import sys
import threading

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'round31'))
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


class SymmetryCheckStats(ct.Structure):
    _fields_ = [(name, U64) for name in ('requested', 'enabled', 'shape_fallback', 'workspace_fallback', 'budget_fallback', 'asymmetric_fallback', 'guard_terms', 'guard_pairs', 'guard_coefficients', 'proof_pairs', 'proof_words', 'proof_mismatches', 'representatives', 'inferred_aliases', 'constant_aliases', 'multiplier_aliases', 'partial_aliases', 'enumerated_aliases', 'derived_partial_rank', 'derived_partial_assignments', 'derived_partial_inconsistent', 'work', 'workspace_bytes', 'avoided_constant_parities', 'avoided_multiplier_parities', 'avoided_assignments')]
    _fields_ += [('guard_seconds', ct.c_double)]

    def record(self):
        return {name: getattr(self, name) for name, _ in self._fields_}


TRANSFORM_MODES = {'full': 0, 'axes': 1, 'tile8': 2, 'tile16': 3, 'tile32': 4, 'hoisted': 5}


class TransformCheckStats(ct.Structure):
    _fields_ = [(name, U64) for name in ('requested_mode', 'selected_mode',
        'shape_fallback', 'symmetry_fallback', 'slices', 'word_bits',
        'full_xors', 'actual_xors', 'mirror_words', 'audit_words', 'audit_bytes', 'audit_xors')]
    _fields_ += [('seconds', ct.c_double)]

    def record(self):
        return {name: getattr(self, name) for name, _ in self._fields_}


IDENTITY_MODES = {'dense': 0, 'reduce': 1, 'packed': 2, 'local': 3,
                  'grouped': 4, 'grouped_local': 5, 'factored': 6, 'factored_local': 7}


class IdentityCheckStats(ct.Structure):
    _fields_ = [(name, U64) for name in ('mode', 'attempted_records', 'reused_records',
        'dense_equivalent_parities', 'parities', 'ands', 'accumulator_xors', 'witness_xors',
        'identity_xors', 'table_loads', 'cached_loads', 'copy_words', 'layout_bytes',
        'cache_stack_bytes', 'identity_stack_bytes', 'audit_records', 'audit_coefficients', 'audit_parities')]

    def record(self):
        return {name: getattr(self, name) for name, _ in self._fields_}


class Checker(Native):
    def __init__(self, x, y, equations, *, sanitizer=False, budget_test=False, partial_budget_test=False, symmetry=True, symmetry_budget_test=False, symmetry_workspace_test=False, symmetry_late_budget_test=False, transform="full", transform_audit_test=False, identity="dense", identity_audit_test=False):
        dimensions(x, y, equations)
        if type(identity) is not str or identity not in IDENTITY_MODES:
            raise ValueError("unknown identity mode")
        if type(transform) is not str or transform not in TRANSFORM_MODES:
            raise ValueError("unknown transform mode")
        if type(symmetry) is not bool:
            raise ValueError('symmetry must be bool')
        if sum(bool(v) for v in (sanitizer, budget_test, partial_budget_test, symmetry_budget_test, symmetry_workspace_test, symmetry_late_budget_test, transform_audit_test, identity_audit_test)) > 1:
            raise ValueError('select one checker test build')
        self.x, self.y, self.nvars, self.equations = x, y, x+y, equations
        self._lock, self._handle = threading.Lock(), None
        tag = '-identity-audit' if identity_audit_test else '-transform-audit' if transform_audit_test else '-symmetry-late-budget' if symmetry_late_budget_test else '-symmetry-workspace' if symmetry_workspace_test else '-symmetry-budget' if symmetry_budget_test else '-partial-budget' if partial_budget_test else '-budget' if budget_test else '-ubsan' if sanitizer else ''
        self.path = HERE/'build'/('checker'+tag+('.dylib' if sys.platform == 'darwin' else '.so'))
        self.binary_sha256 = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.lib = lib = ct.CDLL(str(self.path))
        lib.check_stats_size.restype = U64
        if lib.check_stats_size() != ct.sizeof(CheckStats):
            raise RuntimeError('checker ABI mismatch')
        lib.check_partial_stats_size.restype = U64
        if lib.check_partial_stats_size() != ct.sizeof(PartialCheckStats):
            raise RuntimeError('partial checker metadata ABI mismatch')
        lib.check_symmetry_stats_size.restype = U64
        if lib.check_symmetry_stats_size() != ct.sizeof(SymmetryCheckStats):
            raise RuntimeError('symmetry checker metadata ABI mismatch')
        lib.check_transform_stats_size.restype = U64
        if lib.check_transform_stats_size() != ct.sizeof(TransformCheckStats):
            raise RuntimeError("transform metadata ABI mismatch")
        lib.check_identity_stats_size.restype = U64
        if lib.check_identity_stats_size() != ct.sizeof(IdentityCheckStats):
            raise RuntimeError("identity metadata ABI mismatch")
        for name, result, args in (
            ("check_last_identity_stats", ct.POINTER(IdentityCheckStats), []),
            ("check_identity_configure", ct.c_int, [ct.c_void_p, U32]),
            ("check_last_transform_stats", ct.POINTER(TransformCheckStats), []),
            ("check_transform_configure", ct.c_int, [ct.c_void_p, U32]),
            ('check_last_symmetry_stats', ct.POINTER(SymmetryCheckStats), []),
            ('check_symmetry_configure', ct.c_int, [ct.c_void_p, U32]),
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
        self.configure_symmetry(symmetry)
        self.configure_transform(transform)
        self.configure_identity(identity)

    def configure_identity(self, mode):
        if type(mode) is not str or mode not in IDENTITY_MODES:
            raise ValueError('unknown identity mode')
        with self._lock:
            if not self._handle:
                raise RuntimeError('checker is closed')
            if self.lib.check_identity_configure(self._handle, IDENTITY_MODES[mode]):
                raise RuntimeError('identity configuration failed')

    def configure_transform(self, mode):
        if type(mode) is not str or mode not in TRANSFORM_MODES:
            raise ValueError('unknown transform mode')
        with self._lock:
            if not self._handle:
                raise RuntimeError('checker is closed')
            if self.lib.check_transform_configure(self._handle, TRANSFORM_MODES[mode]):
                raise RuntimeError('transform configuration failed')

    def configure_symmetry(self, enabled):
        if type(enabled) is not bool:
            raise ValueError('symmetry must be bool')
        with self._lock:
            if not self._handle:
                raise RuntimeError('checker is closed')
            if self.lib.check_symmetry_configure(self._handle, int(enabled)):
                raise RuntimeError('symmetry configuration failed')

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
            symmetry = self.lib.check_last_symmetry_stats().contents.record()
            transform = self.lib.check_last_transform_stats().contents.record()
            identity = self.lib.check_last_identity_stats().contents.record()
        if code == 6:
            raise ValueError('invalid packed certificate')
        if code == 8:
            raise RuntimeError('checker internal failure')
        result = {'verified': code == 0, 'code': code,
                  'backend': 'independent-grouped-identity-tagged-affine-proof',
                  'identity_check_stats': identity,
                  'transform_check_stats': transform,
                  'symmetry_check_stats': symmetry,
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
