# Complete-query checker comparison

This experiment integrates the exact round93 completion ordering and round94
proof-value reclamation into the round60 leased packed-input path. The producer
is the unchanged round62 F4 kernel. All configurations solve from fresh target
coefficients and produce fresh proofs. There is no automatic dispatch change.

The immutable round13 fixture contains eight algebra controls and fifteen
planted PDP correctness controls (6, 9, and 12 Boolean variables). The PDP
controls are not estimates of ordinary relation yield, unseen-target recovery,
or IC/rho performance. Algebra controls include easy systems up to 64 variables
and budget-limited dense systems; variable count is not a hardness measure.

Four arms use identical producer limits and workspaces: legacy checking,
completion-first checking, and completion-first checking with reclamation under
cumulative or live-term budgets. The last policy changes what the term limit
counts. It does not bound process RSS, allocator overhead, or all temporary
storage. All arms retain exact ideal equality and Boolean completion checks.

The measured interval starts before target coefficient descent (or control
coefficient copying) and ends after the input lease is released. Four exclusive
phases sum exactly to the interval: descent/input preparation; native solving,
certification and materialized proof export; bounded extraction and curve replay;
and independent original-equation/curve replay plus lease teardown. Frozen
coefficient equality is also checked inside the interval. The extraction search
is restricted to these at-most-12-variable planted controls. General high-degree
root extraction is not implemented here.

Fixture construction, field/ring layouts, library loading and reusable allocation
are setup. Preparation is reported separately. Summation polynomials are freshly
regenerated during each build into a private cache, with both JSON and pickle
bytes recorded. Artifact auditors must never unpickle downloaded resources or
load archived native binaries.

Correctness uses optimized and UBSan builds, all 23 fixtures and all four arms.
Diagnostics use two warmup rounds followed by four fixed balanced cyclic orders.
Run the preset once; retain all rows including unsuccessful attempts. Each call
is a fresh query; these repetitions do not constitute a multiple-target IC
measurement. Local host timing remains exploratory. Qualified, aggregate and
online speedups stay null without an auditable isolated-host receipt.

The independent native-free audit rechecks certificates, Boolean roots on small
systems, every solved PDP assignment against the original equations and curve,
proof lifetime counters, paired producer/certificate counters, full panel
coverage, source bindings and phase sums. Corruption controls test these gates.

From the repository root, after committing all executable sources:

```sh
python3 experiments/groebner-perf-20260924/round95/run_validation.py --output /absolute/new/evidence-directory --diagnostics
```

The runner acquires the shared local heavy-work lock, rebuilds on the current
platform, records source/native/resource bytes, and preserves failures. CI runs
correctness on Ubuntu and macOS without diagnostics. A CI correctness pass does
not qualify a speedup or establish performance on other hardware.
