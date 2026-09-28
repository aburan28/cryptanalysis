# Ordinary relation collection: frozen stage diagnostic

## Question and acceptance condition

Does a solver challenger reduce fully charged wall time per new independently
verified row by at least two relative to the fastest available same-base control?
This implements steps 1–4 of the requested evaluation. It is not an end-to-end
DLP result. `candidate_id` and `full_dlp_speedup` remain null. The primary
single-unseen-target DLP comparison remains a separate, unperformed experiment.

Controls: exact point-pair lookup and CryptoMiniSat 5.16.0 with native XOR.
Challengers: three-bit assumption branching with CryptoMiniSat, the repository
Boolean F5B prototype, and its block F4 prototype. GB outputs use charged SAT
root extraction. No complete-basis claim is made by this protocol. These are
not measurements of Magma F4, msolve, M5GB, PolyBoRi, or Groebner.jl learn/apply.
No automatic algorithm search or additional cloud workers are launched.

## Frozen samples and limits

* Correctness: n=7, l=4; exhaustive three-point decomposability over the complete
  small subgroup and algebraic checks for selected subgroup targets.
* Ordinary small-curve trial: n=13, l=5, three summands, seeds
  20260928–20261002, 12 uniform nonidentity subgroup queries per seed.
  One second per polynomial encoding + solve + witness extraction, 25 seconds
  per backend/seed cell, one thread, 2 GiB address-space limit.
* Fidelity probe: n=83, l=6, three summands, seeds 20260928 and 20260929,
  four ordinary queries per seed, three seconds per polynomial attempt,
  60 seconds per backend/seed cell, one thread, 2 GiB address-space limit.

The manifest is frozen and committed with source hashes before execution.
The cell watchdog includes direct index construction and every attempt. The
per-attempt watchdog applies to the polynomial subprocess; direct lookup is
bounded by the enumerated base and the same cell watchdog. Direct control is
Python, not an optimized compiled collector: a gain against it alone would not
establish superiority to best known code. Backends run serially and their order
reverses on alternate seeds. A launch takes an output directory that must not
already exist. Raw requests, equations, stdout/stderr, journals, and hashes are
retained. An absent complete event remains an incomplete cell.

## Mathematics and useful rows

The curve is `y²+xy=x³+1` in an explicitly archived irreducible polynomial basis.
Its order is computed from trace recurrence `t0=2, t1=-1, tn=-t(n-1)-2t(n-2)`.
The largest prime subgroup order has a recursively checked, full-factorization
Lucas certificate. Every point with x in `span(1,z,...,z^(l-1))` is enumerated.
Projection by the cofactor defines the usable subgroup base; zero images are
omitted and all nonzero images pass subgroup checks. The original point set,
projected set, actual B, sign representatives and column count are archived.
No Frobenius orbit identification is applied without phase coefficients.

The sampler draws k uniformly from 1..r-1 and forms R=[k]G; no decomposition is
planted. Solvers receive R and the base, never k. On a valid signed decomposition
sum(Pi)=R, the row consists of the signed coefficients of [h]Pi and RHS h*k mod r.
The driver verifies the point sum before incremental rank over F_r. Scalar
multiples of previous rows are duplicates. A separate post-run replay reconstructs
each row, verifies its RHS by group arithmetic, and checks rank using SymPy's
finite-field DomainMatrix elimination. The rank is of coefficient columns, not
the augmented RHS or a solver's Macaulay matrix. Each query retains its first
valid decomposition; no solver gets free searches for more independent rows.

## Charging and inference

Each cell is charged its fresh-process wall time plus the recorded cost of
constructing the frozen base and that seed's ordinary query stream. This charges
shared construction once to every arm, rather than charging it only to the
first arm. Equation construction, index construction, imports, solving,
invalid roots, misses, timeouts, verification, rank updates, and journal output
are inside the worker interval. Installation, freezing-file serialization,
post-run independent audit and final summaries are outside it and named.
No learn/apply reuse is exercised. Process RSS maxima are not simultaneous
process-tree memory. The fixed address-space limit is also retained.

Cost per new row is null when rank is zero. Timed-out/failed cells retain all
costs and completed verified rows. SAT exhaustion is `no_witness_uncertified`,
never a certified UNSAT result. Timeout is unknown. Direct lookup exhaustion
is exact for the explicitly enumerated original base.

The predeclared 2× stage gate requires at least five paired independent seeds,
at least eight independent rows per complete/replayed cell, candidate cost at
most half the fastest named baseline on **every** seed, and an upper 95% paired
seed-bootstrap ratio at most 0.5. Five seeds are only an initial screening gate;
a positive result needs fresh holdouts and compiled controls before publication.
The two-seed n=83 probe cannot pass that gate by construction. It tests natural
yield and technical feasibility, not the full n=83 campaign.

The archived upper bound `(B+epsilon)^3/(r-1)`, epsilon=1 when zero is a projected
base image, bounds uniform nonidentity query coverage by counting ordered
projected tuples. It is a bound, not measured yield. If ordinary n=83 yield is
zero and this bound is tiny, stop this bounded trial and identify a larger,
manageable base/encoding as the next experiment. Do not replenish with planted
queries, call solver time an independent-row speedup, or extrapolate to n=131.

## Commands

```sh
python -m pip install sympy==1.14.0 pycryptosat==5.16.0
python -m unittest groebner_compare.test_relation_metrics -v
python -m unittest discover -s experiments/pdp-scaling -p test_ordinary_campaign.py -v
python experiments/pdp-scaling/ordinary_campaign.py freeze MANIFEST.json --n 83 --l 6 --attempts 4
python experiments/pdp-scaling/ordinary_campaign.py run MANIFEST.json NEW_OUTPUT_DIRECTORY
```

The older `collect.py` remains an m=3 WDSat diagnostic. Its corrected total
includes collector construction and failed searches; it still reports
`independent_rank: null`. Use this campaign for signed-row/rank accounting.
