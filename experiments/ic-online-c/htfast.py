"""ctypes bindings for htfast.c: batched PDP2ht attempts (v1), the previous C oracle (v0), and rho."""

from __future__ import annotations

import ctypes
import hashlib
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PDP = HERE.parent / "pdp-degree-heuristics"
sys.path.insert(0, str(PDP))

from factor_base import FactorBase, _columns_of_rows, kernel_basis  # noqa: E402
from htsolver import HalfTraceSolver  # noqa: E402
from toycurve import ToyCurve  # noqa: E402

SOURCE = HERE / "htfast.c"
CC = os.environ.get("HTFAST_CC", "gcc")
CFLAGS = ["-O3", "-march=native", "-mpclmul", "-shared", "-fPIC", "-std=gnu11"]
HIT_WORDS = 7
U64, P = ctypes.c_uint64, ctypes.POINTER
_LIB = None


def source_sha256() -> str:
    return hashlib.sha256(SOURCE.read_bytes()).hexdigest()


def lib() -> ctypes.CDLL:
    global _LIB
    if _LIB is None:
        out = HERE / "build" / hashlib.sha256((source_sha256() + CC + " ".join(CFLAGS)).encode()).hexdigest()[:16] / "libhtfast.so"
        if not out.exists():
            out.parent.mkdir(parents=True, exist_ok=True)
            tmp = out.with_suffix(f".{os.getpid()}.so")
            subprocess.run([CC, *CFLAGS, "-o", str(tmp), str(SOURCE)], check=True)
            os.replace(tmp, out)
        L = ctypes.CDLL(str(out))
        L.htf_init.restype = ctypes.c_void_p
        L.htf_init.argtypes = [ctypes.c_int, U64, U64, U64, U64, ctypes.c_int, P(U64), ctypes.c_int, P(U64), U64,
                               P(U64), P(U64), ctypes.c_int]
        L.htf_free.argtypes = [ctypes.c_void_p]
        L.htf_smul.argtypes = [ctypes.c_void_p, U64, U64, ctypes.c_int, P(U64), ctypes.c_int, P(U64)]
        L.htf_add.argtypes = [ctypes.c_void_p, P(U64), P(U64), P(U64)]
        L.htf_chain.argtypes = [ctypes.c_void_p, P(U64), P(U64), ctypes.c_int, P(U64), P(U64), P(ctypes.c_ubyte)]
        L.htf_run.restype = ctypes.c_int
        L.htf_run.argtypes = [ctypes.c_void_p, ctypes.c_int, P(U64), P(U64), P(ctypes.c_ubyte), U64, U64,
                              P(ctypes.c_longlong), P(ctypes.c_int), ctypes.c_int, ctypes.c_int, P(U64), ctypes.c_int,
                              P(ctypes.c_longlong)]
        L.htf_run_v0.restype = ctypes.c_int
        L.htf_run_v0.argtypes = [ctypes.c_void_p, P(U64), P(ctypes.c_ubyte), U64, U64, P(ctypes.c_longlong),
                                 P(ctypes.c_int), ctypes.c_int, ctypes.c_int, P(U64), ctypes.c_int,
                                 P(ctypes.c_longlong)]
        L.htf_rho.restype = ctypes.c_int
        L.htf_rho.argtypes = [ctypes.c_void_p, ctypes.c_int, P(U64), P(U64), P(U64), P(U64), P(U64), P(U64), P(U64),
                              P(U64), U64, U64, ctypes.c_void_p, ctypes.c_longlong, ctypes.c_longlong, P(U64),
                              P(ctypes.c_longlong)]
        _LIB = L
    return _LIB


def ptr(a: np.ndarray, t=U64):
    return a.ctypes.data_as(P(t))


INF = (0, 0, 1)
DP_DTYPE = np.dtype([("x", "<u8"), ("y", "<u8"), ("a", "<u8"), ("b", "<u8")])


