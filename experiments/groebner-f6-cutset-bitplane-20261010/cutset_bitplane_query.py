"""Fresh cutset targets over exact cached boundary truth planes."""
import ctypes as C
import hashlib
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'groebner-f6-replay-plan-20261009'))
from replay_plan import ReplayContext  # noqa: E402
from cutset_query import condition_equation, STATUS, pack  # noqa: E402
from message_query import MessageResult, U32, U64  # noqa: E402


class CutsetBitplaneResult(C.Structure):
    _fields_ = [('message', MessageResult)] + [(name, U64) for name in (
        'setup_static_assignments', 'setup_template_evaluations',
        'plane_words', 'query_xor_words', 'query_and_words', 'query_ns')]


class BitplaneContext(ReplayContext):
    """Pair the unchanged grouped message path with target-bitplane queries.

    Both arms share the same branch geometry, packed target coefficient source,
    original ANF and curve checks, and planned point replay. Each target still
    runs a native decision and receives a fresh independent verification.
    """

    def __init__(self, case, runtime, *, max_bag=24,
                 max_states=200_000_000, sanitized=False):
        start = time.perf_counter_ns()
        super().__init__(case, runtime, max_bag=max_bag,
                         max_states=max_states, sanitized=sanitized)
        self.message_setup_ns = self.setup_ns
        bitplane_start = time.perf_counter_ns()
        self.bitplane_handles = []
        try:
            suffix = '.dylib' if sys.platform == 'darwin' else '.so'
            self.path = HERE / 'build' / ('cutset_bitplane' +
                ('-ubsan' if sanitized else '') + suffix)
            self.lib = C.CDLL(str(self.path))
            self.lib.cutset_bitplane_create.argtypes = [
                U32, U64, U64, C.POINTER(U64), C.POINTER(U64), U64, U32,
                U64, U32, U64, U32, U32, U64, C.POINTER(U64),
                C.POINTER(U64), C.POINTER(CutsetBitplaneResult)]
            self.lib.cutset_bitplane_create.restype = C.c_void_p
            self.lib.cutset_bitplane_run.argtypes = [
                C.c_void_p, U64, U64, C.POINTER(CutsetBitplaneResult)]
            self.lib.cutset_bitplane_run.restype = C.c_int
            self.lib.cutset_bitplane_destroy.argtypes = [C.c_void_p]
            self.lib.cutset_bitplane_destroy.restype = None
            template = self.template.build(0)
            for bit in range(case['n']):
                template.extend(self.template.build(1 << bit))
            template_offsets, template_terms, template_count = pack(template)
            prefix, _ = runtime['split_case'](case)
            for branch in self.branches:
                choices = list(zip(self.branch_bits, branch['values']))
                conditioned = [condition_equation(row, choices)
                               for row in self.original_static]
                offsets, terms, count = pack(conditioned)
                result = CutsetBitplaneResult()
                handle = self.lib.cutset_bitplane_create(
                    case['nvars'], len(conditioned), count, offsets, terms,
                    len(prefix), case['n'], self.boundary_mask,
                    max_bag, max_states, case['n'], case['n'],
                    template_count, template_offsets, template_terms,
                    C.byref(result))
                if not handle or result.message.result.status != 1:
                    raise RuntimeError('bitplane setup failed: '
                                       f'{result.message.result.status}')
                self.bitplane_handles.append(handle)
            self.library_sha256 = hashlib.sha256(self.path.read_bytes()).hexdigest()
            self.bitplane_setup = dict(
                handles=len(self.bitplane_handles),
                boundary_bits=self.boundary_mask.bit_count(),
                static_assignments=result.setup_static_assignments,
                template_evaluations_per_branch=result.setup_template_evaluations,
                plane_words_per_branch=result.plane_words,
                library_sha256=self.library_sha256)
            self.bitplane_setup_ns = time.perf_counter_ns() - bitplane_start
            self.setup_ns = time.perf_counter_ns() - start
        except BaseException:
            self.close()
            raise

    def close(self):
        for handle in getattr(self, 'bitplane_handles', []):
            self.lib.cutset_bitplane_destroy(handle)
        self.bitplane_handles = []
        super().close()

    def run(self, target_x, solver_arm, *, exhaustive=True, on_branch=None):
        if solver_arm == 'message':
            result = super().run(target_x, 'planned',
                coefficient_arm='packed', exhaustive=exhaustive,
                on_branch=on_branch)
            result['solver_arm'] = solver_arm
            return result
        if solver_arm != 'bitplane':
            raise ValueError('unknown solver arm')
        with self._mode_lock, self._query_lock:
            self._replay_mode = 'planned'
            self._point_ns = 0
            try:
                start = time.perf_counter_ns()
                rows, count, offsets, terms = self._target_rows(target_x, 'packed')
                coefficient_ns = time.perf_counter_ns() - start
                branch_results = []
                selected_assignment = None
                first_answer_ns = None
                native_ns = 0
                for index, (branch, handle) in enumerate(zip(
                        self.branches, self.bitplane_handles)):
                    before = time.perf_counter_ns()
                    native = CutsetBitplaneResult()
                    code = self.lib.cutset_bitplane_run(
                        handle, target_x, self.branches[index]['layout'].max_states,
                        C.byref(native))
                    call_ns = time.perf_counter_ns() - before
                    native_ns += call_ns
                    if code != native.message.result.status or code not in STATUS:
                        raise AssertionError('inconsistent bitplane status')
                    status = STATUS[code]
                    native_assignment = (native.message.result.assignment
                                         if code == 1 else None)
                    assignment = None
                    input_verified = original_equation_verified = None
                    equation_verified = point_verified = None
                    if native_assignment is not None:
                        if native_assignment & self.branch_mask:
                            raise AssertionError('bitplane witness sets a fixed bit')
                        assignment = native_assignment | branch['fixed_one']
                        input_verified = self._rows_zero(
                            assignment, offsets, terms, rows)
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
                        native_assignment=native_assignment,
                        assignment=assignment, input_verified=input_verified,
                        original_equation_verified=original_equation_verified,
                        equation_verified=equation_verified,
                        point_verified=point_verified, call_ns=call_ns,
                        query_xor_words=native.query_xor_words,
                        query_and_words=native.query_and_words,
                        query_ns=native.query_ns,
                        native_factor_states=native.message.result.factor_states,
                        native_elimination_states=
                            native.message.result.elimination_states)
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
                check_ns = end - start - coefficient_ns - native_ns
                other_check_ns = check_ns - self._point_ns
                if other_check_ns < 0:
                    raise AssertionError('point replay exceeds check interval')
                return dict(solver_arm=solver_arm, arm='packed',
                    replay_arm='planned', target_x=target_x, status=status,
                    assignment=selected_assignment, branches=branch_results,
                    first_answer_ns=first_answer_ns,
                    coefficient_ns=coefficient_ns, native_ns=native_ns,
                    check_ns=check_ns, point_replay_ns=self._point_ns,
                    other_check_ns=other_check_ns, online_ns=end - start)
            finally:
                self._replay_mode = 'reference'
