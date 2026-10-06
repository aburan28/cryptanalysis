"""Shared cost-model constants for the speedup-search follow-up.

Every exponent here is a *premise*, not a measurement.  They restate the
selected thin-product theorem of Alman and Vassilevska Williams
(arXiv:2610.06783) in the form the follow-up report uses:

    Given X in F^{N x D}, Y in F^{D x N} with D <= N^(1/18) and a selected set
    W of entries of XY, the selected entries can be computed in
        PRE(N, D)   = N^2 / D^PRE_EXP          preprocessing, plus
        QUERY(D)    = D^QUERY_EXP              per selected entry,
    for a separation rank s = D^(1/2+o(1)).

PRE_EXP = 0.063 and QUERY_EXP = 0.437 are the values the report assumes, and
MAX_D_EXP = 1/18 is the inner-dimension ceiling under which the theorem is
stated.  All screens below are parametrised on these three numbers so a
different reading of the theorem is a one-line change, and so that the
scoped dominance results are explicitly conditional on them.

Nothing in this file is evidence; the modules that import it either prove a
statement symbolically, check it exhaustively on small instances, or measure
it, and say which.
"""

from __future__ import annotations

from dataclasses import dataclass

PRE_EXP = 0.063
QUERY_EXP = 0.437
MAX_D_EXP = 1.0 / 18.0

# The report's "necessary condition" for a selected-product representation
# to be in the theorem's regime: separation rank s must exceed n^QUERY_EXP
# where n is the inner dimension.  A one-hot (support-one) selected product
# has s = 1 and fails this for every n > 1.
def rank_condition_holds(separation_rank: float, inner_dimension: float) -> bool:
    return separation_rank > inner_dimension**QUERY_EXP


@dataclass(frozen=True)
class AvwCost:
    """Log-scale (base: the ambient size N) cost of the AVW route."""

    preprocessing_exp: float
    query_exp: float

    @property
    def total_exp(self) -> float:
        return max(self.preprocessing_exp, self.query_exp)


def avw_cost_exponents(n_exp: float, d_exp: float, w_exp: float) -> AvwCost:
    """Exponents of the two AVW terms when N = S^n_exp, D = S^d_exp, |W| = S^w_exp.

    Everything is expressed as an exponent of a common base S so that the
    NFS-window and batch-screen modules can compare against elementary
    comparators in the same unit.
    """
    pre = 2.0 * n_exp - PRE_EXP * d_exp
    query = w_exp + QUERY_EXP * d_exp
    return AvwCost(pre, query)
