# Bounded radix sorting

Round99 replaces packed-key comparison sorting on sufficiently large normal
multiplication rows with stable byte-wise radix passes. Constant bytes are
skipped. Per-query scratch is bounded; small, wide and over-cap rows retain
comparison-sort fallbacks. The unchanged producer remains the default.

The frozen twelve-variable control records lower local cost to the same work
limit. It remains inconclusive, and this unqualified host does not establish a
solved-query speedup. Small solved controls do not improve consistently.

- [Sorting proof, memory contract and frozen protocol](PROTOCOL.md)
- [Results and next decision](RESULTS.md)
- [All 92 raw timing/counter cells](summary.json)
- [Lossless evidence archive](results.tar.gz) and [custody receipt](archive.json)

Optimized/UBSan validation passes seven test groups, 16,384 native multiplication
cases and 1,728 sorting cases per build, 184 complete-query controls, 552 preset
diagnostic calls and 31 artifact corruption controls.
