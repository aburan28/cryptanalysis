# Independent partial-affine coefficient locality

This opt-in checker candidate copies each partial record's freshly reconstructed
coefficients into contiguous local storage before checking its nonzero witness
rows. The existing round51 producer, GPU shader, proof format, rank recomputation,
root completeness check, and reduced-basis check are unchanged. Only immutable
monomial layouts are reused between targets; the coefficient copy is overwritten
for each record and each certification.

`adapter.ProjectionQuery(..., partial_coefficients="local")` selects the
candidate. `partial_coefficients="strided"` retains direct source-table reads
in the same new checker. The round51 adapter is the unmodified comparator.
CPU remains the default producer backend and the accepted implementations
remain available. Direct producer checks preserve their prior full-record
verification behavior; complete queries retain the explicit symmetry option.

The copy is lazy: zero witness rows do not trigger it. At most 112 coefficient
words fit the validated residual dimensions. All existing verification-budget
charges occur in the original order. Copy reads/writes and cached reads are
reported separately in `partial_locality_stats`; copying does not change the
old verification-work unit. A copy costs at most 112 words per reached nonzero
partial record. The complete query clock includes this work. `cache_stack_bytes`
reports the C++ cache object's size, not a measured native stack high-water mark.

## Correctness

Build the same portable dependencies as round51, then run:

```sh
python3 experiments/groebner-perf-20260924/round52/build.py
python3 -m unittest discover -s experiments/groebner-perf-20260924/round52 -p 'test_*.py' -v
python3 experiments/groebner-perf-20260924/round52/validate_native.py --output /tmp/locality-local.json.gz
python3 experiments/groebner-perf-20260924/round52/validate_native.py --partial-coefficients strided --output /tmp/locality-strided.json.gz
python3 experiments/groebner-perf-20260924/round52/audit_cache.py --input /tmp/locality-local.json.gz --output /tmp/locality-cache-audit.json
python3 experiments/groebner-perf-20260924/round52/audit_queries.py --input /tmp/locality-local.json.gz --output /tmp/locality-proof-audit.json
```

These are standalone Python jobs, not Sage jobs. On macOS, build the producer
dependencies with their `--metal` option and add `--metal` to validation. Set
`QUADRATIC_TEST_METAL=1` for the unit suite only after detecting a working device.
Every platform rebuilds native code. Device absence is an explicit result.

The unit suite covers both coefficient widths and limbs, all transform modes,
fresh valid/invalid/valid inputs, zero/dependent/reordered/missing witnesses,
proof limits, rollback, native configuration, and isolated factories. The
dedicated audit build compares every cached coefficient used by a witness
against the independent table. It replays every distinct query/proof with full
and tile16 transforms. Each full query is also compared with a fresh round51
query, including proof bytes/hashes, roots, bases, assignments, and existing
integer counters. A separate Python audit checks proofs from original ANFs.

## Performance contract

`measurement_plan.json` freezes seven arms, input order, pairing seeds, load
admission, repetitions, and the acceptance criterion. The complete-query
boundary includes fresh coefficient reconstruction, solving, independent
certification, direct equation checks, transfers/synchronization, and curve
replay. Reusable setup is separate. All failed admissions and executions remain
records. No owned build, validation, or audit on the timed host may overlap a timing campaign.
The cache audit must pass before measurement and is excluded from timing.

Source-level table-read counts do not establish cache misses, native loads, or
elapsed speedups: a copy adds contiguous reads and writes. The strided new-checker
arm isolates instrumentation overhead. No routing promotion follows from
correctness alone, and no general F4/F5, asymptotic, or complete IC/rho speedup is
claimed. `candidate_id` and `online_speedup` remain null for these stage tests.
