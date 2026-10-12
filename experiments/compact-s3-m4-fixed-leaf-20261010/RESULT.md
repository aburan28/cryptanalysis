# Q1423: fixed-leaf S3 search on N53 and N83

Fixing one exact factor-base subgroup point outside SAT removes one leaf and
one S3 link from the four-summand formula. On the same bases, the N53 formula
falls from 23,055 to 13,684 variables and the N83 raw-preimage formula from
65,221 to 43,646 variables. Both locked known-solution controls pass native
model checks and independent exact Sage point-sum replay. Free searches on
the same public targets remain bounded under the frozen caps.

## Method and identifiers

Q1423 is a point-decomposition proposal, with `candidate_id: null` and
`isogeny: none`. The N53 ordinary workload `74f2979b3e68` uses
`EC1N53Ckb1hf77aab617904`, the exact W≤3 subgroup orbit base with
`B=24,062` before folding and `K=227` signed-Frobenius columns. The N83
ordinary workload `bab50a1e5f66` uses `EC1N83Ckb1h876c2921cb64`, the
exact cofactor-projected W≤5 base with `B=30,977,592` and `K=186,612`.
The complete base digests, public points, source hashes, solver binary, and
limits are in [freeze.json](freeze.json).

For each public `Q`, choose `P3` from that exact base, compute `T=Q-P3`, and
solve `P0+P1+P2=T`. N53 selects three exact subgroup x orbits. N83 selects
three raw W≤5 x coordinates and one of the four cofactor preimages of `T`.
`pool1` chooses the first deterministic SHA-256-derived base point;
`pool64` scores 64 points by Hamming weight of `x(Q-P3)` and charges all
64 group subtractions. The selected remainder weights were 24→20 on N53
and 44→28 on N83. The final remainder recomputation makes the charged
subtraction counts two and 65 respectively.

## Measured stage results

CryptoMiniSat used one thread, deterministic random seed zero, a
1,000,000-conflict cap, and a 1,536 MiB sampled RSS cap. Locked controls had
a 30-second solver allowance; other searches had 120 seconds and a
135-second external cap. Times are exploratory on a host without a CPU
isolation receipt. `BOUNDED_UNKNOWN` denotes a censored SAT search.

| n | Case | Variables | AND gates | Solver status | Conflicts reported | Solver wall s | Verified four-point relation |
| ---: | --- | ---: | ---: | --- | ---: | ---: | --- |
| 53 | locked known solution | 13,684 | 11,342 | SAT | 0 | 0.214 | yes |
| 53 | unpinned known solution | 13,684 | 11,342 | BOUNDED_UNKNOWN | 1,000,003 | 29.529 | — |
| 53 | ordinary `pool1` | 13,684 | 11,342 | BOUNDED_UNKNOWN | 1,000,001 | 24.972 | — |
| 53 | ordinary `pool64` | 13,684 | 11,342 | BOUNDED_UNKNOWN | 1,000,002 | 34.137 | — |
| 83 | locked known solution | 43,646 | 41,334 | SAT | 0 | 0.217 | yes |
| 83 | unpinned known solution | 43,646 | 41,334 | BOUNDED_UNKNOWN | external 135 s cap | 135.221 | — |
| 83 | ordinary `pool1` | 43,646 | 41,334 | BOUNDED_UNKNOWN | external 135 s cap | 135.016 | — |
| 83 | ordinary `pool64` | 43,646 | 41,334 | BOUNDED_UNKNOWN | 1,000,002 | 111.682 | — |

All eight solver logs show search began. For the two external-timeout rows,
CryptoMiniSat did not print final conflict counts before termination. The
locked relations pass an independent Sage field conversion, subgroup check,
and point-sum replay. The verifier checks each XCNF header and SHA-256,
compressed stdout/stderr, frozen inputs, and status. See
[verification.json](verification.json) and
[verification_sage.json](verification_sage.json). The exact phase costs and
selection receipts are in the eight `n*.json` records.

The formula reduction is 40.65% of variables and 42.78% of AND gates on N53,
and 33.08% of variables and 33.33% of AND gates on N83, relative to the
same-base four-leaf receipts. The caps do not identify the natural relation
yield or solver work to a relation.

## N131 fixed-point rank-supply reference

The exact Q1413 N131 W≤6 base belongs to a separate curve,
`EC1N131Ckb1h6816f880945e`, with `B=6,559,634,788`,
`K=25,036,774`, and subgroup order
`r=680564733841876926932320129493409985129`. For a point `P3` selected
independently of a uniform nonidentity subgroup query `Q`, each unordered
three-point multiset maps to at most one `Q-P3`. Thus the mean number of
distinct three-point representations is at most

`C(B+2,3)/(r-1) = 6.9122317481e-11 = 2^-33.7521`.

If every representation supplies an independent matrix row, Markov's
inequality still requires at least `181,104,850,882,659,135 = 2^57.3296`
independent fixed-point attempts for a 50% chance of `K` rows. This is
**30.6110 more attempt bits** than the Q1414 uniform four-summand reference.
With all other costs set to zero, a `2^61` total permits only
`12.7321 = 2^3.6704` abstract work units per such attempt. This is a
necessary affordability ceiling for the stated independent-point input law,
not a measured N131 solver cost.

Q1423's `pool1` hash includes `Q`, and `pool64` additionally scores
`x(Q-P3)`. These target-dependent policies are outside that proof scope.
The four ordinary probes provide no estimated natural yield for them.
The [analysis record](analysis.json) preserves the exact counting inputs,
source receipts, formula comparisons, and null complete-solve exponents.

## Next experiment

The full four-leaf search retains the much larger relation supply, so the
next solver change should preserve all four variable leaves while eliminating
an S3 intermediate or strengthening propagation. Compare the same N53 and
N83 ordinary points and known-solution controls under frozen caps. Promote a
candidate only after a natural relation and rank novelty are verified, then
measure relation collection, final matrix solving, and target descent before
reporting a complete `2^x` solve cost.
