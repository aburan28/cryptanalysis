"""Exact reusable factor-base geometry for independent curve replay."""
from pathlib import Path
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'groebner-f6-cutset-packed-20261009'))
from packed_cutset_query import PackedCutsetContext  # noqa: E402


class PointReplayPlan:
    """Precompute lifts and two-summand sums, never target answers.

    At depth j, the state set contains exactly the finite sums of the first
    j selected points whose intermediate prefixes of length >= 2 are finite.
    The pair table establishes the invariant at j=2; fresh group additions
    extend it for the remaining summands in every verification call.
    """

    def __init__(self, curve, m, ell):
        start = time.perf_counter_ns()
        if curve.F.n != 9 or curve.b != 1 or m not in (4, 5) or ell != 7:
            raise ValueError('unsupported frozen replay geometry')
        self.curve, self.m, self.ell = curve, m, ell
        choices = []
        for x in range(1 << ell):
            point = curve.lift_x(x)
            points = () if point is None else tuple(sorted(
                {point, curve.neg(point)}, key=lambda p: (p.x, p.y)))
            choices.append(points)
        self.choices = tuple(choices)
        liftable = [x for x, points in enumerate(choices) if points]
        pairs = {}
        for index, x in enumerate(liftable):
            for y in liftable[index:]:
                values = tuple(sorted({point for left in choices[x]
                    for right in choices[y]
                    if not (point := curve.add(left, right)).inf},
                    key=lambda p: (p.x, p.y)))
                pairs[x, y] = pairs[y, x] = values
        self.pairs = pairs
        self.liftable_x = len(liftable)
        self.pair_slots = len(pairs)
        self.pair_states = sum(len(states) for states in pairs.values())
        self.setup_ns = time.perf_counter_ns() - start

    def verify(self, assignment, target_x):
        if type(assignment) is not int or assignment < 0 or type(target_x) is not int:
            raise ValueError('invalid curve replay input')
        mask = (1 << self.ell) - 1
        abscissae = [(assignment >> (j * self.ell)) & mask
                     for j in range(self.m)]
        states = self.pairs.get((abscissae[0], abscissae[1]), ())
        if not states:
            return False
        for j in range(2, self.m):
            points = self.choices[abscissae[j]]
            if not points:
                return False
            if j == self.m - 1:
                return any(not (total := self.curve.add(partial, point)).inf
                           and total.x == target_x
                           for partial in states for point in points)
            next_states = set()
            for partial in states:
                for point in points:
                    total = self.curve.add(partial, point)
                    if not total.inf:
                        next_states.add(total)
            states = next_states
            if not states:
                return False
        return False


class ReplayContext(PackedCutsetContext):
    """Pair old and planned replay over the same native layouts and buffers."""

    def __init__(self, case, runtime, **kwargs):
        start = time.perf_counter_ns()
        copied = dict(runtime)
        original_replay = copied['point_replay']
        super().__init__(case, copied, **kwargs)
        try:
            self.point_plan = PointReplayPlan(self.curve, case['m'], case['ell'])
            self._replay_mode = 'reference'
            self._point_ns = 0
            self._mode_lock = threading.Lock()

            def dispatch(curve, assignment, m, ell, target_x):
                if curve is not self.curve or m != case['m'] or ell != case['ell']:
                    raise ValueError('curve replay geometry mismatch')
                before = time.perf_counter_ns()
                try:
                    if self._replay_mode == 'planned':
                        return self.point_plan.verify(assignment, target_x)
                    return original_replay(curve, assignment, m, ell, target_x)
                finally:
                    self._point_ns += time.perf_counter_ns() - before

            self.runtime['point_replay'] = dispatch
            self.setup_ns = time.perf_counter_ns() - start
        except BaseException:
            self.close()
            raise

    def run(self, target_x, replay_arm, *, coefficient_arm='packed',
            exhaustive=True, on_branch=None):
        if replay_arm not in ('reference', 'planned'):
            raise ValueError('unknown curve replay arm')
        with self._mode_lock:
            self._replay_mode = replay_arm
            self._point_ns = 0
            try:
                result = super().run(target_x, coefficient_arm,
                    exhaustive=exhaustive, on_branch=on_branch)
                result['replay_arm'] = replay_arm
                result['point_replay_ns'] = self._point_ns
                result['other_check_ns'] = result['check_ns'] - self._point_ns
                if result['other_check_ns'] < 0:
                    raise AssertionError('point replay clock exceeds check interval')
                return result
            finally:
                self._replay_mode = 'reference'
