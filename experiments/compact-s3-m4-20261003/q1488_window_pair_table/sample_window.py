"""Uniform full-base sampler for Q1481's N83 cyclic-window orbit union."""

from __future__ import annotations

from build_n53_base import onb_x_from_cycle_mask


def representative(index: int, d: int) -> int:
    """Invert Q1481's deterministic long-zero-gap raw-orbit ordinal."""
    assert 0 <= index < (1 << (d - 1))
    if index == 0:
        return 1
    span = index.bit_length() + 1
    start = 1 << (span - 2)
    interior = index - start
    assert 2 <= span <= d and 0 <= interior < start
    return 1 | (1 << (span - 1)) | (interior << 1)


class WindowOrbitSampler:
    def __init__(self, onb, curve, orbit, cofactor, d, rng):
        assert onb.m == 83 and d == 23 and cofactor == 4
        self.onb = onb
        self.curve = curve
        self.orbit = orbit
        self.cofactor = cofactor
        self.d = d
        self.rng = rng
        self.draws = 0
        self.nonrational = 0
        self.identity_projection = 0
        self.accepted = 0
        self.certificates = {}

    def point(self):
        while True:
            self.draws += 1
            ordinal = self.rng.randrange(1 << (self.d - 1))
            mask = representative(ordinal, self.d)
            raw_x = onb_x_from_cycle_mask(mask, self.onb, self.orbit)
            raw = self.curve.pointFromX(raw_x)
            if raw is None:
                self.nonrational += 1
                continue
            projected = self.curve.mul(raw, self.cofactor)
            if projected is None:
                self.identity_projection += 1
                continue
            shift = self.rng.randrange(self.onb.m)
            sign_bit = self.rng.getrandbits(1)
            point = self.curve.frob(projected, shift)
            if sign_bit:
                point = self.curve.neg(point)
            self.accepted += 1
            self.certificates.setdefault(point, {
                "raw_orbit_ordinal": ordinal,
                "raw_cycle_mask": mask,
                "frobenius_shift": shift,
                "sign_bit": sign_bit,
            })
            return point

    def certificate(self, point):
        return self.certificates[point]

    def counters(self):
        return {
            "raw_orbit_draws": self.draws,
            "nonrational_x": self.nonrational,
            "identity_projections": self.identity_projection,
            "accepted_points": self.accepted,
        }
