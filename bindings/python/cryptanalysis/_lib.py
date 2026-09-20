"""Locate and load ``libcryptanalysis`` and declare its ctypes prototypes.

Nothing in here is part of the public API; use :mod:`cryptanalysis` instead.

Search order for the shared library:

1. ``$CRYPTANALYSIS_LIB`` (full path to the shared object),
2. a shared library shipped inside this package directory
   (``libcryptanalysis*`` or ``_cryptanalysis*``; ``setup.py`` puts it there),
3. ``build/libcryptanalysis.{so,dylib}`` of a developer checkout, i.e.
   ``../../build`` relative to ``bindings/python`` (this package's parent),
4. ``ctypes.util.find_library("cryptanalysis")`` (system-wide install).
"""

from __future__ import annotations

import ctypes
import ctypes.util
import glob
import os
from ctypes import (
    POINTER,
    Structure,
    c_char_p,
    c_double,
    c_int,
    c_int32,
    c_size_t,
    c_uint,
    c_uint32,
    c_uint64,
    c_void_p,
)
from typing import TYPE_CHECKING, Iterator

from .errors import CryptanalysisError, Status, exception_for_status

ENV_VAR = "CRYPTANALYSIS_LIB"
U64_MAX = (1 << 64) - 1

# --------------------------------------------------------------------------
# POD structs (field-for-field copies of the C headers)
# --------------------------------------------------------------------------


class CStats(Structure):
    """``ca_stats`` from ca_types.h."""

    _fields_ = [
        ("group_ops", c_uint64),
        ("iterations", c_uint64),
        ("table_entries", c_uint64),
        ("collisions", c_uint64),
        ("bytes_peak", c_uint64),
        ("seconds", c_double),
        ("threads", c_uint32),
        ("reserved", c_uint32),
    ]


class COptions(Structure):
    """``ca_ffi_options`` from ca_ffi.h."""

    _fields_ = [
        ("threads", c_uint32),
        ("reserved0", c_uint32),
        ("seed", c_uint64),
        ("max_ops", c_uint64),
        ("bsgs_table_size", c_uint64),
        ("rho_r", c_uint32),
        ("rho_dp_bits", c_int32),
        ("rho_walks_per_thread", c_uint32),
        ("rho_negation_map", c_int32),
        ("rho_max_table_entries", c_uint64),
        ("kangaroo_herd_size", c_uint32),
        ("kangaroo_dp_bits", c_int32),
        ("kangaroo_jumps", c_uint32),
        ("reserved1", c_uint32),
        ("grumpy_m", c_uint64),
        ("grumpy_alpha", c_double),
        ("solver", c_int32),
        ("reserved2", c_int32),
        ("bsgs_max_prime", c_uint64),
    ]


class CICParams(Structure):
    """``ca_ic_params`` from ca_indexcalc.h (``method`` is a C enum -> int)."""

    _fields_ = [
        ("method", c_int),
        ("factor_base_bound", c_uint32),
        ("sieve_radius", c_uint32),
        ("threads", c_uint32),
        ("extra_relations", c_uint32),
        ("seed", c_uint64),
        ("max_relation_tries", c_uint64),
        ("verbose", c_int),
    ]


class CICStats(Structure):
    """``ca_ic_stats`` from ca_indexcalc.h."""

    _fields_ = [
        ("factor_base_size", c_uint32),
        ("unknowns", c_uint32),
        ("relations", c_uint32),
        ("verified_logs", c_uint32),
        ("sieve_candidates", c_uint64),
        ("smooth_tests", c_uint64),
        ("sieve_seconds", c_double),
        ("linalg_seconds", c_double),
        ("total_seconds", c_double),
        ("lanczos_iterations", c_uint32),
        ("threads", c_uint32),
    ]


Words = c_uint64 * 4  # uint64_t[4] element words
P64 = POINTER(c_uint64)

if TYPE_CHECKING:
    # `Words` is a ctypes array *class* built by multiplication, which type
    # checkers cannot use in an annotation.  `WordArray` is the same thing
    # spelled in a way they understand; at run time it is just `Words`.
    WordArray = ctypes.Array[c_uint64]
else:
    WordArray = Words

# --------------------------------------------------------------------------
# Locating the shared library
# --------------------------------------------------------------------------

_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
_DIST_DIR = os.path.dirname(_PKG_DIR)  # bindings/python
_SHLIB_SUFFIXES = (".so", ".dylib", ".dll", ".pyd")


