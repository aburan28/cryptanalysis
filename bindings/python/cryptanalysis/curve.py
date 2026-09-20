"""Curve-aware dispatch: GLV endomorphism detection and the named registry.

Some curves over F_p carry an efficiently computable endomorphism beyond
negation -- :attr:`CurveEndo.J0` (``y^2 = x^3 + b``, ``p = 1 mod 3``, an
order-6 automorphism group) and :attr:`CurveEndo.J1728` (``y^2 = x^3 + a x``,
``p = 1 mod 4``, order 4).  :meth:`Group.curve_solve` folds the Pollard rho
walk by it for ``sqrt(m)`` fewer operations.
"""

from __future__ import annotations

from ctypes import byref, c_double, c_int32, c_uint32, c_uint64
from dataclasses import dataclass
from enum import IntEnum

from . import _lib
from ._lib import lib


class CurveEndo(IntEnum):
    """The endomorphism a curve carries."""

    NONE = 0
    J0 = 1
    J1728 = 2

    def __str__(self) -> str:
        return {CurveEndo.J0: "j0", CurveEndo.J1728: "j1728"}.get(self, "none")


@dataclass(frozen=True)
class CurveInfo:
    """A curve's endomorphism structure and the resulting rho speed-up."""

    endo: CurveEndo
    aut_order: int
    beta: int  # cube root of unity (j0) or sqrt(-1) (j1728) mod p, or 0
    lambda_: int  # eigenvalue with psi(P) = lambda*P (mod order), or 0
    rho_speedup: float  # sqrt(aut_order): rho op-count factor vs a plain sqrt(n)


def curve_detect(p: int, a: int, b: int, order: int = 0) -> CurveInfo:
    """Detect the endomorphism structure of ``y^2 = x^3 + a x + b`` over F_p.

    ``order`` is the subgroup order (0 => geometric structure only, leaving
    ``lambda_`` unresolved).
    """
    endo, am, beta, lam, sp = c_int32(0), c_uint32(0), c_uint64(0), c_uint64(0), c_double(0.0)
    _lib.arm()
    rc = lib.ca_ffi_curve_detect(
        _lib.u64(p, "p"),
        _lib.u64(a, "a"),
        _lib.u64(b, "b"),
        _lib.u64(order, "order"),
        byref(endo),
        byref(am),
        byref(beta),
        byref(lam),
        byref(sp),
    )
    _lib.check(rc)
    return CurveInfo(CurveEndo(endo.value), am.value, beta.value, lam.value, sp.value)


def curve_by_name(name: str) -> tuple[int, int, int, int]:
    """Look up a registry curve, returning ``(p, a, b, order)``."""
    p, a, b, order = c_uint64(0), c_uint64(0), c_uint64(0), c_uint64(0)
    _lib.arm()
    rc = lib.ca_ffi_curve_by_name(
        name.encode("utf-8"), byref(p), byref(a), byref(b), byref(order)
    )
    _lib.check(rc)
    return p.value, a.value, b.value, order.value


def curve_names() -> list[str]:
    """The names of the curves in the registry."""
    out: list[str] = []
    i = 0
    while True:
        ptr = lib.ca_ffi_curve_name(i)
        if not ptr:
            break
        out.append(ptr.decode("utf-8"))
        i += 1
    return out


__all__ = ["CurveEndo", "CurveInfo", "curve_by_name", "curve_detect", "curve_names"]
