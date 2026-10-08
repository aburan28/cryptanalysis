# Bounded storage for normal-reduction merges

The round96 profile identified repeated ordered polynomial merges in normal
reduction. This experiment replaces their fresh output vector with bounded
scratch storage local to one `normal()` invocation. It does not retain numeric
polynomials, pivots, coefficients or answers across queries.

Four explicitly selected arms use the same packed producer and independent
legacy checker: the unchanged baseline; an instrumented fresh-vector control
with cap zero; scratch with a cap of 32,768 mask words; and a four-word cap that
exercises the fresh-vector fallback. The application default is unchanged.

The new merge uses exactly the original descending grevlex comparator and XOR
proof operands. It charges the same term sum atomically before computing the
merge, and emits the same witness before replacing the input row. Work or proof
budget failure therefore leaves that input row unchanged. After exchanging
buffers, an oversized old input allocation is released. Retained scratch
capacity between completed merges is at most the selected cap (256 KiB for the
main arm). Transient scratch ownership of an oversized old input is counted
before release. This cap does not bound output-row storage, temporary multiples,
allocator overhead or process RSS. Scratch is destroyed on every normal-call
exit, including chain-probe exceptions.

Counters record charged merge calls, completed merges, new fresh vectors,
capacity growths, reuse without growth, oversized releases, and capacity peaks.
`fresh_vectors + growths` counts explicit requests for new vector storage; it is
not a sampled malloc count or elapsed-time measurement. Saturation is explicit
and invalidates the record. Calls that fail an atomic work charge are not counted
as storage requests; proof-node failures after a successful charge retain the
partial counters. The zero-cap control exposes the same merge request count as
the baseline while preserving its exact non-timing trace.

Native controls compare 6,144 combinations of ordered polynomials, caps, work
budgets and proof-node limits per build, including high-bit monomials, empty
polynomials, cancellation, aliasing, reuse and oversized release. Python tests
exercise the complete query, changed targets, budget boundaries and concurrent
thread-local state. The native-free audit requires identical proofs, statuses,
failure reasons and all mathematical counters for every baseline/candidate pair.

The frozen round13 fixture, limits and complete query interval are unchanged:
fresh coefficient descent through solving, certification, materialized proof,
bounded extraction, original equations/curve replay and lease teardown. Setup
stays separate. Fifteen PDP labels are planted controls, not ordinary-query yield
or IC/rho results. The five six-variable labels contain two distinct targets.
Wider algebra controls do not establish high-regularity solving performance.

Correctness runs all 23 fixtures × four arms × optimized/UBSan modes = 184 calls.
One preset diagnostic panel uses two warmups and four balanced cyclic orders =
552 calls. All failures remain rows. No timing is qualified without the
repository's host-isolation receipt; qualified and online speedups stay null.

After freezing executable sources, run from the repository root:

```sh
python3 experiments/groebner-perf-20260924/round97/run_validation.py --output /absolute/new/evidence-directory --diagnostics
```

The runner takes the shared heavy-work lock, rebuilds every native component,
records sources/generated resources/native bytes, and preserves failures. CI
rebuilds on Ubuntu and macOS. Downloaded native or pickle artifacts are never
executed by the publication audit.
