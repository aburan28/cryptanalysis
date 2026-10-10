# Q1422: optimize explicit S3 indexing on the exact Q1413 N131 base

Use Q1413's exact N131 normal-basis weight-at-most-six projected base on
`EC1N131Ckb1h6816f880945e`. Bind its enumeration receipt, protocol,
independent Sage replay, Q1414 ordinary-query bound, and Q1416 pair-index
screen by SHA-256 before calculating. Retain its actual usable `B`, folded
column count `K`, and enumerated-set digest. Set `isogeny: "none"` (`ISO0`)
and keep `candidate_id` and `run_id` null.

For the exact prime subgroup order `r` and odd prime degree `n=131`, define
`U=(r-1)/(2n)` signed-Frobenius canonical nonidentity subgroup keys.
Consider an explicit table of `M` distinct S3 pair-output keys built
independently of an ordinary uniform nonzero target `Q`. Fix a list of
partner points independently of `Q`. Each `Q-b_i` is uniform over `r-1`
group points, and a canonical key has `2n` preimages. The hit probability
of one lookup is at most `M/U`; linearity gives expected hits at most
`LM/U` for `L` lookups even when they are dependent. Assuming every hit
adds one novel factor-base log row, Markov's inequality makes
`L >= ceil(KU/(2M))` necessary for a half chance of `K` rows.

With `K` signed-Frobenius base columns there are `nK` distinct x values.
Unordered x pairs have full Frobenius orbit length `n`; each pair has at
most two S3 roots. Hence `M <= min(U,K(nK+1))`, even before collisions.
At least `M` distinct key insertions are required to build such an
explicit index. Minimize the necessary logical-action count
`T(K,M)=M+ceil(KU/(2M))` first for Q1413's **exact K**, then globally
over every integer `1 <= K <= U` and permitted `M`. The global relaxation
allows bases that may not exist; it measures the best possible fixed-index
parameter tuning under this work law.

For the integer optimization, locate the first `K` where
`2K(nK+1)^2 >= U`. Below it the best `M` is the pair-output cap, giving
`T=K(nK+1)+ceil(U/[2(nK+1)])`. The real expression inside that ceiling
is strictly convex; find its derivative sign change and compare the two
adjacent integers. At and above the boundary the unconstrained minimum
is feasible and nondecreasing in `K`. Independently verify these integer
claims and exhaustively check small `(n,U,K,M)` domains.

Report exact action counts, logarithms, and gaps above `2^61` in the
named **logical index action** unit. Q1416's conditional uniform-key
pair-probe model and Q1414's ordinary-query supply bound are separate
comparators, not substitutions for this lower bound. Keep complete cold
and one-target-online field-call, matrix, descent, replay, and wall-time
work exponents null until measured. Target-dependent partner schedules
and implicit solvers are outside this fixed-index theorem.

Freeze protocol, both source files, and all input receipts before creating
the numeric result. Stop if any source digest, curve ID, subgroup order,
base count, or prior verification changes.
