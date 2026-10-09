"""Fill reusable packed ANF buffers for each fresh S3 target and call native."""
import ctypes as C
from pathlib import Path
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'groebner-f6-affine-target-20261009'))
from affine_query import AffineContext  # noqa: E402
from compact_query import (MessageResult, PackedResult, STATUS, STAGE, U64,
                           canonical, satisfies, point_replay)  # noqa: E402


class PackedAffineRows:
    """Reusable offsets/terms arrays; only the target's coefficients change."""

    def __init__(self, template):
        self.template = template
        self.offsets = (U64 * (template.n + 1))()
        self.capacity = max(1, template.n * len(template.universe))
        self.terms = (U64 * self.capacity)()

    def fill(self, target_x):
        if not isinstance(target_x, int) or not 0 <= target_x < 1 << self.template.n:
            raise ValueError('target abscissa outside the field encoding')
        selected = tuple(table[(target_x >> offset) & mask]
                         for offset, mask, table in self.template.groups)
        count = 0
        self.offsets[0] = 0
        for index, initial in enumerate(self.template.base):
            row = initial
            for group in selected:
                row ^= group[index]
            while row:
                bit = row & -row
                self.terms[count] = self.template.universe[bit.bit_length() - 1]
                count += 1
                row ^= bit
            self.offsets[index + 1] = count
        assert count <= self.capacity
        return count


class PackedContext:
    def __init__(self, case, *, sanitized=False):
        start = time.perf_counter_ns()
        self.affine = AffineContext(case, sanitized=sanitized)
        self.compact = self.affine.base.compact
        self.prepared = self.affine.base.base.base
        self.rows = PackedAffineRows(self.affine.template)
        self.static = [canonical(row) for row in self.compact.static_equations]
        self.lock = threading.Lock()
        self.setup_ns = time.perf_counter_ns() - start

    def _original_s3_zero(self, assignment, target_x):
        case, field = self.prepared.case, self.prepared.field
        n, ell, m = case['n'], case['ell'], case['m']
        a = (assignment >> (m * ell + (m - 3) * n)) & ((1 << n) - 1)
        b = (assignment >> ((m - 1) * ell)) & ((1 << ell) - 1)
        a2, b2, t2 = (field.mul(x, x) for x in (a, b, target_x))
        return (field.mul(a2, b2) ^ field.mul(a2, t2) ^
                field.mul(b2, t2) ^ field.mul(field.mul(a, b), target_x) ^
                case['curve_b']) == 0

    def _packed_rows_zero(self, assignment):
        for row in range(self.affine.template.n):
            parity = 0
            for term in range(self.rows.offsets[row], self.rows.offsets[row + 1]):
                monomial = self.rows.terms[term]
                parity ^= (assignment & monomial) == monomial
            if parity:
                return False
        return True

    def run(self, target_x, arm):
        if arm in ('compact', 'affine'):
            return self.affine.run(target_x, arm)
        if arm != 'packed':
            raise ValueError('unknown arm')
        with self.lock:
            start = time.perf_counter_ns()
            count = self.rows.fill(target_x)
            filled = time.perf_counter_ns()
            raw = MessageResult()
            code = self.compact.lib.compact_separator_run(
                self.compact.handle, self.affine.template.n, count,
                self.rows.offsets, self.rows.terms, self.compact.max_states,
                C.byref(raw))
            solved = time.perf_counter_ns()
            assert code == raw.result.status and code in STATUS
            assignment = raw.result.assignment if code == 1 else None
            verified = None
            if assignment is not None:
                verified = (all(satisfies(row, assignment) for row in self.static)
                            and self._packed_rows_zero(assignment)
                            and self._original_s3_zero(assignment, target_x))
                assert verified
            fields = {name: getattr(raw.result, name) for name, _ in PackedResult._fields_}
            fields.update(status=STATUS[code], assignment=assignment,
                          stage=STAGE[raw.result.stage], independently_verified=verified,
                          setup_factor_states=raw.setup_factor_states,
                          setup_elimination_states=raw.setup_elimination_states,
                          residual_factor_words=raw.residual_factor_words,
                          cached_witness_words=raw.cached_witness_words,
                          copy_ns=raw.copy_ns,
                          dynamic_factor_ns=raw.dynamic_factor_ns,
                          query_elimination_ns=raw.query_elimination_ns,
                          library_sha256=self.compact.library_sha256,
                          timing_eligible=False, qualified_speedup=None)
            checked = time.perf_counter_ns()
            point_verified = (point_replay(self.prepared.curve, assignment,
                                           self.prepared.case['m'],
                                           self.prepared.case['ell'], target_x)
                              if assignment is not None else None)
            finished = time.perf_counter_ns()
            return dict(arm=arm, target_x=target_x, status=fields['status'],
                        assignment=assignment, point_verified=point_verified,
                        equation_verified=verified, online_ns=finished - start,
                        pack_ns=filled - start, native_ns=solved - filled,
                        verify_ns=checked - solved, point_replay_ns=finished - checked,
                        solver=fields, timing_eligible=False, qualified_speedup=None)

    def close(self):
        self.affine.close()
