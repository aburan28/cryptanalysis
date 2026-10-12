#!/usr/bin/env python3
"""Courtois's common-factor restriction, measured as a covering of V by sub-bases.

Courtois (ePrint 2016/003, Sec. 2.5) restricts two-point decompositions over the polynomial-degree
subspace to pairs whose x-coordinates (as polynomials) share a factor M of degree delta.  For the
prefix base V = span{1, z, ..., z^(l-1)} that is exactly a decomposition over the subspace

    W_M = M * span{1, z, ..., z^(l-delta-1)}  (subset of V, no reduction since deg < l < n),

whose product space has dimension 2(l - delta) - 1, so W_M is linearizable when 3(l - delta) - 1 <= n
even if V is not.  Taking every monic M of degree delta covers part of V's decompositions with 2^delta
linear oracle calls per attempt.  This measures, exactly:

  * the yield of the cover, p_cover = |union_M D(W_M)| / (r - 1), against V's own p_dec;
  * the per-attempt cost, 2^delta half-trace oracles on the W_M (each below the limit);
  * the resulting one-target online cost, against the half-trace enumeration on V itself.

The factor-base columns stay those of V (every W_M lies in V), so the setup is unchanged.

    python3 gcdcover.py --n 19 23 --l 8 9 10 --delta 1 2 3
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "pdp-degree-heuristics"))
sys.path.insert(0, str(HERE.parent / "ic-bench"))
sys.path.insert(0, str(HERE))

from factor_base import FactorBase  # noqa: E402
from htsolver import HalfTraceSolver  # noqa: E402
from toycurve import ToyCurve, canonical  # noqa: E402


def cover_bases(C: ToyCurve, l: int, delta: int) -> list[FactorBase]:
    """W_M for every monic M of degree delta (polynomial basis, M = z^delta + lower terms)."""
    K = C.K
    out = []
    for low in range(1 << delta):
        M = (1 << delta) | low
        basis = [K.mul(M, 1 << j) for j in range(l - delta)]
        out.append(FactorBase(C, "gcdcover", l - delta, 0, basis=basis, params={"M": M, "delta": delta}))
    return out


def main() -> None:
    import halftrace
    import online
    from calibrate import weights_for

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, nargs="+", required=True)
    ap.add_argument("--l", type=int, nargs="+", required=True)
    ap.add_argument("--delta", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--calibration", default=str(HERE / "results" / "calibration-n19-23-41.json"))
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    cal = json.loads(Path(args.calibration).read_text())
    out = open(args.out, "a") if args.out else None
    for n in args.n:
        C = ToyCurve(n)
        w = weights_for(cal, n)
        rho = round((3.141592653589793 * C.r / 2) ** 0.5) * w["ec_add"]
        step = w["ec_add"]
        for l in args.l:
            V = FactorBase(C, "prefix", l, 1)
            DV = {tuple(map(int, p)) for p in online.decomposable_points(V).tolist()}
            pV = len(DV) / (C.r - 1)
            htV = halftrace.probe(V, w, fails=40, successes=10)
            online_V = (1 / pV) * (htV["c_fail_ops"] + step)
            for delta in args.delta:
                if l - delta < 2:
                    continue
                Ws = cover_bases(C, l, delta)
                union = set()
                for W in Ws:
                    union |= {tuple(map(int, p)) for p in online.decomposable_points(W).tolist()}
                assert union <= DV, "a cover decomposition is not a decomposition over V"
                pc = len(union) / (C.r - 1)
                c_one = halftrace.probe(Ws[0], w, fails=40, successes=10)["c_fail_ops"]
                per_attempt = len(Ws) * c_one + step
                online_cover = per_attempt / pc if pc else None
                sv = HalfTraceSolver(Ws[0])
                rec = {"schema": "fb-search-gcdcover/1", "kind": "stage", "n": n, "l": l, "delta": delta,
                       "calibration_id": cal["calibration_id"], "V_excess": HalfTraceSolver(V).excess(),
                       "W_excess": sv.excess(), "covers": len(Ws), "p_dec_V": pV, "p_cover": pc,
                       "yield_fraction": pc / pV, "c_attempt_cover": per_attempt,
                       "c_attempt_enum_V": htV["c_fail_ops"] + step,
                       "online_ops_cover": online_cover, "online_ops_enum_V": online_V,
                       "online_cover_over_enum": online_cover / online_V if online_cover else None,
                       "online_cover_over_rho": online_cover / rho if online_cover else None,
                       "online_enum_over_rho": online_V / rho}
                print(f"n{n} l{l} delta{delta}: V e={rec['V_excess']:+d}, W e={rec['W_excess']:+d}, "
                      f"yield fraction {rec['yield_fraction']:.3f} (2^-delta = {2**-delta:.3f}), "
                      f"online cover/enum = {rec['online_cover_over_enum']:.2f}, "
                      f"cover/rho = {rec['online_cover_over_rho']:.2f}, enum/rho = {rec['online_enum_over_rho']:.2f}",
                      flush=True)
                if out:
                    out.write(canonical(rec) + "\n")


if __name__ == "__main__":
    main()
