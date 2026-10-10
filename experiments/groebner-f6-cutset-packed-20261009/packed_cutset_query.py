"""Fresh packed target coefficients over exact reusable cutset layouts."""
import ctypes as C
import sys
from pathlib import Path
import threading
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'groebner-f6-cutset-20261009'))
sys.path.insert(0, str(HERE.parent / 'groebner-f6-packed-target-20261009'))
from cutset_query import CutsetContext, MessageResult, STATUS, pack  # noqa: E402
from packed_query import PackedAffineRows  # noqa: E402
from affine_query import AffineEquations  # noqa: E402


class PackedCutsetContext(CutsetContext):
    """Share static layouts and ANF storage; recompute every target answer.

    The ``direct`` arm builds and packs the target's ANF rows. The ``packed``
    arm combines precomputed affine coefficient planes into reusable ctypes
    arrays. Both use the same native branch layouts, resource caps, original
    field-equation check, and curve replay inside the timed interval.
    """

    def __init__(self, case, runtime, **kwargs):
        start = time.perf_counter_ns()
        super().__init__(case, runtime, **kwargs)
        try:
            self.template = AffineEquations(
                self.field, case['curve_b'], self.auxiliary, self.summand)
            if any(term & self.branch_mask for term in self.template.universe):
                raise ValueError('target template uses a conditioned variable')
            self.rows = PackedAffineRows(self.template)
            self._query_lock = threading.Lock()
            self.setup_ns = time.perf_counter_ns() - start
        except BaseException:
            self.close()
            raise

    def _original_s3_zero(self, assignment, target_x):
        """Evaluate the original last S3 field equation independently."""
        case, field = self.case, self.field
        n, ell, m = case['n'], case['ell'], case['m']
        a = (assignment >> (m * ell + (m - 3) * n)) & ((1 << n) - 1)
        b = (assignment >> ((m - 1) * ell)) & ((1 << ell) - 1)
        a2, b2, t2 = (field.mul(x, x) for x in (a, b, target_x))
        return (field.mul(a2, b2) ^ field.mul(a2, t2) ^
                field.mul(b2, t2) ^ field.mul(field.mul(a, b), target_x) ^
                case['curve_b']) == 0

    @staticmethod
    def _rows_zero(assignment, offsets, terms, rows):
        if (offsets[0] != 0 or offsets[rows] > len(terms) or
                any(offsets[row] > offsets[row + 1]
                    for row in range(rows))):
            raise AssertionError('invalid packed row offsets')
        for row in range(rows):
            parity = 0
            for term in range(offsets[row], offsets[row + 1]):
                monomial = terms[term]
                parity ^= (assignment & monomial) == monomial
            if parity:
                return False
        return True

    def _target_rows(self, target_x, arm):
        if type(target_x) is not int or not 0 <= target_x < 1 << self.template.n:
            raise ValueError('target abscissa outside the field encoding')
        if arm == 'packed':
            count = self.rows.fill(target_x)
            return self.template.n, count, self.rows.offsets, self.rows.terms
        dynamic = self.runtime['equations'](
            self.field, self.runtime['s3'](
                self.field, self.case['curve_b'], self.auxiliary,
                self.summand, {0: target_x}))
        self.check_dynamic_scope(dynamic)
        offsets, terms, count = pack(dynamic)
        return len(dynamic), count, offsets, terms

    def run(self, target_x, arm, *, exhaustive=True, on_branch=None):
        if arm not in ('direct', 'packed'):
            raise ValueError('unknown target coefficient arm')
        with self._query_lock:
            start = time.perf_counter_ns()
            rows, count, offsets, terms = self._target_rows(target_x, arm)
            coefficient_ns = time.perf_counter_ns() - start
            branch_results = []
            selected_assignment = None
            first_answer_ns = None
            native_ns = 0
            for index, branch in enumerate(self.branches):
                layout = branch['layout']
                if not layout.handle:
                    raise ValueError('cutset layout is closed')
                before = time.perf_counter_ns()
                native = MessageResult()
                code = layout.lib.message_separator_run(
                    layout.handle, rows, count, offsets, terms,
                    layout.max_states, C.byref(native))
                call_ns = time.perf_counter_ns() - before
                native_ns += call_ns
                if code != native.result.status or code not in STATUS:
                    raise AssertionError('inconsistent native result status')
                status = STATUS[code]
                native_assignment = native.result.assignment if code == 1 else None
                assignment = None
                input_verified = original_equation_verified = None
                equation_verified = point_verified = None
                if native_assignment is not None:
                    if native_assignment & self.branch_mask:
                        raise AssertionError('native witness sets a fixed branch bit')
                    assignment = native_assignment | branch['fixed_one']
                    input_verified = self._rows_zero(assignment, offsets, terms, rows)
                    original_equation_verified = self._original_s3_zero(
                        assignment, target_x)
                    equation_verified = (input_verified and
                        original_equation_verified and
                        all(self.runtime['satisfies'](row, assignment)
                            for row in self.original_canonical))
                    point_verified = self.runtime['point_replay'](
                        self.curve, assignment, self.case['m'],
                        self.case['ell'], target_x)
                    if selected_assignment is None:
                        selected_assignment = assignment
                        first_answer_ns = time.perf_counter_ns() - start
                row = dict(index=index, values=branch['values'],
                    fixed_one=branch['fixed_one'], status=status,
                    native_assignment=native_assignment, assignment=assignment,
                    input_verified=input_verified,
                    original_equation_verified=original_equation_verified,
                    equation_verified=equation_verified,
                    point_verified=point_verified, call_ns=call_ns,
                    native_factor_states=native.result.factor_states,
                    native_elimination_states=native.result.elimination_states,
                    native_copy_ns=native.copy_ns,
                    native_dynamic_factor_ns=native.dynamic_factor_ns,
                    native_query_elimination_ns=native.query_elimination_ns)
                branch_results.append(row)
                if on_branch is not None:
                    on_branch(row)
                if selected_assignment is not None and not exhaustive:
                    break
            status = ('satisfiable' if selected_assignment is not None else
                'unsatisfiable' if len(branch_results) == len(self.branches)
                and all(row['status'] == 'unsatisfiable'
                        for row in branch_results) else 'inconclusive')
            end = time.perf_counter_ns()
            return dict(arm=arm, target_x=target_x, status=status,
                assignment=selected_assignment, branches=branch_results,
                first_answer_ns=first_answer_ns,
                coefficient_ns=coefficient_ns, native_ns=native_ns,
                check_ns=end - start - coefficient_ns - native_ns,
                online_ns=end - start)
