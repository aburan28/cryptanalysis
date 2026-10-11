# Q1422: exact N131 base needs at least 2^88.355609 fixed-index actions

The exact Q1413 weight-at-most-six factor base requires at least
**395,993,893,517,632,118,233,168,669 logical index actions**
(`2^88.355608650`) to build an explicit S3 pair-output key table and
obtain `K` rank rows with probability one half under a fixed,
target-independent partner schedule. This is **27.355609 bits above
`2^61` in the stated action unit**. The calculation gives the table every
possible distinct pair-output key and lets every hit contribute a novel row.

The exact curve is `EC1N131Ckb1h6816f880945e`, with prime subgroup
order `680564733841876926932320129493409985129`, degree `n=131`, and
`isogeny: "none"` (`ISO0`). [Q1413's enumerated base](../compact-s3-m4-20261003/runs/n131_q1413_projected_x_w6.json)
has **B=6,559,634,788 distinct usable points before folding** and
**K=25,036,774 signed-Frobenius columns**. Its enumerated-set SHA-256 is
`e5f66c3944069924b9af7b8c22887e216702c8ac11a3a2ad072437e7d81ecb3b`.
Q1422 is an analytic proposal with null `candidate_id` and `run_id`.

| Domain | K columns | Indexed keys M | Necessary lookups L | Insertions + lookups | Gap over `2^61` |
| --- | ---: | ---: | ---: | ---: | ---: |
| Exact Q1413 base; all distinct S3 pair outputs granted | 25,036,774 | 82,116,046,879,883,730 (`2^56.189`) | `2^88.355609` | **`2^88.355609` actions** | **27.355609 bits** |
| Unrestricted integer K and permitted M | 33,572,874,131 | `2^76.966577` | `2^77.966577` | **`2^78.551539` actions** | **17.551539 bits** |

The second row minimizes the same action law over every integer
`1 <= K <= U`, including column counts for which no base has been
constructed. It lowers the optimistic action floor by 9.804069 bits
relative to the exact Q1413 base. Its `K=33,572,874,131` would itself
correspond to `2nK=8,796,093,022,322` usable points before folding, so it
is a parameter bound rather than a measured faster configuration.

## Work law and exact minimization

There are `U=(r-1)/(2n)=2,597,575,320,007,163,843,253,130,265,242,022,844`
nonzero signed-Frobenius canonical subgroup keys. For a fixed list of
partner points independent of an ordinary uniform nonzero target, any one
lookup hits an index of `M` keys with probability at most `M/U`.
Linearity and Markov's inequality give
`L >= ceil(KU/(2M))` necessary lookups for a half chance of `K` hits,
without an independence assumption among lookups. An index on `K`
columns has `M <= min(U,K(nK+1))` distinct S3 pair-output
keys; pair collisions reduce this count. Building `M` distinct stored
keys costs at least `M` insertions. Thus
`T(K,M)=M+ceil(KU/(2M))` is a necessary logical-action count under this
fixed explicit-index setup.

For the exact Q1413 `K`, the best permitted `M` equals its full
pair-output ceiling, 82,116,046,879,883,730 keys. The resulting
necessary lookups are 395,993,893,435,516,071,353,284,939.
For the unrestricted sweep, the pair-output cap first reaches the
unconstrained index optimum at `K=42,299,170,823`. Below that boundary,
the real capped expression
`K(nK+1)+U/[2(nK+1)]` has second derivative
`2n+Un²/(nK+1)³>0`; its derivative changes sign at
`K=33,572,874,131`. Checking that integer and its predecessor, then the
uncapped boundary, certifies the global minimum. The
[independent verifier](verification.json) recomputes exact counts and
checks the optimizer against exhaustive enumeration on 8,316 small
domains. The [pre-result freeze](freeze.json) binds the
[protocol](PROTOCOL.md), both source files, Q1413's base and independent
Sage replay, and the Q1414/Q1416 comparator receipts. Full integers and
null completion fields are in the [result](result.json).

Q1416's `2^89.355609` conditional K-row **pair-probe model** and
Q1414's minimum 110,435,936 **uniform relation queries** answer
different questions; neither is substituted for the exact-base
fixed-index action floor. The action count is not converted to N131
field calls or wall time, and complete cold and one-target-online solve
exponents remain null. Base construction, observed ordinary relation
yield, rank novelty, final matrix solving, target descent, and scalar
replay still require their own charges. A target-dependent partner rule
or implicit point-decomposition solver lies outside this theorem and is
the next solver direction to measure on exact N53 and N83 workloads.
