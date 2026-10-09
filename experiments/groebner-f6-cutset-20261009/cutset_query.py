"""Exact S3 cutset conditioning over immutable grouped-factor layouts."""
import ctypes as C
import itertools
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'groebner-f6-grouped-factor-20261009'))
from grouped_query import GroupedLayout  # noqa: E402
from message_query import MessageResult, STATUS, pack  # noqa: E402


def condition_equation(row, choices):
    """Substitute fixed Boolean bits in an ANF, canceling duplicate terms."""
    fixed_mask = 0
    for bit, _ in choices:
        if bit == 0 or bit & (bit - 1) or fixed_mask & bit:
            raise ValueError('branch bits must be distinct single-bit masks')
        fixed_mask |= bit
    parity = set()
    for term in row:
        if any(term & bit and not value for bit, value in choices):
            continue
        reduced = term & ~fixed_mask
        if reduced in parity:
            parity.remove(reduced)
        else:
            parity.add(reduced)
    return sorted(parity)


class CutsetContext:
    """Condition one high bit of each nonterminal middle summand.

    Every target still receives fresh equations, native elimination, original
    equation checks, and curve-point replay. Only static branch layouts and
    their witness histories are reused.
    """

    def __init__(self, case, runtime, *, max_bag=24,
                 max_states=200_000_000, sanitized=False):
        start = time.perf_counter_ns()
        self.case, self.runtime = case, runtime
        m, ell, n = case['m'], case['ell'], case['n']
        if m < 4 or m > 5 or n != 9 or ell != 7 or case['nvars'] > 64:
            raise ValueError('unsupported frozen cutset geometry')
        self.field = runtime['GF2n'](n)
        self.curve = runtime['Curve'](self.field, case['curve_b'])
        prefix, suffix = runtime['split_case'](case)
        self.original_static = prefix + suffix
        self.original_canonical = [runtime['canonical'](row)
                                   for row in self.original_static]
        self.auxiliary = runtime['coordinate'](m * ell + (m - 3) * n, n)
        self.summand = runtime['coordinate']((m - 1) * ell, ell)
        self.boundary_mask = 0
        for bit in [*self.auxiliary, *self.summand]:
            self.boundary_mask |= bit
        self.branch_bits = [1 << ((j + 1) * ell - 1)
                            for j in range(2, m - 1)]
        self.branch_mask = sum(self.branch_bits)
        if self.branch_mask & self.boundary_mask:
            raise AssertionError('conditioned variable enters terminal boundary')
        self.branches = []
        try:
            for values in itertools.product((0, 1),
                                            repeat=len(self.branch_bits)):
                choices = list(zip(self.branch_bits, values))
                fixed_one = sum(bit for bit, value in choices if value)
                conditioned = [condition_equation(row, choices)
                               for row in self.original_static]
                layout = GroupedLayout(
                    case['nvars'], conditioned, len(prefix), n,
                    self.boundary_mask, max_bag=max_bag,
                    max_states=max_states, sanitized=sanitized)
                self.branches.append(dict(values=values, fixed_one=fixed_one,
                                          layout=layout))
        except BaseException:
            self.close()
            raise
        self.setup_ns = time.perf_counter_ns() - start

    def check_dynamic_scope(self, dynamic):
        if any(term & self.branch_mask for row in dynamic for term in row):
            raise ValueError('target equation uses a conditioned variable')

    def run(self, target_x, *, exhaustive=True, on_branch=None):
        start = time.perf_counter_ns()
        dynamic = self.runtime['equations'](
            self.field, self.runtime['s3'](
                self.field, self.case['curve_b'], self.auxiliary,
                self.summand, {0: target_x}))
        self.check_dynamic_scope(dynamic)
        dynamic_canonical = [self.runtime['canonical'](row) for row in dynamic]
        offsets, terms, count = pack(dynamic)
        branch_results = []
        selected_assignment = None
        first_answer_ns = None
        for index, branch in enumerate(self.branches):
            layout = branch['layout']
            before = time.perf_counter_ns()
            native = MessageResult()
            code = layout.lib.message_separator_run(
                layout.handle, len(dynamic), count, offsets, terms,
                layout.max_states, C.byref(native))
            call_ns = time.perf_counter_ns() - before
            if code != native.result.status or code not in STATUS:
                raise AssertionError('inconsistent native result status')
            status = STATUS[code]
            native_assignment = native.result.assignment if code == 1 else None
            assignment = None
            equation_verified = point_verified = None
            if native_assignment is not None:
                if native_assignment & self.branch_mask:
                    raise AssertionError('conditioned bits are not free in native assignment')
                assignment = native_assignment | branch['fixed_one']
                equation_verified = all(self.runtime['satisfies'](row, assignment)
                    for row in self.original_canonical + dynamic_canonical)
                point_verified = self.runtime['point_replay'](
                    self.curve, assignment, self.case['m'],
                    self.case['ell'], target_x)
                if selected_assignment is None:
                    selected_assignment = assignment
                    first_answer_ns = time.perf_counter_ns() - start
            branch_results.append(dict(index=index, values=branch['values'],
                fixed_one=branch['fixed_one'], status=status,
                native_assignment=native_assignment, assignment=assignment,
                equation_verified=equation_verified,
                point_verified=point_verified, call_ns=call_ns,
                native_factor_states=native.result.factor_states,
                native_elimination_states=native.result.elimination_states,
                native_copy_ns=native.copy_ns,
                native_dynamic_factor_ns=native.dynamic_factor_ns,
                native_query_elimination_ns=native.query_elimination_ns))
            if on_branch is not None:
                on_branch(branch_results[-1])
            if selected_assignment is not None and not exhaustive:
                break
        status = ('satisfiable' if selected_assignment is not None else
                  'unsatisfiable' if len(branch_results) == len(self.branches)
                  and all(row['status'] == 'unsatisfiable'
                          for row in branch_results) else 'inconclusive')
        return dict(target_x=target_x, status=status,
                    assignment=selected_assignment,
                    branches=branch_results,
                    first_answer_ns=first_answer_ns,
                    online_ns=time.perf_counter_ns() - start)

    def close(self):
        for branch in getattr(self, 'branches', []):
            branch['layout'].close()
        self.branches = []