def _looks_like_shlib(path: str) -> bool:
    base = os.path.basename(path)
    return base.endswith(_SHLIB_SUFFIXES) or ".so." in base


def _candidates() -> Iterator[tuple[str, str]]:
    """Yield ``(origin, path)`` in search order."""
    for pattern in ("libcryptanalysis*", "_cryptanalysis*"):
        for path in sorted(glob.glob(os.path.join(_PKG_DIR, pattern))):
            if _looks_like_shlib(path):
                yield "package directory", path
    build = os.path.normpath(os.path.join(_DIST_DIR, "..", "..", "build"))
    for name in ("libcryptanalysis.so", "libcryptanalysis.dylib"):
        yield "developer build directory", os.path.join(build, name)
    found = ctypes.util.find_library("cryptanalysis")
    if found:
        yield "ctypes.util.find_library", found


_BUILD_HELP = (
    "Build the C library first, e.g. from the repository root:\n"
    "    cmake -S . -B build && cmake --build build -j4\n"
    "or install this package with `pip install .` (which compiles it into the\n"
    f"package), or point ${ENV_VAR} at an existing libcryptanalysis shared object."
)


def _load() -> tuple[ctypes.CDLL, str]:
    env = os.environ.get(ENV_VAR)
    if env:
        try:
            return ctypes.CDLL(env), env
        except OSError as exc:
            raise ImportError(
                f"cryptanalysis: ${ENV_VAR}={env!r} could not be loaded: {exc}\n{_BUILD_HELP}"
            ) from exc
    tried: list[str] = []
    for origin, path in _candidates():
        if os.sep in path and not os.path.exists(path):
            tried.append(f"  - {path} ({origin}): not found")
            continue
        try:
            return ctypes.CDLL(path), path
        except OSError as exc:
            tried.append(f"  - {path} ({origin}): {exc}")
    raise ImportError(
        "cryptanalysis: could not find the libcryptanalysis shared library. Tried:\n"
        + ("\n".join(tried) if tried else "  (nothing)")
        + "\n"
        + _BUILD_HELP
    )


lib, library_path = _load()

# --------------------------------------------------------------------------
# Prototypes
# --------------------------------------------------------------------------

_CTX = c_void_p  # opaque ca_ctx *
_ICCTX = c_void_p  # opaque ca_ic_ctx *

