"""ctypes bindings for native/libf83.dylib (fast F_(2^83) curve arithmetic).

Field elements cross the boundary as Python ints in the m83.py encoding.
"""
import ctypes
from pathlib import Path

import numpy as np

_LIB = ctypes.CDLL(str(Path(__file__).resolve().parents[1] / 'native' / 'libf83.dylib'))


class FE(ctypes.Structure):
    _fields_ = [('lo', ctypes.c_uint64), ('hi', ctypes.c_uint64)]


def fe(v):
    v = int(v)
    return FE(v & 0xFFFFFFFFFFFFFFFF, v >> 64)


def fe_array(vals):
    arr = (FE * max(1, len(vals)))()
    for i, v in enumerate(vals):
        v = int(v)
        arr[i].lo = v & 0xFFFFFFFFFFFFFFFF
        arr[i].hi = v >> 64
    return arr


def to_int(f):
    return int(f.lo) | (int(f.hi) << 64)


_LIB.f83_ratx.argtypes = [FE, ctypes.POINTER(FE), ctypes.c_int, ctypes.POINTER(ctypes.c_uint8)]
_LIB.f83_ratx_nested.argtypes = [FE, ctypes.POINTER(FE), ctypes.c_int, ctypes.POINTER(ctypes.c_uint64)]
_LIB.f83_points.argtypes = [FE, ctypes.POINTER(FE), ctypes.c_int, ctypes.POINTER(FE), ctypes.POINTER(ctypes.c_uint8)]
_LIB.f83_points.restype = ctypes.c_int
_LIB.f83_image.argtypes = [FE, ctypes.POINTER(FE), ctypes.POINTER(FE), ctypes.POINTER(ctypes.c_uint8), ctypes.c_int,
                           ctypes.c_int, ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_uint64),
                           ctypes.c_long, ctypes.POINTER(FE), ctypes.POINTER(ctypes.c_uint64), ctypes.c_long]
_LIB.f83_image.restype = ctypes.c_long
_LIB.f83_mul.argtypes = [FE, FE]
_LIB.f83_mul.restype = FE
_LIB.f83_inv.argtypes = [FE]
_LIB.f83_inv.restype = FE
_LIB.f83_trace.argtypes = [FE]
_LIB.f83_halftrace.argtypes = [FE]
_LIB.f83_halftrace.restype = FE
_LIB.f83_add.argtypes = [FE, FE, FE, FE, FE, ctypes.POINTER(FE), ctypes.POINTER(FE)]


def ratx(b, basis):
    """Truth table over masks of span(basis): 1 iff nonzero rational x."""
    k = len(basis)
    out = np.zeros(1 << k, dtype=np.uint8)
    _LIB.f83_ratx(fe(b), fe_array(basis), k, out.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)))
    return out


def ratx_nested(b, basis):
    k = len(basis)
    counts = (ctypes.c_uint64 * (k + 1))()
    _LIB.f83_ratx_nested(fe(b), fe_array(basis), k, counts)
    return [int(c) for c in counts]


def points(b, xs):
    """Sign-0 y (smaller encoding) and Z/4 tag of the sign-0 point for each x."""
    n = len(xs)
    ys = (FE * max(1, n))()
    tags = (ctypes.c_uint8 * max(1, n))()
    rc = _LIB.f83_points(fe(b), fe_array(xs), n, ys, tags)
    if rc:
        raise ValueError('f83_points failed: %d' % rc)
    return [to_int(ys[i]) for i in range(n)], [int(tags[i]) for i in range(n)]


