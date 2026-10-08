# Producer work attribution with unchanged traces

This is a diagnostic correctness experiment, not a timing comparison. The
unchanged round95 complete-query boundary runs the same frozen 23 fixtures and
20-million-unit producer budget. Baseline/profiled order is reversed on the
second pass. Both optimized and UBSan builds run both orders, for 184 calls.
Every call has fresh coefficients, solver state, proof and independent checking.
All failed attempts remain rows. Planted PDP fixtures remain correctness controls.

The profiled producer adds allocation-free thread-local accounting scopes to
the round62 engine. Exclusive buckets partition the producer's **existing
logical budget units**. Inclusive counters include nested scopes and therefore
must not be summed. Calls count scope entries, including entries that unwind
on failure. Decode contains charges outside an engine scope. Allocation,
sorting and other uncharged work cannot be ranked by these budget counters.
These are not retired instructions, CPU cycles, FLOPs or wall-time shares.

The original atomic charge and repeated-unit shortcut retain their distinct
exhaustion semantics. Both are instrumented. Counter overflow is explicit and
invalidates the profile. Scopes restore the prior category during exception
unwinding; internally handled chain probes retain all charged work. Existing
matrix/column/scratch/pair-pruning counters are copied after each call.

The native unit controls exercise nesting, partial versus atomic exhaustion,
zero and exact-limit products, saturation and thread-local isolation. Python
tests compare exact non-timing producer/checker traces and exported witnesses
across work, node, row, and checker budget boundaries, changed inputs and
concurrent queries. The full panel additionally preserves original equation and
curve replay inside complete PDP intervals.

The native-free auditor checks all mathematical certificates, complete phase
accounting and fixture coverage. Every baseline/profiled pair must have an
identical non-timing result, including proof, statuses and failure reason.
Profiles must reproduce across build modes and reversed order. Exclusive work
must sum exactly to the original producer work, with no overflow or open scope.

No dispatch policy changes. No native diagnostic timing is promoted to a
speedup, and no IC/rho or F6 asymptotic result is claimed. Use the profile to
select the next source-level experiment, then measure an uninstrumented
candidate on a qualified host with the complete-query boundary.

After committing executable sources, run from the repository root:

```sh
python3 experiments/groebner-perf-20260924/round96/run_validation.py --output /absolute/new/evidence-directory
```

The runner takes the shared local heavy-work lock, rebuilds every library and
native test on this platform, binds all sources and generated resources, and
retains raw successful and unsuccessful calls. Downloaded native artifacts and
pickle resources must never be executed by the publication auditor.
