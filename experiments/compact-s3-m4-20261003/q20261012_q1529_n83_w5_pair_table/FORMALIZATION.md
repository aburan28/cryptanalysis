# Q1529 proof map

The contribution is a measured query implementation and a conditional
operation-count conversion. Q1462/Q1526's uniform successful-query law,
sampled N131 W≤7 base size, and one-novel-row-per-useful-match assumption
are **inputs** to the conversion. The native algorithm batches one base-pair
sum across 166 signed/Frobenius complements at N83; the conditional N131
analogue batches across 262. The quotient reuse calculation does not assert
the law or the N131 implementation has been validated.

| Result | Lean declaration | Exact scope | Status |
| --- | --- | --- | --- |
| N83 cross-orbit descriptor count | `Q1529.n83_domain` | exact W≤5 K=186,612, n=83 | checked |
| N83 conditional representative mean lies between 2^48 and 2^49 | `Q1529.n83_representatives_between` | exact B, K, r, T=2^18; Q1462 query law assumed | checked arithmetic |
| Measured 2^20 prefix is below the conditional mean | `Q1529.n83_prefix_below_expectation` | same exact inputs and conditional law | checked arithmetic |
| Reuse lowers pair additions | `Q1529.quotient_reuse_saves_pair_additions` | Q1526 sampled W7 B/K/r; 262 lifts per representative | checked arithmetic |
| New N131 charge lies between 2^85 and 2^86 | `Q1529.quotient_reuse_between_exponents` | same conditional inputs | checked arithmetic |
| New N131 charge remains above 2^61 | `Q1529.quotient_reuse_above_challenge_pair_add_budget` | same conditional inputs, pair-add units | checked arithmetic |

The readable calculation is `Q_lifted = K·2r/B²/f` for K expected useful
matches and table fraction `f`. Native batching changes query additions from
`2Q_lifted` to `Q_lifted + Q_lifted/(2n)`; one representative evaluates
`2n` lifts. For N131 W≤7 full table this gives
`T+(263/262)Q_lifted`. For one N83 relation, the exact table fraction is
`2^18/(83·K·(K−1))`, and the conditional representative mean is
`[2r/(B²f)]/166`. All fractions are checked by cross-multiplied integer
inequalities in [QueryUnits.lean](lean/QueryUnits.lean).

The [proof receipt](lean/proof_receipt.json) pins Lean 4.35.0-rc4, Lean core,
the exact build command, source/output hashes, and `#print axioms` checks.
All declarations build with no axioms. `lean4checker --fresh` was unavailable.
The finite checks do not prove the stochastic query law, N131 base count,
rank novelty, or an end-to-end attack bound.
