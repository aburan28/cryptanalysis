# E-1: bit-parallel longest-zero-gap root canonicalization

The bit-parallel method locates every longest cyclic zero gap with word-wide
AND and rotation operations, then compares only the corresponding full root
rotations. On the frozen N83 one-target stage it preserves every exact
result and lowers the exploratory median partner-canonicalization phase from
16.324 to 6.555 seconds. Median full target-stage time was 52.671 seconds
for the merged candidate-mask reference and 45.508 seconds for the
bit-parallel arm on this contended host. A physical-host isolation receipt
is required to promote the wall-time ratio.

For a nonconstant binary word, its least cyclic rotation begins after a
longest zero run. Bit `i` in the span mask for width `w` means the `w`
cyclic bits beginning at `i` are zero. Doubling builds masks for widths
1, 2, 4, 8, 16, 32, and 64; binary lifting finds the maximum run length
and all its start positions. Rotating those positions by the run length
gives the same candidate shifts as the merged gap-mask method. Full-word
comparison and the smallest-shift tie rule then produce the exact canonical
key and shift. Constant words are handled directly.

The curve is `EC1N83Ckb1h876c2921cb64`, workload `981ac530e67e`, and
proposal `Q2026101008`. The parent factor base has 30,977,592 usable points
and 186,612 folded columns. Both arms index the same 2,000,000 sampled
pair states and 4,000,000 exact 16-byte root records, then scan the same
single public target. The sparse 26-bit bitmap-rank directory, singleton
tags, full-key binary search, 1,024 MiB RSS cap, and 180-second per-arm
timeout are shared. Candidate and run IDs remain null for this bounded
decomposition stage.

| Method | Median target stage | Median partner canonicalization | Median index build | Table bytes | Median peak RSS | Full-key probes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Gap mask | 52.671 s | 16.324 s | 20.451 s | 93,360,128 | 508,510,208 | 35,837 |
| Bit parallel | 45.508 s | 6.555 s | 18.621 s | 93,360,128 | 514,883,584 | 35,837 |

The six-run order was reference/candidate, candidate/reference,
reference/candidate. Target-stage ranges were 39.084–68.789 seconds for
the reference and 26.453–47.245 seconds for the candidate. Host load and
RSS changed across runs; these wall times are exploratory. Index building
is target independent and outside the target-stage clock. The clock includes
target query preparation, batched S3 roots, partner canonicalization,
exact lookup, and native relation checks. Every run recorded
`state_cap_no_relation` below the RSS cap. Raw phases and row order are in
[`summary.json`](summary.json).

Four Rust release tests passed, including exhaustive small-field and
100,000 randomized N83 canonical key/shift comparisons, exact hit/miss and
duplicate first-witness parity with the hash index, and batched S3 roots.
All six full-stage rows matched the frozen lookup sample, target status,
arithmetic counters, 35,837 full-key probes, 3,767,807 tagged singleton
buckets, and 445,046 singleton-tag rejections. Fresh isolated-service
wrapper replays of both arms emitted the same pair certificate
`2665304bcdb73b73a19a155744d2fcfde7cb8dfde41e7ef05c454b2a47add288`;
[`replay_check.json`](replay_check.json) retains their output digests.

Run `python3 run.py` in this directory to verify the frozen crypto snapshot,
build, and execute the six-arm panel. Set `N83_E1_TARGET_DIR` for the Cargo
output directory. `make_manifest.py` validates all frozen source and input
hashes and prepares a paired manifest for the repository's
[isolated CPU benchmark service](../../../docs/ISOLATED_BENCHMARKS.md).
