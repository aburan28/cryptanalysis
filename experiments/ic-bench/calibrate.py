#!/usr/bin/env python3
"""Measure the per-class weights that price opcount counters in one unit.

    python3 calibrate.py --out calibration.json

The unit is the reference picosecond (`rps`): one counted operation of class c on a
curve over F_2^n costs weights[n][c] rps, its batch-throughput time on the calibration
host (pdpkernel.c multiplies bit-serially, so field and curve weights grow with n).
Field, curve, Macaulay and enumeration classes are timed through their C batch paths,
so interpreter call overhead is not priced; it shows up as the wall/priced residual of
every run.  Mod-r classes are Python integer arithmetic and are timed as such.  Classes
that exist only as single ctypes calls (gf_inv, gf_lin) are priced as their single-call
time minus that of Field.trace, whose C body is a parity.

The weights are frozen once measured: priced totals are exact integer functions of the
deterministic counters, so two hosts running the same code agree on every total.  A new
measurement yields a new calibration_id, and ../ic-candidate-catalog/analyze.py refuses
to pair runs across calibrations.
"""

from __future__ import annotations

import argparse
import json
import platform
import random
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "pdp-degree-heuristics"))

import kernel  # noqa: E402
import opcount  # noqa: E402
from toycurve import ToyCurve, sha256_hex  # noqa: E402

UNIT = "rps: reference picoseconds, batch throughput on the calibration host"


def best_ns(fn, repeat: int = 7) -> float:
    times = []
    for _ in range(repeat):
        t0 = time.perf_counter_ns()
        fn()
        times.append(time.perf_counter_ns() - t0)
    return float(min(times))


def measure_shared() -> dict[str, dict]:
    """Classes whose cost does not depend on the field: Macaulay elimination and enumeration."""
    rng = np.random.default_rng(1)
    out: dict[str, dict] = {}
    ech = kernel.Echelon(4096)
    rows = rng.integers(0, 1 << 63, size=(4096, ech.words), dtype=np.uint64)
    t0 = time.perf_counter_ns()
    ech.add(rows)
    out["mac_op"] = {"ns": (time.perf_counter_ns() - t0) / ech.xors, "method": "Echelon.add, 4096 dense rows x 4096 columns"}
    nv = 22
    table = rng.integers(0, 1 << 63, size=1 << nv, dtype=np.uint64)
    out["anf_op"] = {"ns": best_ns(lambda: kernel.anf_zeros(table.copy(), nv, 16), 3) / ((nv + 2) << (nv - 1)),
                     "method": "anf_zeros on 22 variables, (N + 2) 2^(N-1) ops (includes the table copy)"}
    return out


def measure_field(n: int) -> dict[str, dict]:
    """Field, curve, system-slicing and mod-r classes on the toy curve over F_2^n."""
    import descent

    C = ToyCurve(n)
    K = C.K
    rng = np.random.default_rng(n)
    prng = random.Random(n)
    out: dict[str, dict] = {}
    a = rng.integers(1, 1 << n, size=1 << 20, dtype=np.uint64)
    b = rng.integers(1, 1 << n, size=1 << 20, dtype=np.uint64)
    out["gf_mul"] = {"ns": best_ns(lambda: K.mul_vec(a, b)) / len(a), "method": "Field.mul_vec, 2^20 products"}

    single = [int(v) for v in a[:20000]]

    def calls(fn):
        return best_ns(lambda: [fn(v) for v in single]) / len(single)

    overhead = calls(K.trace)
    for cls, fn, name in (("gf_inv", K.inv, "Field.inv"), ("gf_lin", K.half_trace, "Field.half_trace")):
        out[cls] = {"ns": max(0.001, calls(fn) - overhead),
                    "method": f"{name} single calls - Field.trace single calls (a parity: the ctypes call overhead)"}

    xs, ys = [], []
    while len(xs) < 2048:
        P = K.lift(prng.getrandbits(n))
        if P:
            xs.append(P[0])
            ys.append(P[1])
    xs, ys = np.array(xs, dtype=np.uint64), np.array(ys, dtype=np.uint64)
    out["ec_add"] = {"ns": best_ns(lambda: K.smul_batch(xs, ys, C.r), 3) / (len(xs) * opcount.smul_cost(C.r)),
                     "method": "Field.smul_batch by r, 2048 points"}
    lx = rng.integers(1, 1 << n, size=1 << 18, dtype=np.uint64)
    out["ec_lift"] = {"ns": best_ns(lambda: K.lift_batch(lx)) / len(lx), "method": "Field.lift_batch, 2^18 abscissae"}

    masks = np.arange(1 << 16, dtype=np.uint32)
    coeffs = rng.integers(1, 1 << n, size=1 << 16, dtype=np.uint64)
    out["sys_word"] = {"ns": best_ns(lambda: descent.BooleanSystem(16, n, masks, coeffs), 3) / (n * len(masks)),
                       "method": "BooleanSystem over 2^16 monomials"}

    r = C.r
    vals = [prng.randrange(1, r) for _ in range(200000)]

    def muladd():
        acc = 1
        for v in vals:
            acc = (v - acc * 12345) % r
        return acc

    out["modr_mul"] = {"ns": best_ns(muladd, 3) / len(vals), "method": "Python (v - a*c) % r loop"}
    inv_vals = vals[:50000]
    out["modr_inv"] = {"ns": best_ns(lambda: [pow(v, -1, r) for v in inv_vals], 3) / len(inv_vals),
                       "method": "Python pow(v, -1, r)"}
    return out


def calibration_record(degrees: list[int]) -> dict:
    shared = measure_shared()
    measured = {str(n): {**shared, **measure_field(n)} for n in degrees}
    weights = {n: {cls: max(1, round(1000 * m[cls]["ns"])) for cls in opcount.CLASSES} for n, m in measured.items()}
    identity = {"unit": UNIT, "weights_by_field_degree": weights}
    return {
        "schema": "ic-bench-calibration/1",
        "calibration_id": f"ICBCAL1h{sha256_hex(identity)[:12]}",
        **identity,
        "measured_ns": {n: {cls: {"ns": round(v["ns"], 4), "method": v["method"]} for cls, v in m.items()}
                        for n, m in measured.items()},
        "host": {"node": platform.node(), "machine": platform.machine(), "processor": platform.processor(),
                 "python": platform.python_version(), "numpy": np.__version__, "kernel_cflags": kernel.CFLAGS},
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def weights_for(calibration: dict, n: int) -> dict[str, int]:
    try:
        return calibration["weights_by_field_degree"][str(n)]
    except KeyError:
        raise ValueError(f"{calibration['calibration_id']} has no weights for n = {n}; recalibrate with --degrees") from None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--degrees", default="13,19,23,29", help="field degrees to calibrate")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    rec = calibration_record([int(v) for v in args.degrees.split(",")])
    text = json.dumps(rec, indent=1, sort_keys=True) + "\n"
    if args.out:
        Path(args.out).write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