_PROTOTYPES: dict[str, tuple[object, list]] = {
    # ca_types.h
    "ca_version": (c_char_p, []),
    "ca_status_string": (c_char_p, [c_int]),
    "ca_last_error": (c_void_p, []),
    # groups
    "ca_ctx_new_zp": (_CTX, [c_uint64, c_uint64]),
    "ca_ctx_new_ec": (_CTX, [c_uint64, c_uint64, c_uint64, c_uint64]),
    "ca_ctx_free": (None, [_CTX]),
    "ca_ctx_kind": (c_int, [_CTX]),
    "ca_ctx_p": (c_uint64, [_CTX]),
    "ca_ctx_order": (c_uint64, [_CTX]),
    "ca_ctx_cofactor": (c_uint64, [_CTX]),
    "ca_ctx_set_order": (None, [_CTX, c_uint64, c_uint64]),
    "ca_ctx_curve_a": (c_uint64, [_CTX]),
    "ca_ctx_curve_b": (c_uint64, [_CTX]),
    # elements
    "ca_ctx_validate": (c_int, [_CTX, P64]),
    "ca_ctx_identity": (c_int, [_CTX, P64]),
    "ca_ctx_is_identity": (c_int, [_CTX, P64]),
    "ca_ctx_op": (c_int, [_CTX, P64, P64, P64]),
    "ca_ctx_inv": (c_int, [_CTX, P64, P64]),
    "ca_ctx_mul": (c_int, [_CTX, P64, P64, c_uint64]),
    "ca_ctx_equal": (c_int, [_CTX, P64, P64]),
    "ca_ctx_elem_order": (c_int, [_CTX, P64, P64]),
    "ca_ctx_find_generator": (c_int, [_CTX, P64, c_uint64]),
    "ca_ctx_random_element": (c_int, [_CTX, P64, c_uint64]),
    "ca_ctx_lift_x": (c_int, [_CTX, P64, c_uint64]),
    "ca_ec_order": (c_int, [c_uint64, c_uint64, c_uint64, P64]),
    # options / sizes
    "ca_ffi_options_default": (None, [POINTER(COptions)]),
    "ca_ffi_options_size": (c_size_t, []),
    "ca_stats_size": (c_size_t, []),
    "ca_ic_params_size": (c_size_t, []),
    "ca_ic_stats_size": (c_size_t, []),
    # solvers
    "ca_ffi_bsgs": (
        c_int,
        [_CTX, P64, P64, c_uint64, c_uint64, POINTER(COptions), P64, POINTER(CStats)],
    ),
    "ca_ffi_kangaroo": (
        c_int,
        [_CTX, P64, P64, c_uint64, c_uint64, POINTER(COptions), P64, POINTER(CStats)],
    ),
    "ca_ffi_grumpy": (
        c_int,
        [_CTX, P64, P64, c_uint64, c_uint64, POINTER(COptions), P64, POINTER(CStats)],
    ),
    "ca_ffi_rho": (c_int, [_CTX, P64, P64, POINTER(COptions), P64, POINTER(CStats)]),
    "ca_ffi_dlog": (c_int, [_CTX, P64, P64, POINTER(COptions), P64, POINTER(CStats)]),
    "ca_ffi_precomp": (
        c_int,
        [_CTX, P64, P64, c_int32, c_uint64, c_double, c_uint32, c_uint64, P64, POINTER(CStats)],
    ),
    # curve dispatch (GLV endomorphism)
    "ca_ffi_curve_detect": (
        c_int,
        [
            c_uint64,
            c_uint64,
            c_uint64,
            c_uint64,
            POINTER(c_int32),
            POINTER(c_uint32),
            P64,
            P64,
            POINTER(c_double),
        ],
    ),
    "ca_ffi_curve_by_name": (c_int, [c_char_p, P64, P64, P64, P64]),
    "ca_ffi_curve_name": (c_char_p, [c_size_t]),
    "ca_ffi_curve_solve": (
        c_int,
        [_CTX, P64, P64, c_uint64, P64, POINTER(c_int32), POINTER(c_uint32), P64, POINTER(CStats)],
    ),
    # Cheon
    "ca_ffi_cheon": (c_int, [_CTX, P64, P64, P64, c_uint64, c_uint64, P64, POINTER(CStats)]),
    "ca_ffi_cheon_instance": (c_int, [_CTX, P64, c_uint64, c_uint64, P64, P64]),
    "ca_ffi_cheon_best_divisor": (c_uint64, [c_uint64, POINTER(c_double)]),
    # index calculus
    "ca_ffi_ic_solve": (
        c_int,
        [c_uint64, c_uint64, c_uint64, POINTER(CICParams), P64, POINTER(CICStats)],
    ),
    "ca_ic_params_default": (None, [POINTER(CICParams)]),
    "ca_ic_auto_params": (None, [c_uint, POINTER(c_uint32), POINTER(c_uint32)]),
    "ca_ic_precompute": (
        c_int,
        [c_uint64, c_uint64, POINTER(CICParams), POINTER(_ICCTX), POINTER(CICStats)],
    ),
    "ca_ic_free": (None, [_ICCTX]),
    "ca_ic_log": (c_int, [_ICCTX, c_uint64, P64, POINTER(CStats)]),
    "ca_ic_modulus": (c_uint64, [_ICCTX]),
    "ca_ic_factor_base_size": (c_uint32, [_ICCTX]),
    "ca_ic_factor_base_log": (c_uint64, [_ICCTX, c_uint32, POINTER(c_uint32), POINTER(c_int)]),
    "ca_ic_primitive_root": (c_uint64, [_ICCTX]),
    # number theory
    "ca_ffi_is_prime": (c_int, [c_uint64]),
    "ca_ffi_next_prime": (c_uint64, [c_uint64]),
    "ca_ffi_primitive_root": (c_uint64, [c_uint64]),
    "ca_ffi_powmod": (c_uint64, [c_uint64, c_uint64, c_uint64]),
    "ca_ffi_invmod": (c_uint64, [c_uint64, c_uint64]),
    "ca_ffi_factorize": (c_uint, [c_uint64, P64, POINTER(c_uint), c_uint]),
}


def _declare() -> None:
    missing = []
    for name, (restype, argtypes) in _PROTOTYPES.items():
        try:
            fn = getattr(lib, name)
        except AttributeError:
            missing.append(name)
            continue
        fn.restype = restype
        fn.argtypes = argtypes
    if missing:
        raise ImportError(
            f"cryptanalysis: {library_path} does not export {', '.join(missing)}; "
            "it is probably an outdated build. Rebuild the C library "
            "(cmake --build build) and try again."
        )


_declare()

