"""ctypes bindings for pdpkernel.c, compiled on first use.

The shared object is cached under build/<source-sha256-prefix>/ (ignored by git),
so a source change always rebuilds and every receipt can name the exact kernel
by `SOURCE_SHA256`.
"""

from __future__ import annotations

import ctypes
import hashlib
import os
import subprocess
from ctypes import POINTER, c_int, c_int32, c_longlong, c_size_t, c_uint8, c_uint32, c_uint64, c_void_p
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "pdpkernel.c"
SOURCE_SHA256 = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
CFLAGS = ["-O3", "-march=native", "-shared", "-fPIC", "-std=c11"]
INF_X = (1 << 64) - 1

_u64p = POINTER(c_uint64)
_u32p = POINTER(c_uint32)
_i32p = POINTER(c_int32)
_u8p = POINTER(c_uint8)
_llp = POINTER(c_longlong)

_SIGNATURES = {
    "ctx_size": (c_size_t, []),
    "ctx_init": (c_int, [c_void_p, c_int, c_uint64, c_uint64, c_uint64]),
    "gf_mul_x": (c_uint64, [c_void_p, c_uint64, c_uint64]),
    "gf_inv_x": (c_uint64, [c_void_p, c_uint64]),
    "gf_trace_x": (c_int, [c_void_p, c_uint64]),
    "gf_halftrace_x": (c_uint64, [c_void_p, c_uint64]),
    "gf_sqrt_x": (c_uint64, [c_void_p, c_uint64]),
    "gf_mul_const_batch": (None, [c_void_p, _u64p, c_int, c_uint64, _u64p]),
    "gf_mul_vec": (None, [c_void_p, _u64p, _u64p, c_int, _u64p]),
    "ec_add_x": (None, [c_void_p, c_uint64, c_uint64, c_uint64, c_uint64, _u64p]),
    "ec_mul_x": (None, [c_void_p, c_uint64, c_uint64, c_uint64, _u64p]),
    "ec_mul_batch": (None, [c_void_p, _u64p, _u64p, c_int, c_uint64, _u64p, _u64p]),
    "ec_lift_batch": (None, [c_void_p, _u64p, c_int, _u64p, _u8p]),
    "ec_pair_sums": (None, [c_void_p, _u64p, _u64p, c_int, _u64p, _u64p]),
    "ec_sub_from": (None, [c_void_p, c_uint64, c_uint64, _u64p, _u64p, c_int, _u64p, _u64p]),
    "mac_build_rows": (
        c_longlong,
        [c_int, _u32p, _i32p, _u32p, _i32p, c_int, _i32p, c_int, c_int, _u64p],
    ),
    "ech_new": (c_void_p, [c_int]),
    "ech_free": (None, [c_void_p]),
    "ech_extend": (c_int, [c_void_p, c_int]),
    "ech_words": (c_int, [c_void_p]),
    "ech_rank": (c_int, [c_void_p]),
    "ech_has_unit": (c_int, [c_void_p]),
    "ech_add": (c_int, [c_void_p, _u64p, c_int, c_int, _llp]),
    "ech_count_pivots_from": (c_int, [c_void_p, c_int]),
    "ech_pivots": (c_int, [c_void_p, _i32p]),
    "ech_row_pivots": (c_int, [c_void_p, _i32p]),
    "mac_mul_rows": (c_longlong, [c_void_p, _i32p, c_int, c_int, _u32p, _i32p, _u64p]),
    "anf_zeros": (c_longlong, [_u64p, c_int, _u32p, c_longlong]),
    "count_standard": (c_longlong, [_u32p, c_int, c_int]),
}

_LIB = None


def _build() -> Path:
    out_dir = HERE / "build" / SOURCE_SHA256[:16]
    lib = out_dir / "libpdpkernel.so"
    if lib.exists():
        return lib
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = out_dir / f"libpdpkernel.{os.getpid()}.so"
    cc = os.environ.get("CC", "gcc")
    subprocess.run([cc, *CFLAGS, "-o", str(tmp), str(SOURCE)], check=True)
    os.replace(tmp, lib)
    return lib


def lib() -> ctypes.CDLL:
    global _LIB
    if _LIB is None:
        handle = ctypes.CDLL(str(_build()))
        for name, (res, args) in _SIGNATURES.items():
            fn = getattr(handle, name)
            fn.restype = res
            fn.argtypes = args
        _LIB = handle
    return _LIB


def _p(a: np.ndarray, ptr):
    return a.ctypes.data_as(ptr)


def u64(a) -> np.ndarray:
    return np.ascontiguousarray(a, dtype=np.uint64)


