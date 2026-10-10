# Q1420 source/degree-263 solver-stage scoreboard

This index pairs the equal-useful-size W24 source and oriented degree-263
descendant experiments on the exact first public query of workload
`eee7f6ee5f6b`. Both bases have `B=16,772,828` subgroup-usable points before
sign folding; the source curve is `EC1N131Ckb1h136f03e58c98`, and the
descendant is `EC1N131Cbinh833014327b07` on route
`IW1E263d1hadee4e69fa3d`. Q1420 is a proposal (`candidate_id: null`).

| Gate | Source | Descendant | Evidence and next implication |
| --- | --- | --- | --- |
| Exact W24 base | 16,772,828 usable points | 16,772,828 usable points | [Equal-base input gate](../ecc2k130-263-equal-w24-workload-20261005/RESULT.md) fixes the same public workload and usable size. |
| Projective-S3 ordinary Q0 | `BOUNDED_UNKNOWN` | `BOUNDED_UNKNOWN` | [Original circuit](../ecc2k130-263-projective-s3-20261010/RESULT.md) enters search under the archived cap. |
| Bilinear-leaf ordinary Q0, default Gauss | `BOUNDED_UNKNOWN`; largest 17,665-row XOR component rejected | `BOUNDED_UNKNOWN`; largest 17,754-row XOR component rejected | [Bilinear ordinary gate](../ecc2k130-263-bilinear-ordinary-q0-20261010/RESULT.md) gives zero verified Q0 relations under 120/150-second guards. |
| Bilinear-leaf fixed x release, default Gauss | x0/x5 `BOUNDED_UNKNOWN` at 20,000 conflicts | x0/x5 `BOUNDED_UNKNOWN` at 20,000 conflicts | [Full x-release ladder](../ecc2k130-263-x-freedom-ladder-20261010/RESULT.md) places the fixed-witness search-budget frontier between 16 and 32 released bits. |
| Bilinear-leaf fixed x release, wide Gauss | x0/x5 admitted 5,809-/5,770-row matrices; both wall-capped | x0/x5 admitted 5,656-/5,922-row matrices; both wall-capped | [Wide-Gauss audit](../ecc2k130-263-wide-gauss-20261010/RESULT.md) confirms active search and no model within the frozen 40-second guards. |
| Bilinear-leaf ordinary Q0, wide Gauss | 17,665 × 27,342 matrix admitted; `BOUNDED_UNKNOWN` | 17,754 × 27,561 matrix admitted; `BOUNDED_UNKNOWN` | Both entered search and hit the 150-second external guard; relation yield for this one attempted query was zero verified rows, with novel rank unavailable. |
| Free-selector leaf-0 identity, paired ordinary Q0 | Base and strengthened both `BOUNDED_UNKNOWN` at 2,001 conflicts; 0 verified rows | Base and strengthened both `BOUNDED_UNKNOWN` at 2,002/2,001 conflicts; 0 verified rows | [Exact free-identity gate](../ecc2k130-263-free-identity-20261010/RESULT.md) verifies both positive controls and all added AND/XOR records. Dense descendant `alpha` admits field-linear factoring with 19.887-fold fewer product-plus-map XOR-literal occurrences, an analytical next encoding rather than a solver result. |

The wide-Gauss intervention changes matrix admission, not the mathematical
instance or factor base. The free-selector identity is mathematically valid
and preserves positive controls, but neither ordinary Q0 cell resolved
within its conflict cap. Solver timings here are exploratory because
host-wide CPU isolation was not established. A complete candidate still
needs verified factor-base logs, target descent, scalar replay, and a
matched single-target online IC/rho measurement.

The free-selector identity row retains all four conflict-capped ordinary
outcomes and 82.71 seconds of paired source/descendant Q0 construction plus
solver wall time on an unisolated host. Its group-verified controls establish
correctness of the redundant constraint. The next gate is to implement the
field-linear factored form on the descendant and test held-out ordinary
queries before comparing relation yield and rank.