def image(b, xs, ys, tags, s, dup_cap=0, targets_cap=0):
    """Exact s-summand image statistics (s = 3 or 4); see f83.c."""
    n = len(xs)
    stats = (ctypes.c_uint64 * 7)()
    dup = (ctypes.c_uint64 * max(2, 2 * dup_cap))() if dup_cap else None
    tgt = (FE * max(2, 2 * targets_cap))() if targets_cap else None
    tid = (ctypes.c_uint64 * max(1, targets_cap))() if targets_cap else None
    tag_arr = (ctypes.c_uint8 * max(1, n))(*tags)
    nd = _LIB.f83_image(fe(b), fe_array(xs), fe_array(ys), tag_arr, n, s, stats, dup, dup_cap, tgt, tid,
                        targets_cap)
    names = ['all_signed_tuples', 'infinity_tuples', 'full_distinct_targets', 'eligible_signed_tuples',
             'eligible_infinity', 'prime_subgroup_distinct_targets', 'eligible_duplicate_excess']
    out = dict(zip(names, (int(v) for v in stats)))
    if dup_cap:
        out['duplicates'] = [(int(dup[2 * i]), int(dup[2 * i + 1])) for i in range(min(nd, dup_cap))]
    if targets_cap:
        ntg = min(out['prime_subgroup_distinct_targets'], targets_cap)
        out['targets'] = [(to_int(tgt[2 * i]), to_int(tgt[2 * i + 1])) for i in range(ntg)]
        out['target_witnesses'] = [int(tid[i]) for i in range(ntg)]
    out['duplicate_members'] = int(nd)
    return out


def unpack_id(i, s):
    """Witness id -> list of (x index, sign)."""
    return [(((i >> (16 * t)) & 0xFFFF) >> 1, ((i >> (16 * t)) & 0xFFFF) & 1) for t in range(s)]


def mul(a, b):
    return to_int(_LIB.f83_mul(fe(a), fe(b)))


def inv(a):
    return to_int(_LIB.f83_inv(fe(a)))


def trace(a):
    return int(_LIB.f83_trace(fe(a)))


def add(b, P, Q):
    ox, oy = FE(), FE()
    inf = _LIB.f83_add(fe(b), fe(P[0]), fe(P[1]), fe(Q[0]), fe(Q[1]), ctypes.byref(ox), ctypes.byref(oy))
    return None if inf else (to_int(ox), to_int(oy))


_LIB.f83_pair_probe.argtypes = [FE, ctypes.POINTER(FE), ctypes.POINTER(FE), ctypes.c_int, ctypes.POINTER(FE),
                                ctypes.POINTER(FE), ctypes.c_int, ctypes.POINTER(ctypes.c_uint64),
                                ctypes.POINTER(ctypes.c_uint64), ctypes.c_long, ctypes.POINTER(ctypes.c_uint64)]
_LIB.f83_pair_probe.restype = ctypes.c_long


def pair_probe(b, xs, ys, targets, wcap=1024):
    """Signed four-summand decompositions of each target over a pair table."""
    n, nt = len(xs), len(targets)
    counts = (ctypes.c_uint64 * max(1, nt))()
    wit = (ctypes.c_uint64 * max(3, 3 * wcap))()
    stats = (ctypes.c_uint64 * 3)()
    nw = _LIB.f83_pair_probe(fe(b), fe_array(xs), fe_array(ys), n, fe_array([t[0] for t in targets]),
                             fe_array([t[1] for t in targets]), nt, counts, wit, wcap, stats)
    out = {'pair_entries': int(stats[0]), 'distinct_pair_sums': int(stats[1]),
           'pair_collision_excess': int(stats[2]), 'counts': [int(counts[i]) for i in range(nt)]}
    out['witnesses'] = [(int(wit[3 * i]), unpack_id(int(wit[3 * i + 1]), 2), unpack_id(int(wit[3 * i + 2]), 2))
                        for i in range(min(nw, wcap))]
    return out


def halftrace(a):
    return to_int(_LIB.f83_halftrace(fe(a)))


_LIB.f83_frobn.argtypes = [ctypes.POINTER(FE), ctypes.POINTER(FE), ctypes.c_long, ctypes.c_int]


def frobn(values, n):
    """[v^(2^n) for v in values], n mod 83."""
    count = len(values)
    if not count:
        return []
    out = (FE * count)()
    _LIB.f83_frobn(fe_array(values), out, count, int(n))
    return [to_int(out[i]) for i in range(count)]