class Field:
    """GF(2^n) in the polynomial basis modulo `mod` (bit n set), with a curve y^2+xy=x^3+a2x^2+b."""

    def __init__(self, n: int, mod: int, a2: int = 0, b: int = 1):
        self.n, self.mod, self.a2, self.b = n, mod, a2, b
        self.L = lib()
        self._ctx = ctypes.create_string_buffer(self.L.ctx_size())
        rc = self.L.ctx_init(self._ctx, n, mod, a2, b)
        if rc != 0:
            raise ValueError(f"ctx_init failed ({rc}) for n={n}, mod={mod:#x}")
        self._out = np.zeros(2, dtype=np.uint64)

    # field
    def mul(self, a: int, b: int) -> int:
        return self.L.gf_mul_x(self._ctx, a, b)

    def sqr(self, a: int) -> int:
        return self.L.gf_mul_x(self._ctx, a, a)

    def inv(self, a: int) -> int:
        if a == 0:
            raise ZeroDivisionError
        return self.L.gf_inv_x(self._ctx, a)

    def pow(self, a: int, e: int) -> int:
        r = 1
        while e:
            if e & 1:
                r = self.mul(r, a)
            a = self.sqr(a)
            e >>= 1
        return r

    def frob(self, a: int, k: int) -> int:
        for _ in range(k):
            a = self.sqr(a)
        return a

    def trace(self, a: int) -> int:
        return self.L.gf_trace_x(self._ctx, a)

    def half_trace(self, a: int) -> int:
        return self.L.gf_halftrace_x(self._ctx, a)

    def sqrt(self, a: int) -> int:
        return self.L.gf_sqrt_x(self._ctx, a)

    def mul_const(self, a: np.ndarray, k: int) -> np.ndarray:
        a = u64(a)
        out = np.empty_like(a)
        if len(a):
            self.L.gf_mul_const_batch(self._ctx, _p(a, _u64p), len(a), k, _p(out, _u64p))
        return out

    def mul_vec(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        a, b = u64(a), u64(b)
        out = np.empty_like(a)
        if len(a):
            self.L.gf_mul_vec(self._ctx, _p(a, _u64p), _p(b, _u64p), len(a), _p(out, _u64p))
        return out

    # curve (points are (x, y) with x == INF_X for the identity)
    def add(self, P: tuple[int, int], Q: tuple[int, int]) -> tuple[int, int]:
        self.L.ec_add_x(self._ctx, P[0], P[1], Q[0], Q[1], _p(self._out, _u64p))
        return int(self._out[0]), int(self._out[1])

    def neg(self, P: tuple[int, int]) -> tuple[int, int]:
        return P if P[0] == INF_X else (P[0], P[0] ^ P[1])

    def smul(self, P: tuple[int, int], k: int) -> tuple[int, int]:
        if k < 0:
            return self.smul(self.neg(P), -k)
        if k >= 1 << 64:
            raise ValueError("scalar exceeds 64 bits")
        self.L.ec_mul_x(self._ctx, P[0], P[1], k, _p(self._out, _u64p))
        return int(self._out[0]), int(self._out[1])

    def smul_batch(self, xs: np.ndarray, ys: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
        xs, ys = u64(xs), u64(ys)
        ox, oy = np.empty_like(xs), np.empty_like(ys)
        if len(xs):
            self.L.ec_mul_batch(self._ctx, _p(xs, _u64p), _p(ys, _u64p), len(xs), k, _p(ox, _u64p), _p(oy, _u64p))
        return ox, oy

    def lift_batch(self, xs: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        xs = u64(xs)
        ys = np.empty_like(xs)
        ok = np.empty(len(xs), dtype=np.uint8)
        if len(xs):
            self.L.ec_lift_batch(self._ctx, _p(xs, _u64p), len(xs), _p(ys, _u64p), _p(ok, _u8p))
        return ys, ok.astype(bool)

    def lift(self, x: int) -> tuple[int, int] | None:
        ys, ok = self.lift_batch(np.array([x], dtype=np.uint64))
        return (x, int(ys[0])) if ok[0] else None

    def on_curve(self, P: tuple[int, int]) -> bool:
        if P[0] == INF_X:
            return True
        x, y = P
        return self.sqr(y) ^ self.mul(x, y) == self.mul(self.sqr(x), x) ^ self.mul(self.a2, self.sqr(x)) ^ self.b

    def pair_sums(self, xs: np.ndarray, ys: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        xs, ys = u64(xs), u64(ys)
        k = len(xs) * (len(xs) + 1) // 2
        ox, oy = np.empty(k, dtype=np.uint64), np.empty(k, dtype=np.uint64)
        if k:
            self.L.ec_pair_sums(self._ctx, _p(xs, _u64p), _p(ys, _u64p), len(xs), _p(ox, _u64p), _p(oy, _u64p))
        return ox, oy

    def sub_from(self, R: tuple[int, int], xs: np.ndarray, ys: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        xs, ys = u64(xs), u64(ys)
        ox, oy = np.empty_like(xs), np.empty_like(ys)
        if len(xs):
            self.L.ec_sub_from(self._ctx, R[0], R[1], _p(xs, _u64p), _p(ys, _u64p), len(xs), _p(ox, _u64p), _p(oy, _u64p))
        return ox, oy


class Echelon:
    """Incremental GF(2) echelon basis; column c is bit c and the pivot is the highest set bit."""

    def __init__(self, ncols: int):
        self.L = lib()
        self._h = self.L.ech_new(max(1, ncols))
        if not self._h:
            raise MemoryError("ech_new")
        self.xors = 0

    def __del__(self):
        h = getattr(self, "_h", None)
        if h:
            self.L.ech_free(h)
            self._h = None

    @property
    def words(self) -> int:
        return self.L.ech_words(self._h)

    @property
    def rank(self) -> int:
        return self.L.ech_rank(self._h)

    @property
    def has_unit(self) -> bool:
        return bool(self.L.ech_has_unit(self._h))

    def extend(self, ncols: int) -> None:
        if self.L.ech_extend(self._h, ncols) != 0:
            raise MemoryError("ech_extend")

    def add(self, rows: np.ndarray, stop_on_unit: bool = False) -> int:
        rows = u64(rows)
        assert rows.ndim == 2 and rows.shape[1] == self.words
        x = c_longlong(0)
        used = self.L.ech_add(self._h, _p(rows, _u64p), rows.shape[0], int(stop_on_unit), ctypes.byref(x))
        if used < 0:
            raise MemoryError("ech_add")
        self.xors += x.value
        return used

    def pivots_from(self, col_lo: int) -> int:
        return self.L.ech_count_pivots_from(self._h, col_lo)

    def pivots(self) -> np.ndarray:
        out = np.empty(max(1, self.rank), dtype=np.int32)
        k = self.L.ech_pivots(self._h, _p(out, _i32p))
        return out[:k]

    def row_pivots(self) -> np.ndarray:
        """Pivot column of every basis row, in insertion order."""
        out = np.empty(max(1, self.rank), dtype=np.int32)
        k = self.L.ech_row_pivots(self._h, _p(out, _i32p))
        return out[:k]

    def mul_rows(self, idx: np.ndarray, nvars: int, pos2mask: np.ndarray, colidx: np.ndarray) -> tuple[np.ndarray, int]:
        """Rows x_j * b for the basis rows idx and every variable j, row-major (i, j)."""
        idx = np.ascontiguousarray(idx, dtype=np.int32)
        pos2mask = np.ascontiguousarray(pos2mask, dtype=np.uint32)
        colidx = np.ascontiguousarray(colidx, dtype=np.int32)
        out = np.zeros((len(idx) * nvars, self.words), dtype=np.uint64)
        ops = 0
        if len(idx):
            ops = self.L.mac_mul_rows(self._h, _p(idx, _i32p), len(idx), nvars, _p(pos2mask, _u32p), _p(colidx, _i32p), _p(out, _u64p))
        return out, int(ops)


def build_rows(
    words: int,
    eq_masks: np.ndarray,
    eq_off: np.ndarray,
    mult: np.ndarray,
    mult_eq: np.ndarray,
    colidx: np.ndarray,
    col_offset: int = 0,
    homog_degree: int = -1,
) -> tuple[np.ndarray, int]:
    eq_masks = np.ascontiguousarray(eq_masks, dtype=np.uint32)
    eq_off = np.ascontiguousarray(eq_off, dtype=np.int32)
    mult = np.ascontiguousarray(mult, dtype=np.uint32)
    mult_eq = np.ascontiguousarray(mult_eq, dtype=np.int32)
    colidx = np.ascontiguousarray(colidx, dtype=np.int32)
    out = np.zeros((len(mult), words), dtype=np.uint64)
    ops = 0
    if len(mult):
        ops = lib().mac_build_rows(
            words, _p(eq_masks, _u32p), _p(eq_off, _i32p), _p(mult, _u32p), _p(mult_eq, _i32p),
            len(mult), _p(colidx, _i32p), col_offset, homog_degree, _p(out, _u64p),
        )
    return out, int(ops)


def anf_zeros(table: np.ndarray, nv: int, max_out: int = 1 << 16) -> tuple[int, np.ndarray]:
    """Zeros of the F_2^n-valued Boolean function whose ANF coefficient of monomial mask is table[mask].

    The table is transformed in place.
    """
    assert table.dtype == np.uint64 and table.flags.c_contiguous and len(table) == 1 << nv
    out = np.empty(max_out, dtype=np.uint32)
    z = lib().anf_zeros(_p(table, _u64p), nv, _p(out, _u32p), max_out)
    return int(z), out[: min(z, max_out)]


def count_standard(leading: np.ndarray, nv: int) -> int:
    leading = np.ascontiguousarray(leading, dtype=np.uint32)
    s = lib().count_standard(_p(leading, _u32p), len(leading), nv)
    if s < 0:
        raise MemoryError("count_standard")
    return int(s)
