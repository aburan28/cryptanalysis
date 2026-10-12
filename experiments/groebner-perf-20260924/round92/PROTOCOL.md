# Ring-only Macaulay layouts with fresh pivots

The reusable object depends only on `(n, equation_count, d, r)`, where every input
polynomial has degree at most `d` and `r` is a squarefree multiplier bound. Let
`S_k` denote all squarefree monomials of degree at most `min(k,n)`. The input
support is `S_d`, columns are `S_(d+r)` in descending grevlex, and each row recipe
is `(input equation, multiplier in S_r)`. The immutable scatter map sends
`(multiplier, input monomial)` to the column for their bitwise union.

This is a bounded Boolean Macaulay construction, not a new F4/F5 or F6 algorithm.
Boolean Macaulay matrices and their role in polynomial solving are established;
see [Bardet, Faugère, Salvy and Spaenlehauer](https://members.loria.fr/PJSpaenlehauer/data/papers/BarFauSalSpa11.pdf).
The declared multiplier bound here is explicit; it must not be mistaken for a
proved solving degree. F4 symbolic/matrix methods and learned traces are also
established; see the [msolve paper](https://perso.lip6.fr/Mohab.Safey/Articles/msolve-issac21.pdf).

Each call independently validates the complete support order and coefficient
padding, decodes fresh coefficients, forms every recipe, and chooses fresh
forward pivots and backward eliminations. Every multiplication and row XOR
produces an original-equation derivation node. Unused nodes are removed without
changing the surviving derivations. No coefficient, rank, pivot, proof or answer
is retained in the layout. All numeric storage belongs to the call.

The proposal consists of the fully row-reduced rows whose leading monomials are
minimal under divisibility. This alone is not an acceptance condition. The
separate unchanged round11 checker proves output membership, reverse input
inclusion, reducedness, and ordinary and Boolean-field critical-pair completion.
Incomplete row spans, nonstandard tails and inadequate multiplier bounds must
remain rejected/inconclusive proposals. With fallback enabled, the unchanged
round62 F4 engine starts afresh on the original packed input and its result is
independently checked. The wrapper shares its declared work/checker allowances
across both attempts and never returns a partial basis as verified.

For `r=n`, the rows span the entire Boolean ideal as a vector space because all
squarefree multiples of all generators occur. Row reduction plus the minimal
leading rows then gives the reduced Boolean basis. This is a useful small-ring
correctness control, not a complexity improvement: it has exponential size.
For `r<n`, completion is explicitly unproved until independent checking passes.

Monomial layouts are bounded to 262144 terms; retained support, column,
multiplier and scatter payload is capped at 64 MiB. The count preflight stops
before overflowing or enumerating large binomial sums. That payload excludes
container metadata and temporary construction maps. Numeric pivot payload is
separately capped at 64 MiB, with declared row and proof-node limits. Reported
source visits/word XORs are logical counters, not physical operation estimates
or interchangeable calibrated work units across F4 and Macaulay algorithms.

The frozen panel preserves round91's 14 families and 28 subsequent systems.
The prior training inputs establish the family law/degree bound only; there is
no numerical training. Linear families use `r=0`. Nonlinear arms use `r=1` or
`r=2`. Fresh-layout and reused-layout r1 arms must have identical coefficients,
pivot/proof traces and logical counters. Their algebra query interval differs
only by whether ring-only layout construction/destruction is charged or retained
as separate preparation. All arms start from the same immutable, full-support
packed ANF. Fixture generation and packing are outside this algebra boundary.
This is not a complete point-decomposition/curve query or IC measurement.

The six arms are fresh F4, fresh-layout r1, reused r1, reused r2, interpreted
Boolean F5B and native evaluation/interpolation. The signature comparator now
attempts systems through 12 variables; evaluation attempts systems through its
20-variable native bound and uses the independent uncached certificate above
12. Both retain timeouts and unsupported cases. Two warmup orders precede six
balanced observation orders. No observation is replaced, and all local timing
claims remain exploratory without an isolation receipt.

Portable correctness covers full-multiplier ideals against independent truth
tables, incomplete-degree counterexamples, changed nonlinear coefficients,
limb/bit-63 boundaries, work/proof/row/layout limits, failure recovery, malformed
ABI inputs, result lifetime and concurrency. CI rebuilds native libraries on
each claimed platform. No GPU execution, automatic dispatch, asymptotic F6
result or one-target IC/rho speedup is established by this experiment.
