# E-1: longest-gap candidate mask for N83 root canonicalization

The candidate-mask method cuts full Frobenius rotations by 70.40% in the
frozen N83 target stage while preserving every completed exact lookup and
target result. It records the positions following the longest cyclic zero
gaps in one pass, then rotates and compares only those positions. The
existing sparse 26-bit index and 16-byte exact root records are shared by
both arms.

For a nonconstant binary word, its lexicographically least cyclic rotation
begins after a longest cyclic zero gap: a shorter initial zero run would
compare larger. All longest-gap positions remain candidates. Comparing their
complete rotations, then choosing the smallest shift on an equal value,
preserves the original canonical key and shift. The implementation handles
the all-zero and all-one words directly.

The curve is `EC1N83Ckb1h876c2921cb64`, workload `981ac530e67e`, and
proposal `Q2026101007`. The parent factor base has 30,977,592 usable points
and 186,612 folded columns. Each arm indexes 2,000,000 sampled pair states
and 4,000,000 exact root records, then scans the same single public target.
The RSS cap is 1,024 MiB and the per-arm process timeout is 180 seconds.
Candidate and run IDs remain null for this bounded decomposition stage.

| Method | Index-build rotations | Target rotations | Completed target stage | Stage status |
| --- | ---: | ---: | --- | --- |
| Zero-gap scan | 19,127,078 | 38,261,354 | 19.075, 27.158 s; one 180 s timeout | `state_cap_no_relation` in completed rows |
| Longest-gap mask | 5,661,620 | 11,325,200 | 19.678, 62.052, 100.191 s | `state_cap_no_relation` in all three rows |

The six-run order was reference/candidate, candidate/reference,
reference/candidate. The local host load reached about 160 during the first
pair and changed sharply across the panel. The timeout is retained as a
censored row in [`summary.json`](summary.json); no target-stage wall-time
ratio is promoted from these runs. The target-stage clock begins after
target-independent index construction and includes query preparation,
batched S3 roots, partner canonicalization, exact lookup, and native
relation checks. Raw phase times, memory, and host receipts are retained
for each completed arm. Every completed arm stayed below the RSS cap.

Four Rust release tests passed, including exhaustive small-field rotation
comparisons, 100,000 randomized N83 words, exact hit/miss and duplicate
first-witness parity with the hash index, and batched S3 roots. Across the
five completed full-stage rows, frozen lookup samples, stage status,
noncanonical arithmetic counts, 35,837 full-key probes, 3,767,807 tagged
singleton buckets, and 445,046 singleton-tag rejections matched. Their
paired correctness certificate is recorded in `summary.json`. Fresh
isolated-service wrapper replays of both arms passed and emitted the same
certificate `fc7ff8a273c09d8c209801adec5bcaa54af3f60799dabd91495192976486f736`;
[`replay_check.json`](replay_check.json) retains their output digests. The source
also corrects the native report to state the actual packed record width.

Run `python3 run.py` in this directory to build and execute the frozen
counterbalanced panel, then `python3 summarize_censored.py` to validate
completed rows and retain timeout rows. `run.py` exits nonzero when an arm
times out; it preserves each raw record before exiting. Set
`N83_E1_TARGET_DIR` for the Cargo output directory. The repository's
[CPU isolation contract](../../../docs/ISOLATED_BENCHMARKS.md) applies to a
controlled wall-time comparison on a physical host. `make_manifest.py`
validates the frozen source, input, and fixture hashes and creates the
paired isolated-service manifest for that host.