# --------------------------------------------------------------------------
# Struct size verification against the library
# --------------------------------------------------------------------------


def _check_sizes() -> None:
    checks = (
        ("ca_ffi_options", COptions, lib.ca_ffi_options_size()),
        ("ca_stats", CStats, lib.ca_stats_size()),
        ("ca_ic_params", CICParams, lib.ca_ic_params_size()),
        ("ca_ic_stats", CICStats, lib.ca_ic_stats_size()),
    )
    bad = [
        f"{name}: ctypes={ctypes.sizeof(struct)} library={size}"
        for name, struct, size in checks
        if ctypes.sizeof(struct) != size
    ]
    if bad:
        raise ImportError(
            "cryptanalysis: struct layout mismatch between the Python bindings and "
            f"{library_path} ({'; '.join(bad)}). The bindings and the C library are "
            "out of sync; rebuild the library from the matching sources."
        )


_check_sizes()

# --------------------------------------------------------------------------
# Error plumbing
# --------------------------------------------------------------------------


def last_error() -> str:
    """Return the library's thread-local ``ca_last_error()`` text."""
    ptr = lib.ca_last_error()
    if not ptr:
        return ""
    return ctypes.string_at(ptr).decode("utf-8", "replace")


def status_string(status: int) -> str:
    """Return ``ca_status_string(status)``."""
    s = lib.ca_status_string(int(status))
    return s.decode("utf-8", "replace") if s else "unknown"


def _arm_error_buffer() -> str:
    """Overwrite the thread-local error buffer with a known sentinel.

    The C ABI never clears ``ca_last_error()``, so after an unrelated failure
    a later error that does not set a message would inherit a stale one.
    ``ca_ctx_new_zp(4, 0)`` always fails (4 is not an odd prime), sets a
    deterministic message and leaks nothing, so we use it to put the buffer
    into a known state right before every fallible call; afterwards a message
    equal to the sentinel means "the call did not describe its failure".
    """
    if lib.ca_ctx_new_zp(4, 0):  # pragma: no cover - cannot happen
        raise RuntimeError("cryptanalysis: ca_ctx_new_zp(4, 0) unexpectedly succeeded")
    return last_error()


_SENTINEL = _arm_error_buffer()


def arm() -> None:
    """Put the error buffer into the sentinel state (call before a fallible call)."""
    if _SENTINEL:
        _arm_error_buffer()


def fresh_error() -> str:
    """The message set by the call made after the last :func:`arm`, or ``""``."""
    msg = last_error()
    if _SENTINEL and msg == _SENTINEL:
        return ""
    return msg


def make_error(status: int, fallback: str = "") -> CryptanalysisError:
    """Build the exception for a non-zero status using ``ca_last_error()``."""
    status = int(status)
    msg = fresh_error() or fallback or status_string(status)
    return exception_for_status(status)(status, msg)


def check(status: int, fallback: str = "") -> None:
    """Raise the matching exception when ``status`` is not ``CA_OK``."""
    if status != Status.OK:
        raise make_error(status, fallback)


def u64(value: int, name: str = "value") -> int:
    """Validate that ``value`` is an int in ``[0, 2**64)`` and return it."""
    if isinstance(value, bool) or not isinstance(value, int):
        try:
            value = value.__index__()
        except (AttributeError, TypeError):
            raise TypeError(f"{name} must be an int, not {type(value).__name__}") from None
    if value < 0 or value > U64_MAX:
        raise OverflowError(f"{name}={value} does not fit in an unsigned 64-bit integer")
    return value


def i32(value: int, name: str = "value") -> int:
    """Validate that ``value`` is an int in the ``int32_t`` range and return it."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int, not {type(value).__name__}")
    if value < -(1 << 31) or value >= (1 << 31):
        raise OverflowError(f"{name}={value} does not fit in a signed 32-bit integer")
    return value


def u32(value: int, name: str = "value") -> int:
    """Validate that ``value`` is an int in the ``uint32_t`` range and return it."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int, not {type(value).__name__}")
    if value < 0 or value >= (1 << 32):
        raise OverflowError(f"{name}={value} does not fit in an unsigned 32-bit integer")
    return value


__all__ = [
    "ENV_VAR",
    "P64",
    "CICParams",
    "CICStats",
    "COptions",
    "CStats",
    "WordArray",
    "Words",
    "arm",
    "check",
    "fresh_error",
    "i32",
    "last_error",
    "lib",
    "library_path",
    "make_error",
    "status_string",
    "u32",
    "u64",
]
