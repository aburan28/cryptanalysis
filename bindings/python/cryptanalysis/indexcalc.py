"""Index calculus in (Z/pZ)^*: one-shot :func:`ic_solve` and reusable :class:`ICContext`."""

from __future__ import annotations

import ctypes
from typing import TYPE_CHECKING, Optional

from . import _lib
from ._lib import CICStats, CStats, lib
from ._types import ICParams, ICStats, Stats

if TYPE_CHECKING:
    from ctypes import _CArgObject  # only exists for type checkers


def _params(params: Optional[ICParams]) -> Optional[_CArgObject]:
    if params is None:
        return None
    if not isinstance(params, ICParams):
        raise TypeError(f"params must be an ICParams instance, not {type(params).__name__}")
    return ctypes.byref(params.to_c())


def ic_solve(p: int, g: int, h: int, params: Optional[ICParams] = None) -> tuple[int, ICStats]:
    """Find x with g^x == h (mod p) by index calculus (``p`` an odd prime < 2^63)."""
    p, g, h = _lib.u64(p, "p"), _lib.u64(g, "g"), _lib.u64(h, "h")
    x = ctypes.c_uint64(0)
    st = CICStats()
    _lib.arm()
    _lib.check(lib.ca_ffi_ic_solve(p, g, h, _params(params), ctypes.byref(x), ctypes.byref(st)))
    return x.value, ICStats.from_c(st)


def ic_auto_params(bits: int) -> tuple[int, int]:
    """The automatic (B, C) = (factor_base_bound, sieve_radius) for a ``bits``-bit modulus."""
    B, C = ctypes.c_uint32(0), ctypes.c_uint32(0)
    lib.ca_ic_auto_params(_lib.u32(bits, "bits"), ctypes.byref(B), ctypes.byref(C))
    return B.value, C.value


class ICContext:
    """Precomputed factor-base logarithms for base ``g`` modulo ``p``.

    Precomputation happens in the constructor; :meth:`log` then answers
    individual logarithms cheaply.  Free with :meth:`close` or a ``with`` block.
    """

    _handle: Optional[int] = None

    def __init__(self, p: int, g: int, params: Optional[ICParams] = None) -> None:
        p, g = _lib.u64(p, "p"), _lib.u64(g, "g")
        handle = ctypes.c_void_p(None)
        st = CICStats()
        _lib.arm()
        _lib.check(
            lib.ca_ic_precompute(p, g, _params(params), ctypes.byref(handle), ctypes.byref(st))
        )
        self._handle = handle.value
        self._p = p
        self._g = g
        self.stats: ICStats = ICStats.from_c(st)  #: statistics of the precomputation

    # ---- lifetime --------------------------------------------------------

    def close(self) -> None:
        handle, self._handle = self._handle, None
        if handle:
            lib.ca_ic_free(handle)

    def __del__(self) -> None:
        # contextlib.suppress() is deliberately not used here: __del__ can run
        # during interpreter shutdown, when module globals (including the
        # contextlib module object) may already have been torn down.
        try:  # noqa: SIM105
            self.close()
        except Exception:  # pragma: no cover
            pass

    def __enter__(self) -> ICContext:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @property
    def _ctx(self) -> int:
        if self._handle is None:
            raise ValueError("operation on a closed ICContext")
        return self._handle

    def __repr__(self) -> str:
        if self._handle is None:
            return "<ICContext closed>"
        return f"ICContext(p={self._p}, g={self._g}, factor_base_size={self.factor_base_size})"

    # ---- queries -----------------------------------------------------------

    @property
    def p(self) -> int:
        return lib.ca_ic_modulus(self._ctx)

    @property
    def g(self) -> int:
        return self._g

    @property
    def factor_base_size(self) -> int:
        return lib.ca_ic_factor_base_size(self._ctx)

    @property
    def primitive_root(self) -> int:
        """The primitive root the factor-base logarithms are taken with respect to."""
        return lib.ca_ic_primitive_root(self._ctx)

    def factor_base_logs(self) -> list[tuple[int, Optional[int]]]:
        """``(prime, log)`` for every factor-base prime (log is None if unknown).

        The logarithms are relative to :attr:`primitive_root`.
        """
        out = []
        prime, known = ctypes.c_uint32(0), ctypes.c_int(0)
        for i in range(self.factor_base_size):
            lg = lib.ca_ic_factor_base_log(self._ctx, i, ctypes.byref(prime), ctypes.byref(known))
            out.append((prime.value, lg if known.value else None))
        return out

    def log(self, h: int) -> tuple[int, Stats]:
        """Find x in [0, ord(g)) with g^x == h (mod p)."""
        x = ctypes.c_uint64(0)
        st = CStats()
        _lib.arm()
        _lib.check(lib.ca_ic_log(self._ctx, _lib.u64(h, "h"), ctypes.byref(x), ctypes.byref(st)))
        return x.value, Stats.from_c(st)


__all__ = ["ICContext", "ic_auto_params", "ic_solve"]