class Kernel:
    """One factor base's tables in C, with the curve operations used by the pipeline."""

    def __init__(self, fb: FactorBase, cap: int = 4096):
        C, K = fb.curve, fb.curve.K
        self.fb, self.C, self.n = fb, C, C.n
        sv = HalfTraceSolver(fb)
        self.sv = sv
        n, nb = C.n, (C.n + 7) // 8
        self.l, self.nchk = sv.l, len(sv.checks)
        vchecks = kernel_basis(_columns_of_rows(sv.basis, n), n)
        ht = np.zeros(nb * 256, dtype=np.uint64)
        syn = np.zeros(nb * 256, dtype=np.uint64)
        for j in range(nb):
            for b in range(256):
                z = (b << (8 * j)) & ((1 << n) - 1)
                ht[j * 256 + b] = K.half_trace(z) if z else 0
                syn[j * 256 + b] = sum((bin(h & z).count("1") & 1) << r for r, h in enumerate(vchecks))
        self.trmask = sum(K.trace(1 << j) << j for j in range(n))
        basis = np.array(sv.basis, dtype=np.uint64)
        checks = np.array(sv.checks or [0], dtype=np.uint64)
        self.ctx = lib().htf_init(n, U64(C.mod & ((1 << n) - 1)), U64(C.a2), U64(C.b), U64(sv.sqrt_b), sv.l,
                                  ptr(basis), self.nchk, ptr(checks), U64(self.trmask), ptr(ht), ptr(syn), cap)
        if not self.ctx:
            raise ValueError("htfast needs odd n <= 63 and l + 1, nchk + 1 <= 64")
        self._words = (C.r.bit_length() + 63) // 64 + 1

    def __del__(self):
        if getattr(self, "ctx", None):
            lib().htf_free(self.ctx)

    # ------------------------------------------------------------ curve
    def smul(self, Pt: tuple, k: int) -> tuple:
        k %= self.C.r
        words = np.array([(k >> (64 * i)) & ((1 << 64) - 1) for i in range(self._words)], dtype=np.uint64)
        out = np.zeros(3, dtype=np.uint64)
        x, y, inf = (*Pt, 0) if len(Pt) == 2 else Pt
        lib().htf_smul(self.ctx, U64(x), U64(y), int(inf), ptr(words), self._words, ptr(out))
        return (int(out[0]), int(out[1]), int(out[2]))

    def add(self, A: tuple, B: tuple) -> tuple:
        a = np.array(A if len(A) == 3 else (*A, 0), dtype=np.uint64)
        b = np.array(B if len(B) == 3 else (*B, 0), dtype=np.uint64)
        out = np.zeros(3, dtype=np.uint64)
        lib().htf_add(self.ctx, ptr(a), ptr(b), ptr(out))
        return (int(out[0]), int(out[1]), int(out[2]))

    def chain(self, Pt: tuple, step: tuple, W: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        X = np.zeros(W, dtype=np.uint64)
        Y = np.zeros(W, dtype=np.uint64)
        inf = np.zeros(W, dtype=np.uint8)
        a = np.array(Pt if len(Pt) == 3 else (*Pt, 0), dtype=np.uint64)
        s = np.array(step if len(step) == 3 else (*step, 0), dtype=np.uint64)
        lib().htf_chain(self.ctx, ptr(a), ptr(s), W, ptr(X), ptr(Y), ptr(inf, ctypes.c_ubyte))
        return X, Y, inf


class Walk:
    """W walk points R_w = P + (w + 1) step advancing by W step: attempt t W + w + 1 is P + i step."""

    def __init__(self, k: Kernel, P0: tuple, step: tuple, W: int):
        self.k, self.W = k, W
        self.X, self.Y, self.inf = k.chain(P0, step, W)
        stride = k.smul(step, W)
        if stride[2]:
            raise ValueError("W step is the identity")
        self.sx, self.sy = stride[0], stride[1]
        self.round = np.zeros(1, dtype=np.int64)
        self.pending = np.zeros(1, dtype=np.int32)
        self.stats = np.zeros(8, dtype=np.int64)

    def run(self, rounds: int, stop_on_hit: bool, max_hits: int = 4096) -> np.ndarray:
        hits = np.zeros(max_hits * HIT_WORDS, dtype=np.uint64)
        nh = lib().htf_run(self.k.ctx, self.W, ptr(self.X), ptr(self.Y), ptr(self.inf, ctypes.c_ubyte),
                           U64(self.sx), U64(self.sy), ptr(self.round, ctypes.c_longlong),
                           ptr(self.pending, ctypes.c_int), rounds, int(stop_on_hit), ptr(hits), max_hits,
                           ptr(self.stats, ctypes.c_longlong))
        return hits[: min(nh, max_hits) * HIT_WORDS].reshape(-1, HIT_WORDS)


class WalkV0:
    """The previous oracle's walk: R <- R + step, one attempt per point (attempt i is P + i step)."""

    def __init__(self, k: Kernel, P0: tuple, step: tuple):
        self.k = k
        self.R = np.array(P0[:2], dtype=np.uint64)
        self.inf = np.array([P0[2] if len(P0) == 3 else 0], dtype=np.uint8)
        self.sx, self.sy = step[0], step[1]
        self.index = np.zeros(1, dtype=np.int64)
        self.pending = np.ones(1, dtype=np.int32)
        self.stats = np.zeros(8, dtype=np.int64)

    def run(self, attempts: int, stop_on_hit: bool, max_hits: int = 4096) -> np.ndarray:
        hits = np.zeros(max_hits * HIT_WORDS, dtype=np.uint64)
        nh = lib().htf_run_v0(self.k.ctx, ptr(self.R), ptr(self.inf, ctypes.c_ubyte), U64(self.sx), U64(self.sy),
                              ptr(self.index, ctypes.c_longlong), ptr(self.pending, ctypes.c_int), attempts,
                              int(stop_on_hit), ptr(hits), max_hits, ptr(self.stats, ctypes.c_longlong))
        return hits[: min(nh, max_hits) * HIT_WORDS].reshape(-1, HIT_WORDS)


def rho_call(k: Kernel, W: int, X, Y, A, B, TX, TY, TC, TD, dp_mask: int, table: np.ndarray, rounds: int,
             out: np.ndarray, stats: np.ndarray) -> int:
    return lib().htf_rho(k.ctx, W, ptr(X), ptr(Y), ptr(A), ptr(B), ptr(TX), ptr(TY), ptr(TC), ptr(TD),
                         U64(k.C.r), U64(dp_mask), table.ctypes.data_as(ctypes.c_void_p), len(table), rounds,
                         ptr(out), ptr(stats, ctypes.c_longlong))


def curve(n: int) -> ToyCurve:
    return ToyCurve(n)
