# Multiplication/squaring-aware selective atlas: design-data screen

The current selective recoder minimizes `M+S`, implicitly assigning
equal costs to multiplication and squaring. The native formulas have
different `M,S` vectors. Screen three declared scalar weights,
`M=1000` and `S∈{500,750,1000}`, on the **original 64-case design
panel only**. These weights are hypotheses, not hardware calibration.

Retain the same two-choice width-four alphabet, bounded carry,
16-position tail, seed dependency graph, and tie order. Replace the
single source cost with exact `M,S` vectors: τ step `(4,2)`, paired
step discount `(2,0)`, mixed add `(8,3)`, cached general add `(11,3)`,
cache entry `(1,1)`, point double `(2,5)`, seed mixed add `(8,3)`,
and each unit/orbit rotation `(1,0)`. First nonzero digit initializes
the accumulator, so its addition is free. Verify the vector by a
separate recount of the selected stream and preparation mask.

For each weight, report the chosen stream's total `M,S`, weighted cost,
the equal-weight incumbent recoded under the same weight, per-case
differences, and digit-choice changes. Reproduce the saved 64-case
equal-weight total of 87,298 as an accounting control. This is a
retrospective design screen; any promising weight-specific rule needs
a frozen independent workload and a physical-host calibration before
performance claims. Academic novelty remains open.
