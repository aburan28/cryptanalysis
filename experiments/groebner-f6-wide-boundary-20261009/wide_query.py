"""Opt-in exact S3 target queries with a wider, bounded static separator."""

from pathlib import Path
import sys
import time


DEPENDENCIES = (
    'groebner-f6-packed-20261009',
    'groebner-f6-prepared-20261009',
    'groebner-f6-message-20261009',
    'groebner-f6-boundary-compact-20261009',
    'groebner-f6-affine-target-20261009',
    'groebner-f6-packed-target-20261009',
    'groebner-f6-bitplane-target-20261009',
    'groebner-f6-20261008',
    'pdp-scaling',
)


def load_runtime(runtime_root):
    experiments = Path(runtime_root).resolve() / 'experiments'
    for name in DEPENDENCIES:
        path = str(experiments / name)
        if path not in sys.path:
            sys.path.insert(0, path)
    from chain_fixture import fixture  # noqa: E402
    from prepared_query import split_case  # noqa: E402
    from compact_query import CompactLayout, canonical, satisfies, point_replay  # noqa: E402
    from affine_query import AffineEquations  # noqa: E402
    from bitplane_query import BitplaneLayout  # noqa: E402
    from message_query import MessageLayout  # noqa: E402
    from chain_profile import coordinate, equations, s3  # noqa: E402
    from gf2n import Curve, GF2n  # noqa: E402
    return locals()


class WideContext:
    """Reuse only static factors and affine target truth planes.

    Every call computes its target-specific coefficients and obtains a fresh
    native answer. A separate compact elimination and the original equations
    are checked for every target in the validation driver.
    """

    def __init__(self, case, runtime, *, max_bag, max_states=200_000_000,
                 sanitized=False):
        before = time.perf_counter_ns()
        self.case, self.runtime = case, runtime
        self.field = runtime['GF2n'](case['n'])
        self.curve = runtime['Curve'](self.field, case['curve_b'])
        prefix, suffix = runtime['split_case'](case)
        self.static = prefix + suffix
        self.static_canonical = [runtime['canonical'](row) for row in self.static]
        m, ell, n = case['m'], case['ell'], case['n']
        self.auxiliary = runtime['coordinate'](m * ell + (m - 3) * n, n)
        self.summand = runtime['coordinate']((m - 1) * ell, ell)
        self.boundary_mask = 0
        for mask in [*self.auxiliary, *self.summand]:
            self.boundary_mask |= mask
        self.template = runtime['AffineEquations'](
            self.field, case['curve_b'], self.auxiliary, self.summand)
        template_rows = self.template.build(0)
        for bit in range(n):
            template_rows.extend(self.template.build(1 << bit))
        self.compact = runtime['CompactLayout'](
            case['nvars'], self.static, self.boundary_mask,
            max_bag=max_bag, max_states=max_states, sanitized=sanitized)
        try:
            self.bitplane = runtime['BitplaneLayout'](
                case['nvars'], self.static, self.boundary_mask, n, template_rows,
                max_bag=max_bag, max_states=max_states, sanitized=sanitized)
        except BaseException:
            self.compact.close()
            raise
        self.setup_ns = time.perf_counter_ns() - before

    def run(self, target_x, arm):
        if arm not in ('compact', 'bitplane'):
            raise ValueError('unknown arm')
        before = time.perf_counter_ns()
        if arm == 'compact':
            result = self.compact.run(self.template.build(target_x))
        else:
            result = self.bitplane.run(target_x)
        direct = self.runtime['equations'](
            self.field, self.runtime['s3'](
                self.field, self.case['curve_b'], self.auxiliary,
                self.summand, {0: target_x}))
        assignment = result['assignment']
        equation_verified = None
        point_verified = None
        if assignment is not None:
            equation_verified = all(
                self.runtime['satisfies'](row, assignment)
                for row in self.static_canonical)
            equation_verified &= all(
                self.runtime['satisfies'](self.runtime['canonical'](row),
                                          assignment) for row in direct)
            point_verified = self.runtime['point_replay'](
                self.curve, assignment, self.case['m'], self.case['ell'], target_x)
        return dict(arm=arm, target_x=target_x, status=result['status'],
                    assignment=assignment, equation_verified=equation_verified,
                    point_verified=point_verified,
                    online_ns=time.perf_counter_ns() - before, native=result)

    def close(self):
        self.bitplane.close()
        self.compact.close()
