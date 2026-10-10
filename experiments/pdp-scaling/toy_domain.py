"""Explicit small-domain control for the PDP benchmark; exponential in l.

Bounded to n<=19 and l<=8. This does not provide a scalable factor-base
membership algorithm, cache target answers, or change the Semaev equations.
"""
from fixed_phase import Template, scalar, subgroup_order
from gf2n import Curve


class ToyDomainTemplate(Template):
    def __init__(self, F, l, phases, encoding):
        if not (3 <= F.n <= 19 and F.n % 2 and 1 <= l <= min(8, F.n)):
            raise ValueError('explicit-domain control requires odd 3<=n<=19 and l<=8')
        super().__init__(F, l, phases, encoding)
        E, r = Curve(F, 1), subgroup_order(F.n)
        allowed = []
        # The source payload is literally its polynomial-basis coordinate.
        # Frobenius preserves E0, nonzero x, and [r]P=O, so the identical
        # admissible payload set applies to all three fixed-phase blocks.
        for payload in range(1, 1 << l):
            point = E.lift_x(payload)
            if point is not None and scalar(E, r, point).inf:
                allowed.append(payload)
        self.domain_payloads = allowed
        # Positive support encoding: one selector per valid payload. At least
        # one selector must hold; two different selectors imply contradictory
        # payload bits, so explicit pairwise at-most-one clauses are unnecessary.
        # This propagates admissibility before a complete payload assignment.
        for block in self.payload:
            selectors = [self.c.var() for _ in allowed]
            self.c.clauses.append(selectors)
            for selector, payload in zip(selectors, allowed):
                literals = [w if payload >> j & 1 else -w for j, w in enumerate(block)]
                self.c.clauses.extend([[-selector, lit] for lit in literals])
                self.c.clauses.append([selector] + [-lit for lit in literals])
        # Full lifting, subgroup and point-sum verification remains inherited.
