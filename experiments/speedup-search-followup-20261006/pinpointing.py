"""Joux's advanced pinpointing: the closest established asymptotic
index-calculus speedup, and why AVW adds nothing to it.

Source: A. Joux, "Faster index calculus for the medium prime case.
Application to 1175-bit and 1425-bit finite fields", ePrint 2012/720 /
EUROCRYPT 2013, section 3.3 (Kummer extensions, advanced pinpointing) and
section 3.4 (complexity).

Construction (restated).  F_{q^n} = F_q[x]/(x^n - alpha) with n = d1 d2 - 1
dividing q - 1, y = x^{d2}, smoothness basis {x + a, y + a : a in F_q}.
Candidates XY + aY + bX + c read, on the two sides,

    x^{d2+1} + a x^{d2} + b x + c   and   (y^{d1+1} + b y^{d1})/alpha + a y + c.

With lambda = c/(ab), A = b a^{-d2}, B = a b^{-d1}, the X side splits iff
U^{d2+1} + U^{d2} + A(U + lambda) splits over F_q and the Y side iff
(V^{d1+1} + V^{d1})/alpha + B(V + lambda) splits.  So for fixed lambda one
builds L_A and L_B (cost O(q) each) and emits exactly the pairs

    W_lambda = {(A, B) : A B^{d2} is an n-th power in F_q},

each of which is already a relation whose (a, b, c) are recovered in O(1)
field operations: b^n = 1/(A B^{d2}), a = B b^{d1}, c = lambda a b.

Why AVW is irrelevant here.  Compatibility is an n-th-power-residue *label*;
a bucket join on that label costs O(|L_A| + |L_B| + |W_lambda|), which is
output-optimal.  Written as a selected product the compatibility test is
one-hot: inner dimension n, support one, separation rank 1, which fails the
theorem's s > n^0.437 requirement for every n > 1 (avw_model.py).

Complexity (Joux 3.4; heuristic list-size and splitting estimates as in the
source).  With q = L_Q(1/3, alpha):
    sieving  (Joux-Lercier 2006):      L(1/3, alpha + 2/(3 sqrt(alpha)))   for alpha >= 3^{-2/3}
    advanced pinpointing, relations:   L(1/3, max(alpha, 2/(3 sqrt(alpha))))
    linear algebra (basis 2q):         L(1/3, 2 alpha)
    full DLP, pinpointing:             L(1/3, 2 alpha)   for alpha >= 3^{-2/3}
which beats the sieving-dominated algorithm exactly for
3^{-2/3} <= alpha < (2/3)^{2/3}.  At alpha = 3^{-2/3} the constant falls from
3^{1/3} ~ 1.442 to 2 * 3^{-2/3} ~ 0.961.  (The source prints this value as
"(2/3)^{2/3} ~ 0.96"; (2/3)^{2/3} = 0.763, and 0.96 is 2 * 3^{-2/3} = 2 alpha
at that alpha, which is what the surrounding text computes.)

What this module does.
  * Builds a toy Kummer instance (q = 311, n = 5, d1 = 2, d2 = 3), runs
    advanced pinpointing for several lambda with the bucket join, recovers
    (a, b, c) for every emitted pair and checks in F_{q^n} that both sides
    split and are equal as field elements, i.e. that each emitted pair is a
    genuine multiplicative relation among the smoothness basis (exact).
  * Counts bucket-join work against the all-pairs scan (exact counts).
  * Evaluates the L(1/3, .) constants over alpha, writes the table and draws
    figures/pinpointing_constants.svg.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict

from avw_model import QUERY_EXP, rank_condition_holds

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results", "pinpointing.json")
FIG = os.path.join(HERE, "figures", "pinpointing_constants.svg")


# ----------------------------------------------------------------- F_q polys
def poly_eval(coeffs, u, q):
    r = 0
    for c in reversed(coeffs):  # coeffs[i] is the coefficient of U^i
        r = (r * u + c) % q
    return r


def poly_divmod_linear(coeffs, root, q):
    """Divide by (U - root); return quotient (assumes root is a root)."""
    n = len(coeffs) - 1
    out = [0] * n
    carry = 0
    for i in range(n, 0, -1):
        carry = (coeffs[i] + carry * root) % q if i == n else (coeffs[i] + carry * root) % q
        out[i - 1] = carry
    return out


def splits_completely(coeffs, q):
    """Roots with multiplicity if the polynomial splits over F_q, else None."""
    coeffs = [c % q for c in coeffs]
    while coeffs and coeffs[-1] == 0:
        coeffs.pop()
    roots = []
    while len(coeffs) > 1:
        r = next((u for u in range(q) if poly_eval(coeffs, u, q) == 0), None)
        if r is None:
            return None
        roots.append(r)
        coeffs = poly_divmod_linear(coeffs, r, q)
    return roots


# ----------------------------------------------------------- F_{q^n} elements
class Kummer:
    """F_q[x]/(x^n - alpha), elements as coefficient lists of length n."""

    def __init__(self, q, n, alpha):
        self.q, self.n, self.alpha = q, n, alpha

    def mul(self, a, b):
        q, n = self.q, self.n
        out = [0] * (2 * n - 1)
        for i, ai in enumerate(a):
            if ai:
                for j, bj in enumerate(b):
                    out[i + j] = (out[i + j] + ai * bj) % q
        for k in range(2 * n - 2, n - 1, -1):
            out[k - n] = (out[k - n] + out[k] * self.alpha) % q
        return out[:n]

    def const(self, c):
        return [c % self.q] + [0] * (self.n - 1)

    def x_plus(self, c):  # x + c
        v = self.const(c)
        v[1] = 1
        return v

    def pow(self, a, e):
        r = self.const(1)
        while e:
            if e & 1:
                r = self.mul(r, a)
            a = self.mul(a, a)
            e >>= 1
        return r

    def prod(self, items):
        r = self.const(1)
        for it in items:
            r = self.mul(r, it)
        return r


def nth_power_label(v, q, n, g):
    """Discrete log of v modulo n, via v^((q-1)/n) in the group of n-th roots of unity."""
    t = pow(v, (q - 1) // n, q)
    for k in range(n):
        if pow(g, k * (q - 1) // n, q) == t:
            return k
    raise ValueError


def primitive_root(q):
    from sympy import primitive_root as pr

    return int(pr(q))


def toy_instance(q=311, d1=2, d2=3) -> dict:
    n = d1 * d2 - 1
    assert (q - 1) % n == 0
    g = primitive_root(q)
    # alpha not an n-th power  =>  x^n - alpha irreducible (n prime, n | q-1)
    alpha = next(a for a in range(2, q) if nth_power_label(a, q, n, g) != 0)
    inv_alpha = pow(alpha, -1, q)
    F = Kummer(q, n, alpha)
    x = F.x_plus(0)
    y = F.pow(x, d2)
    labels = {v: nth_power_label(v, q, n, g) for v in range(1, q)}
    per_lambda = []
    total_checked = 0
    for lam in (1, 2, 3, 5, 7):
        # L_A: U^{d2+1} + U^{d2} + A(U + lam) splits ; coefficient list by degree
        LA, LB = {}, {}
        for A in range(1, q):
            cf = [0] * (d2 + 2)
            cf[d2 + 1] = 1
            cf[d2] = 1
            cf[1] = (cf[1] + A) % q
            cf[0] = (cf[0] + A * lam) % q
            r = splits_completely(cf, q)
            if r is not None:
                LA[A] = r
        for B in range(1, q):
            cf = [0] * (d1 + 2)
            cf[d1 + 1] = inv_alpha
            cf[d1] = inv_alpha
            cf[1] = (cf[1] + B) % q
            cf[0] = (cf[0] + B * lam) % q
            r = splits_completely(cf, q)
            if r is not None:
                LB[B] = r
        # bucket join on the n-th power residue label: need label(A) + d2*label(B) = 0 mod n
        buckets = defaultdict(list)
        for B in LB:
            buckets[(-d2 * labels[B]) % n].append(B)
        W = [(A, B) for A in LA for B in buckets[labels[A]]]
        join_work = len(LA) + len(LB) + len(W)
        # verify every emitted pair is a relation
        for A, B in W:
            v = pow(A * pow(B, d2, q) % q, -1, q)  # b^n = v
            b = next(bb for bb in range(1, q) if pow(bb, n, q) == v)
            a = B * pow(b, d1, q) % q
            c = lam * a * b % q
            # X side: x^{d2+1} + a x^{d2} + b x + c = a^{d2+1} P(x/a) = prod (x - a*u_i)
            lhs = F.const(0)
            for coeff, e in ((1, d2 + 1), (a, d2), (b, 1), (c, 0)):
                term = F.pow(x, e)
                term = [t * coeff % q for t in term]
                lhs = [(p + t) % q for p, t in zip(lhs, term)]
            roots_x = [(-a * u) % q for u in LA[A]]  # x = aU, U = u_i  => x - a u_i
            rhs = F.prod([F.x_plus(r) for r in roots_x])
            assert lhs == rhs, "X side does not factor as predicted"
            # Y side: (y^{d1+1} + b y^{d1})/alpha + a y + c = b^{d1+1} Q(y/b) = (1/alpha) prod (y - b v_j), and equals lhs
            ys = F.const(0)
            for coeff, e in ((inv_alpha, d1 + 1), (b * inv_alpha % q, d1), (a, 1), (c, 0)):
                term = F.pow(y, e)
                term = [t * coeff % q for t in term]
                ys = [(p + t) % q for p, t in zip(ys, term)]
            assert ys == lhs, "the two sides are not the same field element"
            yroots = [(-b * v) % q for v in LB[B]]
            yr = F.prod([[(yy + (r if i == 0 else 0)) % q for i, yy in enumerate(y)] for r in yroots])
            yr = [t * inv_alpha % q for t in yr]
            assert yr == ys, "Y side does not factor as predicted"
            total_checked += 1
        per_lambda.append(
            {
                "lambda": lam,
                "|L_A|": len(LA),
                "|L_B|": len(LB),
                "|W_lambda|": len(W),
                "bucket_join_work": join_work,
                "all_pairs_scan": len(LA) * len(LB),
                "expected_|W|_(|L_A||L_B|/n)": round(len(LA) * len(LB) / n, 1),
            }
        )
    return {
        "q": q,
        "n": n,
        "d1": d1,
        "d2": d2,
        "alpha": alpha,
        "per_lambda": per_lambda,
        "relations_verified_in_F_q^n": total_checked,
        "one_hot_selected_product": {
            "inner_dimension_n": n,
            "separation_rank": 1,
            "needs_rank_gt_n^0.437": round(n**QUERY_EXP, 3),
            "condition_holds": rank_condition_holds(1, n),
        },
        "status": "checked",
    }


# -------------------------------------------------------------- L(1/3) constants
def constants(alpha: float) -> dict:
    sieve_rel = alpha + 2.0 / (3.0 * alpha**0.5)
    pin_rel = max(alpha, 2.0 / (3.0 * alpha**0.5))
    la = 2.0 * alpha
    return {
        "alpha": alpha,
        "sieving_relations": sieve_rel,
        "pinpointing_relations": pin_rel,
        "linear_algebra": la,
        "classical_total": max(sieve_rel, la),
        "pinpointing_total": max(pin_rel, la),
    }


def constants_table() -> dict:
    lo = 3.0 ** (-2.0 / 3.0)
    hi = (2.0 / 3.0) ** (2.0 / 3.0)
    rows = [constants(a) for a in (lo, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, hi, 0.8, 0.9, 1.0)]
    return {
        "alpha_low_3^(-2/3)": lo,
        "alpha_high_(2/3)^(2/3)": hi,
        "at_alpha_low": {"classical": 3.0 ** (1.0 / 3.0), "pinpointing": 2.0 * lo, "source_misprint_(2/3)^(2/3)": hi},
        "improvement_range": "3^(-2/3) <= alpha < (2/3)^(2/3): pinpointing total 2*alpha < classical alpha + 2/(3 sqrt alpha)",
        "rows": rows,
        "note": "list-size and splitting estimates are heuristic, as in the source analysis",
    }


def draw(tbl: dict) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    alphas = [0.3 + i * 0.7 / 400 for i in range(401)]
    cs = [constants(a) for a in alphas]
    fig, ax = plt.subplots(figsize=(7.2, 4.2), dpi=120)
    ax.plot(alphas, [c["sieving_relations"] for c in cs], color="#c0392b", lw=2, label="sieving relations: α + 2/(3√α)")
    ax.plot(alphas, [c["pinpointing_relations"] for c in cs], color="#27ae60", lw=2, label="advanced pinpointing relations: max(α, 2/(3√α))")
    ax.plot(alphas, [c["linear_algebra"] for c in cs], color="#2a78d6", lw=2, ls="--", label="linear algebra: 2α")
    lo, hi = tbl["alpha_low_3^(-2/3)"], tbl["alpha_high_(2/3)^(2/3)"]
    ax.axvspan(lo, hi, color="#f5b041", alpha=0.35, label=f"full-DLP improvement range [{lo:.3f}, {hi:.3f})")
    ax.axhline(3 ** (1 / 3), color="#777", lw=1, ls=":")
    ax.text(0.31, 3 ** (1 / 3) + 0.01, "3^{1/3} ≈ 1.442 (classical at α = 3^{-2/3})", fontsize=7.5, color="#444")
    ax.scatter([lo], [2 * lo], color="k", zorder=5)
    ax.text(lo + 0.01, 2 * lo - 0.08, f"2·3^{{-2/3}} ≈ {2*lo:.3f}", fontsize=7.5)
    ax.set_xlabel("α   (q = L_Q(1/3, α))")
    ax.set_ylabel("constant c in L_Q(1/3, c)")
    ax.set_title("Medium-prime index calculus: relation collection and linear algebra constants (Joux 2012)")
    ax.set_ylim(0.5, 2.2)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7.5, loc="upper right")
    fig.tight_layout()
    fig.savefig(FIG)
    fig.savefig(FIG.replace(".svg", ".png"))


def main() -> None:
    toy = toy_instance()
    tbl = constants_table()
    res = {"toy_kummer_pinpointing": toy, "L13_constants": tbl}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    os.makedirs(os.path.dirname(FIG), exist_ok=True)
    with open(OUT, "w") as fh:
        json.dump(res, fh, indent=1)
    draw(tbl)
    for r in toy["per_lambda"]:
        print(f"lambda={r['lambda']}: |L_A|={r['|L_A|']} |L_B|={r['|L_B|']} |W|={r['|W_lambda|']} (expected ~{r['expected_|W|_(|L_A||L_B|/n)']}); join work {r['bucket_join_work']} vs all-pairs {r['all_pairs_scan']}")
    print(f"relations verified in F_q^n: {toy['relations_verified_in_F_q^n']}; one-hot rank condition holds: {toy['one_hot_selected_product']['condition_holds']}")
    print(f"improvement range alpha in [{tbl['alpha_low_3^(-2/3)']:.4f}, {tbl['alpha_high_(2/3)^(2/3)']:.4f}); at low end classical {tbl['at_alpha_low']['classical']:.4f} -> pinpointing {tbl['at_alpha_low']['pinpointing']:.4f}")
    print(f"wrote {OUT} and {FIG}")


if __name__ == "__main__":
    main()
