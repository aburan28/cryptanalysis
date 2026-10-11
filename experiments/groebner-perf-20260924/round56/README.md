# Sparse F4 matrix-output selection and deferred-tail ablations

The cached sparse F4 implementation sends every echelon pivot through polynomial
normalization, including pivots already represented by symbolic reducer rows.
This experiment discards those redundant outputs before normalization and
combines that selection with round55's checked chain criterion. Every successful
result still passes the unchanged independent algebraic checker. Application
dispatch and earlier experiments remain unchanged; callers explicitly choose a
variant.

This is established F4 engineering. Faugère's
[original F4 paper](https://wstein.org/129-05/refs/faugere_f4.pdf), section 2.1,
defines matrix-output selection after symbolic preprocessing and echelon reduction.
The code uses the equivalent reducer-head test described below for this producer's
matrix construction. It does not introduce a novel F6 algorithm.

## Why filtering is valid

Symbolic preprocessing visits every monomial in the matrix support. For each
monomial divisible by an installed basis leader, it inserts one shifted basis
row having that exact leader. Boolean multiplication by the disjoint leading
quotient preserves that leader; all its other terms are smaller. Newly introduced
terms are visited too. `reducer_heads` records exactly these inserted pivots.

The echelon rows span the same space as the critical rows and those reducers.
For each recorded reducer head, its original reducer is that echelon pivot plus
a combination of lower pivots. Induction over the ordered pivots therefore
expresses every discarded row using the original reducers and retained pivots.
Only the retained outputs can add information modulo the old basis. We filter
against the immutable basis used for this matrix, then normalize retained rows
against the growing basis as before. No critical or Boolean field pair is
silently removed by this selection.

Insertions and membership tests in `reducer_heads` each cost one logical work unit.
Telemetry records output and skipped pivot counts. These counters are stage
diagnostics, not machine instructions or full IC operation counts.

## Negative ablation: defer polynomial tails

`top_normal.inc` reduces only the leading term until that head is irreducible.
Every reduction updates the witness for the entire polynomial. Such an installed
row enlarges the leading ideal; all ordinary and Boolean field pairs remain, and
final interreduction still reduces every term. This is algebraically valid but
performed worse on the solved controls: retained tails enlarge subsequent work.
The implementation and failed budget rows remain available as an explicit
ablation. No automatic routing selects it.

| Variant | Checked chains | Reducer-pivot filtering | Deferred tails |
| --- | --- | --- | --- |
| `prior` | no | no | no |
| `chain` | yes | no | no |
| `top_new` | no | no | new matrix rows |
| `top_all` | no | no | initial and new rows |
| `chain_top_new` | yes | no | new matrix rows |
| `chain_top_all` | yes | no | initial and new rows |
| `filter` | no | yes | no |
| `chain_filter` | yes | yes | no |
| `filter_top` | no | yes | new matrix rows |
| `chain_filter_top` | yes | yes | new matrix rows |

## Validation and measurement boundary

Run from the repository root, with a new output directory:

```sh
python3 experiments/groebner-perf-20260924/round56/run_validation.py --output sparse-f4-evidence
```

This rebuilds 36 producer/checker libraries across both rounds, including UBSan,
runs ten unit groups and six direct native probe controls, retains 552 frozen
algebra rows, and validates 120 fresh planted PDP queries. The complete query
controls include fresh target coefficients, packing, solving, native algebraic
certification, bounded root extraction, original-equation evaluation and curve
replay. Forty queries succeed; the 80 work-budget failures remain results. An
additional portable audit independently replays every distinct successful proof
from the original equations and binds the evidence to sources and rebuilt files.

The non-enumerative algebraic checker accepts masks through 64 variables. The
supplementary root-extraction path here scans at most 4,096 assignments and does
not establish non-enumerative root finding for larger systems. Planted queries
are correctness controls, not natural relation-yield measurements. No row is a
full IC target solve, and `candidate_id` and `online_speedup` remain null.

Linux and macOS CI each rebuild native code on that runner. Artifacts retain the
runner identity, source and binary digests, all successful proofs, failures and
independent replay. A correctness pass does not establish a speedup on that
platform. This experiment has no GPU implementation or automatic GPU routing.

See [RESULTS.md](RESULTS.md) for charged-work observations and the remaining
complete-query timing requirement.
