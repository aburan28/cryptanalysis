# Packed monomial-order keys

Round98 encodes the existing descending-grevlex order once per term inside
`ordered_multiple`, then uses unsigned integer sorting. It preserves exact
proofs, work charges and failure behavior. Masks using bits above 56 retain
the original comparator. The baseline remains the default.

The twelve-variable control shows lower local elapsed time to the same work
limit, with no qualified speedup claim. Small solved controls are noisy and
these measurements do not establish a solved-query improvement.

- [Representation proof and frozen protocol](PROTOCOL.md)
- [Results, failures and next decision](RESULTS.md)
- [All 92 raw timing/counter cells](summary.json)
- [Lossless evidence archive](results.tar.gz) and [custody receipt](archive.json)

Validation passes six test groups, 32,768 native multiplication cases and
1,049,088 order comparisons per optimized/UBSan build, 184 complete-query
controls, 552 diagnostic calls and 26 artifact corruption controls.
