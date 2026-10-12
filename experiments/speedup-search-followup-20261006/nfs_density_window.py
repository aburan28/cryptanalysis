"""The exact NFS density window and the standard-parameter no-go calculation.

Setting.  An NFS sieve box of side S (S^2 cells).  A first-side filter returns
|W| = S^(2 - theta) survivors.  A dyadic second-side prime block has
residue-state dimension D = S^gamma with separation rank s = D^(1/2+o(1)).
The AVW route (avw_model.py) and the best elementary block comparator have
exponents

    T_AVW = max(2 - PRE_EXP*gamma,  2 - theta + QUERY_EXP*gamma)
    T_0   = min(2,  2 - theta + gamma/2)        # full scan  vs  sparse block checks

AVW is strictly better than T_0 iff both of its terms are below both of T_0's:

    2 - PRE_EXP*gamma   < 2 - theta + gamma/2   <=>  theta < (1/2 + PRE_EXP) gamma = 0.563 gamma
    2 - theta + Q*gamma < 2                     <=>  theta > QUERY_EXP gamma         = 0.437 gamma

(the other two inequalities hold automatically for gamma > 0).  Hence the
exact strict window

    0.437 gamma < theta < 0.563 gamma,

and with the theorem's ceiling gamma <= 1/18 the widest possible interval is
0.024277... < theta < 0.031277....

Standard parameters.  Under the usual NFS smoothness heuristics the
first-side survivor density is far sparser than the window: optimised GNFS
has rational/algebraic penalties 1/4 and 3/4 (|W| = S^(7/4)), bounded-coefficient
SNFS has 1/2 and 1/2 (|W| = S^(3/2)); i.e. theta = 1/4 and 1/2, an order of
magnitude outside the window.  A fixed number of large primes moves these by
S^o(1) only.  And standard sparse linear algebra stays S^(2+o(1)) at the
optimised parameters even if the first side were free.

Why SSS does not repair this (derived, see README).  Forcing k top factor-base
primes by CRT across all S lines costs S^(2-o(1)) in transformed roots; triple
collisions return W = S^2/log^3 S = S^(2-o(1)) which is too dense; subsampling
S^(1-eps) primes gives W = S^(2-3eps) but captures only an S^(-3eps) fraction
of the relations, so the repetitions needed restore at least quadratic work.

This module evaluates these formulas (derived from the premise exponents; the
GNFS/SNFS penalties are heuristic inputs, labelled as such), writes the table
and draws figures/nfs_window.svg.
"""

from __future__ import annotations

import json
import os

from avw_model import MAX_D_EXP, PRE_EXP, QUERY_EXP

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results", "nfs_density_window.json")
FIG = os.path.join(HERE, "figures", "nfs_window.svg")

# heuristic first-side survivor penalties theta (|W| = S^(2 - theta))
COLLECTORS = {"GNFS (rational 1/4, algebraic 3/4)": 0.25, "SNFS (1/2, 1/2)": 0.5}


def exponents(theta: float, gamma: float) -> dict:
    avw_pre = 2.0 - PRE_EXP * gamma
    avw_query = 2.0 - theta + QUERY_EXP * gamma
    sparse_block = 2.0 - theta + gamma / 2.0
    scan = 2.0
    batch = 2.0 - theta  # exact batch smoothness test on the explicit survivors
    return {
        "theta": theta,
        "gamma": gamma,
        "T_AVW": max(avw_pre, avw_query),
        "avw_pre": avw_pre,
        "avw_query": avw_query,
        "T0_elementary": min(scan, sparse_block),
        "sparse_block_checks": sparse_block,
        "exact_batch_test": batch,
    }


def window(gamma: float) -> tuple[float, float]:
    return QUERY_EXP * gamma, (0.5 + PRE_EXP) * gamma


def avw_strictly_wins(theta: float, gamma: float) -> bool:
    e = exponents(theta, gamma)
    return e["T_AVW"] < e["T0_elementary"] - 1e-12


def brute_force_window(gamma: float, steps: int = 200_000) -> tuple[float, float]:
    """Numerically recover the window by scanning theta, as a check on the algebra."""
    lo = hi = None
    for i in range(steps + 1):
        th = 2.0 * i / steps
        if avw_strictly_wins(th, gamma):
            lo = th if lo is None else lo
            hi = th
    return lo, hi


