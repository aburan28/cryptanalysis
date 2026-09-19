"""Number-theory helpers exported by the library (all arguments are < 2^64)."""

from __future__ import annotations

import ctypes

from . import _lib
from ._lib import lib


def is_prime(n: int) -> bool:
    """Deterministic primality test for ``n < 2^64``."""
    return bool(lib.ca_ffi_is_prime(_lib.u64(n, "n")))


def next_prime(n: int) -> int:
    """The smallest prime strictly greater than ``n``."""
    return lib.ca_ffi_next_prime(_lib.u64(n, "n"))


def primitive_root(p: int) -> int:
    """The smallest primitive root modulo the prime ``p``."""
    return lib.ca_ffi_primitive_root(_lib.u64(p, "p"))


def powmod(b: int, e: int, m: int) -> int:
    """``b**e mod m``."""
    return lib.ca_ffi_powmod(_lib.u64(b, "b"), _lib.u64(e, "e"), _lib.u64(m, "m"))


def invmod(a: int, m: int) -> int:
    """The inverse of ``a`` modulo ``m`` (0 if it does not exist)."""
    return lib.ca_ffi_invmod(_lib.u64(a, "a"), _lib.u64(m, "m"))


_MAX_DISTINCT_PRIME_FACTORS = 16  # a 64-bit integer has at most 15


def factorize(n: int) -> list[tuple[int, int]]:
    """Prime factorisation of ``n`` as ``[(prime, exponent), ...]`` in increasing order."""
    n = _lib.u64(n, "n")
    cap = _MAX_DISTINCT_PRIME_FACTORS
    while True:
        primes = (ctypes.c_uint64 * cap)()
        exps = (ctypes.c_uint * cap)()
        count = lib.ca_ffi_factorize(n, primes, exps, cap)
        if count <= cap:
            return [(primes[i], exps[i]) for i in range(count)]
        cap = count  # pragma: no cover - cannot happen for 64-bit n


__all__ = ["factorize", "invmod", "is_prime", "next_prime", "powmod", "primitive_root"]
