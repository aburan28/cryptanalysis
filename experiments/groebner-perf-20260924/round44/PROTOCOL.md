# Partial-affine complete-query experiment

This is an implementation experiment based on merged round42 and round43.
Correctness passes the frozen corpus and independent complete-query audit;
see README.md for exact counts and evidence. Performance is pending. The
accepted solver dispatch and prior frozen timing sources remain unchanged.

The initial scope is the existing rank-deficient projection fallback only.
When the producer has already derived r affine consequences with 0<r<y,
it may exhaust their 2^(y-r) assignments and retain original-equation
witnesses. Rank zero uses the old fallback. Both previous contradiction
formats, independent original-equation checks, global root completeness,
basis vanishing, staircase cardinality and reducedness remain required.

## Tagged record format

The complete proof retains the existing constant-prefix and fixed-size tail.
Each tail record still contains 1+(y+1)*ceil(equations/64) words. The branch
word's high bit marks a partial-affine record; every other high bit remains
out of range. A marked record carries y+1 original-equation witness rows,
with zero padding allowed. It carries no trusted rank, pivots or roots.
The explicit format name is `constant-prefix+tagged-affine-records-v2`.

The checker validates branch bounds after decoding the tag, strict branch
ordering, exact word counts, high equation bits, and no overlap with constant
prefix witnesses. It reconstructs every marked consequence and rejects any
nonlinear coefficient. It independently recomputes rank and exhausts the
entire affine solution space, evaluating original residual equations.
Missing records require the unchanged complete fallback; no branch can be
omitted from coverage. Untagged records retain their previous meaning. An
old checker must reject a tagged record rather than reinterpret it.

Fresh exact symmetry checks remain mandatory. Expanded records preserve the
tag and every witness; the checker validates them at each original branch.
Copy-budget failure leaves no record and therefore invokes complete checking.

## Budgets and result atomicity

All failed partial attempts remain charged. Producer assignment limits cover
lifted enumeration, old fallback enumeration and partial-affine enumeration
together. Projection work covers the new attempt as well as prior reduction
work. A partial attempt collects roots locally and commits them only after
complete enumeration and proof/capacity checks. Work exhaustion can return to
the old bounded path; global assignment/root exhaustion is inconclusive.
No incomplete root prefix may escape as a complete basis.

The checker keeps its complete-query assignment, root and basis limits and
adds a bounded partial-witness/reduction work counter. Timings of nested
producer stages are diagnostics and must not be summed as exclusive phases.
All table and proof memory guards remain unchanged; full 30-variable queries
are not enabled by this experiment.

## Required controls before timing

Run optimized and UBSan CPU builds and an explicitly selected Metal build
where available. Compare partial enabled/disabled on the existing frozen
native corpus and every complete-query fixture. Require identical complete
roots and reduced bases; disabled proofs must match the accepted producer.
Independently replay new proofs from original ANFs using a separate Python
checker, including original equation and curve replay for full queries.

Add forced rank-deficient roots and empty systems, rank-zero/full-rank cases,
symmetry copies and copy exhaustion, both coefficient limbs, altered or
nonlinear witnesses, malformed/unknown tags, overlap, duplicates, reordered
records, missing-record fallback, old-checker rejection, configuration reuse,
closed/concurrent handles and producer/checker budget exhaustion.

Freeze a separate full-comparator timing protocol only after these checks.
Report complete-query cost and failed/fallback attempts, not assignment-count
ratios as speedups. Candidate and IC online speedup remain null; this is not
a same-point complete IC/rho comparison or a general F4/F5 ranking.
