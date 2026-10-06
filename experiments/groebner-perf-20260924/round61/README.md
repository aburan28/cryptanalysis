# Bounded scratch storage for sparse F4 matrix XOR

This opt-in experiment compares fresh-vector XOR against reusable scratch storage
inside the round 58 column-indexed matrix reducer. Both arms use the round 60
leased ANF input path and fresh target coefficients, solving, and independent
certification. The complete-query interval includes descent/input filling,
native decoding, solving and independent checking, extraction, original-equation
and curve replay, and lease teardown. Fixture construction and invariant layout
construction remain outside it.

The candidate holds one scratch vector per matrix, requesting at most 32,768
64-bit words (256 KiB of element storage, excluding allocator overhead). Each
eligible XOR clears and fills scratch, emits the same witness, then swaps the
numeric row into place. Inputs remain unchanged if witness emission throws.
Larger XORs take the fresh-vector path. An oversized initial allocation acquired
by a swap is released; before a pivot is retained, any capacity above the last
fresh-vector request is compacted. This prevents a large earlier XOR from
silently inflating the storage retained by later small pivots. Scratch is
destroyed on normal return or exception; no matrix values or witness IDs are
cached across matrices or queries.

The arithmetic order, proof graph, Boolean completion checks, original work
charges and output rows are unchanged. Additional copies and scratch management
are real work charged by the wall clock; equality of the historical work counter
does not imply equal physical CPU work. The unchanged independent checker source
is rebuilt locally for each tested platform.

`baseline` uses fresh vectors, `scratch` has the 32,768-word cap, and the unit-only
`tiny` arm has a four-word cap to exercise both reuse and fallback. Thread-local
counters report XOR attempts after their work charge, fresh-vector reserve
requests, scratch growth requests, reuse, pivot compactions and scratch capacity.
These count allocation requests in this matrix loop only. They are not whole
query allocator counts or timing speedups; compaction requests must be included
when comparing the two paths.

The frozen plan compares the same 23 inputs and budgets as rounds 59–60. The
primary panel is five complete small PDP queries, three independent timing
trials each, seven measured pairs after one warmup. Eighteen other algebra/PDP
controls retain failures. Every query is sequential; there is no multi-target
throughput metric. A fully qualified panel is needed before claiming a wall-time
improvement or changing default dispatch. These are solver-stage diagnostics,
not a complete IC candidate or a rho comparison.

Validation covers optimized and UBSan builds, 128 random ideals, independent
algebraic and small truth-set checks, wide 64-variable inputs, early/late work
limits, all proof-node cutoffs on a small matrix, changing leased coefficients
through 129 equations, four-thread reuse, and the bounded fallback. The full
92-record preflight must match the round 58 frozen bases, proofs and integer
traces. An independent artifact audit replays certificates and curve solutions
without loading archived native binaries.

From the repository root:

```sh
python3 experiments/groebner-perf-20260924/round61/run_validation.py --output scratch-evidence
```

CI rebuilds on Linux x86-64 and macOS ARM64. Other architectures are untested.
See `RESULTS.md` for the recorded local attempt and its limitations.
