"""The :class:`Group` handle: Z_p^* and elliptic-curve groups with their solvers."""

from __future__ import annotations

import ctypes
from typing import TYPE_CHECKING, Callable, Optional

from . import _lib
from ._lib import CStats, WordArray, Words, lib
from ._types import Elem, ElemLike, GroupKind, Options, Stats, from_words, to_words
from .errors import InvalidError, Status

if TYPE_CHECKING:
    from ctypes import _CArgObject  # only exists for type checkers


def _opts(options: Optional[Options]) -> Optional[_CArgObject]:
    """``ca_ffi_options *`` for the call (NULL => library defaults)."""
    if options is None:
        return None
    if not isinstance(options, Options):
        raise TypeError(f"options must be an Options instance, not {type(options).__name__}")
    return ctypes.byref(options.to_c())


class Group:
    """An opaque ``ca_ctx`` handle for Z_p^* or E(F_p).

    Construct with :meth:`Group.zp` or :meth:`Group.ec`.  The handle is freed
    by :meth:`close`, by leaving a ``with`` block, or by garbage collection.
    """

    _handle: Optional[int] = None

    def __init__(self, handle: int, kind: GroupKind) -> None:
        # Not part of the public API; use Group.zp() / Group.ec().
        self._handle = handle
        self._kind = GroupKind(kind)

    # ---- construction --------------------------------------------------

    @classmethod
    def zp(cls, p: int, order: int = 0) -> Group:
        """The multiplicative group Z_p^* (``p`` an odd prime < 2^64).

        ``order`` is the order of the subgroup you intend to work in (it must
        divide p-1); 0 lets the library use its default.
        """
        p = _lib.u64(p, "p")
        order = _lib.u64(order, "order")
        _lib.arm()
        handle = lib.ca_ctx_new_zp(p, order)
        if not handle:
            raise _lib.make_error(Status.INVALID, f"cannot build Z_p^* for p={p}, order={order}")
        return cls(handle, GroupKind.ZP)

    @classmethod
    def ec(cls, p: int, a: int, b: int, order: int = 0) -> Group:
        """The curve y^2 = x^3 + a x + b over F_p (``p`` a prime > 3).

        ``order`` is the (sub)group order if known; see :meth:`ec_count_points`
        and :meth:`set_order`.
        """
        p, a, b = _lib.u64(p, "p"), _lib.u64(a, "a"), _lib.u64(b, "b")
        order = _lib.u64(order, "order")
        _lib.arm()
        handle = lib.ca_ctx_new_ec(p, a, b, order)
        if not handle:
            raise _lib.make_error(
                Status.INVALID, f"cannot build E(F_p) for p={p}, a={a}, b={b}, order={order}"
            )
        return cls(handle, GroupKind.EC)

    @staticmethod
    def ec_count_points(p: int, a: int, b: int) -> int:
        """``#E(F_p)`` for y^2 = x^3 + a x + b (``ca_ec_order``)."""
        p, a, b = _lib.u64(p, "p"), _lib.u64(a, "a"), _lib.u64(b, "b")
        n = ctypes.c_uint64(0)
        _lib.arm()
        _lib.check(lib.ca_ec_order(p, a, b, ctypes.byref(n)), "point counting failed")
        return n.value

    # ---- lifetime --------------------------------------------------------

    def close(self) -> None:
        """Free the underlying ``ca_ctx``; the object is unusable afterwards."""
        handle, self._handle = self._handle, None
        if handle:
            lib.ca_ctx_free(handle)

    def __del__(self) -> None:
        # contextlib.suppress() is deliberately not used here: __del__ can run
        # during interpreter shutdown, when module globals (including the
        # contextlib module object) may already have been torn down.
        try:  # noqa: SIM105
            self.close()
        except Exception:  # pragma: no cover - interpreter shutdown
            pass

    def __enter__(self) -> Group:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @property
    def closed(self) -> bool:
        return self._handle is None

    @property
    def _ctx(self) -> int:
        if self._handle is None:
            raise ValueError("operation on a closed Group")
        return self._handle

    def __repr__(self) -> str:
        if self._handle is None:
            return "<Group closed>"
        if self._kind == GroupKind.ZP:
            return f"Group.zp(p={self.p}, order={self.order})"
        return f"Group.ec(p={self.p}, a={self.a}, b={self.b}, order={self.order})"

    # ---- properties -----------------------------------------------------

    @property
    def kind(self) -> GroupKind:
        return GroupKind(lib.ca_ctx_kind(self._ctx))

    @property
    def p(self) -> int:
        return lib.ca_ctx_p(self._ctx)

    @property
    def order(self) -> int:
        """The (sub)group order the solvers work with (0 if unknown)."""
        return lib.ca_ctx_order(self._ctx)

    @property
    def cofactor(self) -> int:
        return lib.ca_ctx_cofactor(self._ctx)

    @property
    def a(self) -> int:
        """Curve coefficient ``a`` (0 for Z_p^*)."""
        return lib.ca_ctx_curve_a(self._ctx)

    @property
    def b(self) -> int:
        """Curve coefficient ``b`` (0 for Z_p^*)."""
        return lib.ca_ctx_curve_b(self._ctx)

    def set_order(self, order: int, cofactor: int = 0) -> None:
        """Set the subgroup order (and optional cofactor) used by the solvers."""
        lib.ca_ctx_set_order(self._ctx, _lib.u64(order, "order"), _lib.u64(cofactor, "cofactor"))

    # ---- element helpers ------------------------------------------------

    def _w(self, value: ElemLike, name: str = "element") -> WordArray:
        return to_words(value, self._kind, name)

    def elem(self, value: ElemLike) -> Elem:
        """Normalise any accepted element representation to an :class:`Elem`."""
        return from_words(self._w(value))

    # ---- element operations --------------------------------------------

    def validate(self, a: ElemLike) -> bool:
        """True if ``a`` is a valid element of this group (never raises for bad values)."""
        try:
            w = self._w(a)
        except (TypeError, OverflowError):
            return False
        return bool(lib.ca_ctx_validate(self._ctx, w))

    def identity(self) -> Elem:
        out = Words()
        _lib.arm()
        _lib.check(lib.ca_ctx_identity(self._ctx, out))
        return from_words(out)

    def is_identity(self, a: ElemLike) -> bool:
        return bool(lib.ca_ctx_is_identity(self._ctx, self._w(a)))

    def op(self, a: ElemLike, b: ElemLike) -> Elem:
        """The group operation (``a * b`` in Z_p^*, ``a + b`` on a curve)."""
        out = Words()
        _lib.arm()
        _lib.check(lib.ca_ctx_op(self._ctx, out, self._w(a, "a"), self._w(b, "b")))
        return from_words(out)

    def inv(self, a: ElemLike) -> Elem:
        out = Words()
        _lib.arm()
        _lib.check(lib.ca_ctx_inv(self._ctx, out, self._w(a)))
        return from_words(out)

    def mul(self, a: ElemLike, k: int) -> Elem:
        """Scalar multiple / power ``a^k`` (``[k]a`` on a curve)."""
        out = Words()
        _lib.arm()
        _lib.check(lib.ca_ctx_mul(self._ctx, out, self._w(a), _lib.u64(k, "k")))
        return from_words(out)

    def equal(self, a: ElemLike, b: ElemLike) -> bool:
        return bool(lib.ca_ctx_equal(self._ctx, self._w(a, "a"), self._w(b, "b")))

    def elem_order(self, a: ElemLike) -> int:
        """The order of ``a`` (requires the group order to be known / factorable)."""
        n = ctypes.c_uint64(0)
        _lib.arm()
        _lib.check(
            lib.ca_ctx_elem_order(self._ctx, self._w(a), ctypes.byref(n)),
            "could not determine the element order",
        )
        return n.value

    def find_generator(self, seed: int = 0) -> Elem:
        """A generator of the subgroup of order :attr:`order`."""
        out = Words()
        _lib.arm()
        _lib.check(lib.ca_ctx_find_generator(self._ctx, out, _lib.u64(seed, "seed")))
        return from_words(out)

    def random_element(self, seed: int = 0) -> Elem:
        """A pseudo-random element (multiplied by the cofactor when one is set)."""
        out = Words()
        _lib.arm()
        _lib.check(lib.ca_ctx_random_element(self._ctx, out, _lib.u64(seed, "seed")))
        return from_words(out)

    def lift_x(self, x: int) -> Elem:
        """A curve point with the given x-coordinate (EC only; NotFoundError if none)."""
        out = Words()
        _lib.arm()
        _lib.check(
            lib.ca_ctx_lift_x(self._ctx, out, _lib.u64(x, "x")), f"no point with x={x} on the curve"
        )
        return from_words(out)

    # ---- solvers ----------------------------------------------------------

    def _interval(
        self,
        fn: Callable,
        base: ElemLike,
        target: ElemLike,
        lo: int,
        hi: int,
        options: Optional[Options],
    ) -> tuple[int, Stats]:
        x = ctypes.c_uint64(0)
        st = CStats()
        _lib.arm()
        rc = fn(
            self._ctx,
            self._w(base, "base"),
            self._w(target, "target"),
            _lib.u64(lo, "lo"),
            _lib.u64(hi, "hi"),
            _opts(options),
            ctypes.byref(x),
            ctypes.byref(st),
        )
        _lib.check(rc)
        return x.value, Stats.from_c(st)

    def _whole(
        self, fn: Callable, base: ElemLike, target: ElemLike, options: Optional[Options]
    ) -> tuple[int, Stats]:
        x = ctypes.c_uint64(0)
        st = CStats()
        _lib.arm()
        rc = fn(
            self._ctx,
            self._w(base, "base"),
            self._w(target, "target"),
            _opts(options),
            ctypes.byref(x),
            ctypes.byref(st),
        )
        _lib.check(rc)
        return x.value, Stats.from_c(st)

    def bsgs(
        self,
        base: ElemLike,
        target: ElemLike,
        lo: int = 0,
        hi: int = 0,
        options: Optional[Options] = None,
    ) -> tuple[int, Stats]:
        """Baby-step giant-step for x in [lo, hi] with base^x == target.

        ``lo == hi == 0`` searches the whole group.  Raises NotFoundError when
        no such x lies in the interval and LimitError when ``max_ops`` is hit.
        """
        return self._interval(lib.ca_ffi_bsgs, base, target, lo, hi, options)

    def kangaroo(
        self,
        base: ElemLike,
        target: ElemLike,
        lo: int = 0,
        hi: int = 0,
        options: Optional[Options] = None,
    ) -> tuple[int, Stats]:
        """Pollard's kangaroo (lambda) method on the interval [lo, hi]."""
        return self._interval(lib.ca_ffi_kangaroo, base, target, lo, hi, options)

    def grumpy(
        self,
        base: ElemLike,
        target: ElemLike,
        lo: int = 0,
        hi: int = 0,
        options: Optional[Options] = None,
    ) -> tuple[int, Stats]:
        """Grumpy-giants (Bernstein-Lange) interval algorithm on [lo, hi]."""
        return self._interval(lib.ca_ffi_grumpy, base, target, lo, hi, options)

    def rho(
        self, base: ElemLike, target: ElemLike, options: Optional[Options] = None
    ) -> tuple[int, Stats]:
        """Pollard rho over the whole group (needs :attr:`order`)."""
        return self._whole(lib.ca_ffi_rho, base, target, options)

    def dlog(
        self, base: ElemLike, target: ElemLike, options: Optional[Options] = None
    ) -> tuple[int, Stats]:
        """Pohlig-Hellman driver using the solver selected in ``options.solver``."""
        return self._whole(lib.ca_ffi_dlog, base, target, options)

    # ---- Cheon ------------------------------------------------------------

    def cheon(
        self, gen: ElemLike, g_alpha: ElemLike, g_alpha_d: ElemLike, d: int, max_exps: int = 0
    ) -> tuple[int, Stats]:
        """Cheon's attack: recover alpha from g, g^alpha and g^(alpha^d).

        ``d`` must divide ``order - 1`` (see :func:`cheon_best_divisor`).
        ``max_exps`` bounds the work (0 = unlimited; LimitError when exceeded).
        """
        alpha = ctypes.c_uint64(0)
        st = CStats()
        _lib.arm()
        rc = lib.ca_ffi_cheon(
            self._ctx,
            self._w(gen, "gen"),
            self._w(g_alpha, "g_alpha"),
            self._w(g_alpha_d, "g_alpha_d"),
            _lib.u64(d, "d"),
            _lib.u64(max_exps, "max_exps"),
            ctypes.byref(alpha),
            ctypes.byref(st),
        )
        _lib.check(rc)
        return alpha.value, Stats.from_c(st)

    def cheon_instance(self, gen: ElemLike, alpha: int, d: int) -> tuple[Elem, Elem]:
        """Build a Cheon instance ``(g^alpha, g^(alpha^d))`` for testing."""
        ga, gad = Words(), Words()
        _lib.arm()
        rc = lib.ca_ffi_cheon_instance(
            self._ctx, self._w(gen, "gen"), _lib.u64(alpha, "alpha"), _lib.u64(d, "d"), ga, gad
        )
        _lib.check(rc)
        return from_words(ga), from_words(gad)


def cheon_best_divisor(p: int) -> tuple[int, float]:
    """The divisor d of p-1 minimising Cheon's cost, and that cost in exponentiations."""
    cost = ctypes.c_double(0.0)
    d = lib.ca_ffi_cheon_best_divisor(_lib.u64(p, "p"), ctypes.byref(cost))
    if d == 0:
        raise InvalidError(Status.INVALID, f"cannot factor p-1 for p={p}")
    return d, cost.value


__all__ = ["Group", "cheon_best_divisor"]
