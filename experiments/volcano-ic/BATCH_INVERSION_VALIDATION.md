# Batch inversion validation for volcano IC

The factor-base constructor now uses Montgomery's batch inversion trick: one field inversion and O(B) multiplications for B nonzero x-coordinates, instead of B inversions. It preserves enumeration order and point-lift equations.

## Verify before merging

From `experiments/volcano-ic`, run `sage -python` or Sage with `load("ic.sage")` and construct a reference factor base with the original per-x inversion. Compare the exact x -> point mapping, not just factor-base cardinality, for E0 and several descendants. Then run `python3 crosscheck.py`, `sage crosscheck.sage`, and a bounded `sage run.sage census 0 457` shard. Compare against archived output hashes/semantic fields. Benchmark setup CPU seconds over repeated interleaved runs and record field size and k.

The inverse table requires O(B) additional field elements. For large k, benchmark chunked batch inversion to cap memory.

**No measured speedup is claimed in this PR.** This is a candidate optimization that requires Sage regression tests and benchmarking.
