# Q1526 proof map

Q1526 evaluates the already recorded Q1462 pair-index cost law on four
Q1506 factor-base rows and 21 frozen table fractions. The new Lean module
checks the finite integer comparisons used to mark the abstract `2^61`
boundary. Since every recorded `B` is positive, the cross-multiplied
inequality `4*K*r > 2^61*B^2` corresponds to the full-table query-addition
floor `4*K*r/B^2 > 2^61` in the declared pair-add unit.

| Result | Lean declaration | Exact assumptions | Status |
| --- | --- | --- | --- |
| W5 full-table query-addition floor crosses `2^61` | `Q1526.w5_query_addition_floor` | fixed exact W5 `B=309633434`, `K=1181807`, recorded `r` | checked |
| W6 full-table query-addition floor crosses `2^61` | `Q1526.w6_query_addition_floor` | fixed exact W6 `B=6559634788`, `K=25036774`, recorded `r` | checked |
| W7 full-table query-addition floor crosses `2^61` | `Q1526.w7_query_addition_floor` | conditional sampled W7 `B=118153819312`, `K=450968776`, recorded `r` | checked |
| W8 full-table query-addition floor crosses `2^61` | `Q1526.w8_query_addition_floor` | conditional sampled W8 `B=1844590711506`, `K=7040422563`, recorded `r` | checked |
| W7 `4K²` matrix proxy below `2^61` | `Q1526.w7_matrix_proxy_below_budget` | conditional sampled W7 `K` | checked |
| W8 `4K²` matrix proxy above `2^61` | `Q1526.w8_matrix_proxy_above_budget` | conditional sampled W8 `K` | checked |

The checked declarations are in [PairBudget.lean](lean/PairBudget.lean).
The [proof receipt](lean/proof_receipt.json) pins Lean 4 `v4.35.0-rc4`,
the source and output hashes, and the exact build command. All six
`#print axioms` checks report no axioms. The module uses Lean core only and
contains no `sorry`, `admit`, `sorryAx`, custom axioms, or native evaluation.
`lean4checker` was unavailable.

The probability law behind `Q(f)=K*2*r/(B²*f)` and the condition that each
returned relation increases rank are model assumptions from Q1462. The
Lean declarations verify their numerical consequences for the frozen base
counts; they do not prove the model's probabilistic premises or an
elliptic-curve algorithm bound. W7/W8 point counts remain conditional
sampling projections rather than enumerated bases.