def sss_nfs_tradeoff() -> list[dict]:
    rows = []
    for eps in (0.0, 0.05, 0.1, 0.2, 1.0 / 3.0):
        w_exp = 2.0 - 3.0 * eps
        captured_fraction_exp = -3.0 * eps
        repetitions_exp = 3.0 * eps
        transformed_root_cost_exp = 2.0 - eps  # S lines x S^(1-eps) sampled primes
        rows.append(
            {
                "eps": round(eps, 4),
                "W_exp": round(w_exp, 4),
                "captured_fraction_exp": round(captured_fraction_exp, 4),
                "repetitions_exp": round(repetitions_exp, 4),
                "per_pass_cost_exp": round(transformed_root_cost_exp, 4),
                "total_work_exp": round(transformed_root_cost_exp + repetitions_exp, 4),
            }
        )
    return rows


def draw(gamma: float) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    thetas = [i / 2000 for i in range(0, 1201)]
    e = [exponents(t, gamma) for t in thetas]
    fig, ax = plt.subplots(figsize=(7.2, 4.2), dpi=120)
    ax.plot(thetas, [x["T_AVW"] for x in e], label="AVW: max(S^{2-0.063γ}, S^{2-θ+0.437γ})", color="#c0392b", lw=2)
    ax.plot(thetas, [x["T0_elementary"] for x in e], label="elementary: min(scan S², sparse block S^{2-θ+γ/2})", color="#2a78d6", lw=2)
    ax.plot(thetas, [x["exact_batch_test"] for x in e], label="exact batch test S^{2-θ}", color="#27ae60", lw=1.6, ls="--")
    lo, hi = window(gamma)
    ax.axvspan(lo, hi, color="#f5b041", alpha=0.35, label=f"AVW window 0.437γ<θ<0.563γ = ({lo:.4f}, {hi:.4f})")
    for name, th in COLLECTORS.items():
        ax.axvline(th, color="#555", ls=":", lw=1)
        ax.text(th + 0.005, 1.62, name.split(" (")[0] + f" θ={th}", rotation=90, fontsize=7.5, va="bottom", color="#333")
    ax.set_xlabel("first-side survivor penalty θ   (|W| = S^{2-θ})")
    ax.set_ylabel("cost exponent in S  (sieve box S×S)")
    ax.set_title(f"NFS second-side block: AVW vs elementary comparators at γ = 1/18 (D = S^γ)")
    ax.set_ylim(1.45, 2.05)
    ax.set_xlim(0, 0.6)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7.5, loc="lower left")
    fig.tight_layout()
    fig.savefig(FIG)
    fig.savefig(FIG.replace(".svg", ".png"))


def main() -> None:
    gamma = MAX_D_EXP
    lo, hi = window(gamma)
    blo, bhi = brute_force_window(gamma)
    assert abs(blo - lo) < 2e-5 and abs(bhi - hi) < 2e-5, (blo, bhi, lo, hi)
    table = []
    for name, theta in COLLECTORS.items():
        e = exponents(theta, gamma)
        table.append(
            {
                "collector": name,
                "theta_heuristic_input": theta,
                "AVW_exp": round(e["T_AVW"], 5),
                "sparse_block_checks_exp": round(e["sparse_block_checks"], 5),
                "exact_batch_test_exp": round(e["exact_batch_test"], 5),
                "in_window": lo < theta < hi,
            }
        )
    res = {
        "premise": {"PRE_EXP": PRE_EXP, "QUERY_EXP": QUERY_EXP, "gamma_max": gamma},
        "window_formula": "QUERY_EXP*gamma < theta < (1/2+PRE_EXP)*gamma",
        "window_at_gamma_max": {"theta_low": lo, "theta_high": hi},
        "window_numerical_check": {"theta_low": blo, "theta_high": bhi, "status": "checked"},
        "standard_parameter_table_at_D=S^(1/18)": table,
        "linear_algebra_note": "sparse LA remains S^(2+o(1)) at optimised parameters even with a free first side",
        "sss_to_nfs_tradeoff_derived": sss_nfs_tradeoff(),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    os.makedirs(os.path.dirname(FIG), exist_ok=True)
    with open(OUT, "w") as fh:
        json.dump(res, fh, indent=1)
    draw(gamma)
    print(f"window at gamma=1/18: {lo:.6f} < theta < {hi:.6f}  (numerical scan: {blo:.6f}, {bhi:.6f})")
    for r in table:
        print(f"{r['collector']}: AVW S^{r['AVW_exp']}  sparse-block S^{r['sparse_block_checks_exp']}  batch S^{r['exact_batch_test_exp']}  in_window={r['in_window']}")
    for r in res["sss_to_nfs_tradeoff_derived"]:
        print(f"eps={r['eps']}: W=S^{r['W_exp']}, total work S^{r['total_work_exp']}")
    print(f"wrote {OUT} and {FIG}")


if __name__ == "__main__":
    main()
