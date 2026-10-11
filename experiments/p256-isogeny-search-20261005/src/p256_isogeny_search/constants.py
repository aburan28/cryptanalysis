"""Curve parameters used by the experiment harness."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PrimeCurve:
    name: str
    p: int
    a: int
    b: int
    n: int
    gx: int
    gy: int
    cofactor: int = 1

    @property
    def trace(self) -> int:
        return self.p + 1 - self.n * self.cofactor

    @property
    def frobenius_discriminant(self) -> int:
        return self.trace * self.trace - 4 * self.p


P256 = PrimeCurve(
    name="NIST P-256",
    p=int("FFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF", 16),
    a=int("FFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFC", 16),
    b=int("5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B", 16),
    n=int("FFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551", 16),
    gx=int("6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296", 16),
    gy=int("4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5", 16),
)


# A deliberately tiny prime-order curve used only to validate rho collision
# handling.  Exhaustive point counting gives #E(F_10007) = 9851.
TOY_CURVE = PrimeCurve(
    name="toy-p10007",
    p=10007,
    a=1,
    b=28,
    n=9851,
    gx=2,
    gy=4582,
)


# This complete factorization is verified on every analysis run.  Keeping the
# certificate in-tree makes routine runs fast; --refactor can independently
# rediscover it with SymPy (roughly minutes, depending on the machine).
P256_FROBENIUS_DISCRIMINANT_FACTORS = (
    3,
    5,
    456_597_257_999,
    1_428_624_589_419_343_516_204_097,
    46_523_541_035_814_968_339_936_406_074_986_559_003_387,
)
