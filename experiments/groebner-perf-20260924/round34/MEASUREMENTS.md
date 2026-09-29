# Physical M4 Pro measurements

These are complete public-point PDP queries on frozen planted inputs, not full
IC/rho recovery or natural relation-yield measurements. Raw reports retain
sources, binaries, every attempt, proofs, timing boundaries and device use.
All four reports passed independent mathematical and accounting audits.
The raw reports and original append-only journals remain in the local
`affine-multipliers/performance-v1` artifact archive. Their absolute paths,
hashes and full audit summaries are recorded in `results/performance-audits.json`.

## First qualified wide trial

Each input has seven measured paired repetitions plus one warmup. Both CPU
arms solve the same original input and independently certify the complete
answer. The old algorithm is unchanged round33 with both enumeration bounds
expanded to 2^27, so it completes the 27-variable controls. Reported speedup
is the geometric mean of paired old/new wall-time ratios; it is not the ratio
of the displayed medians. Intervals are paired bootstrap 95% intervals.

| Variables | Seed | Old CPU median ms | New CPU median ms | Paired speedup | 95% interval | Qualified win |
|---:|---:|---:|---:|---:|---:|:---:|
| 21 | 201 | 12.347 | 12.562 | 0.985× | 0.976–0.997 | no |
| 21 | 202 | 12.400 | 12.615 | 1.001× | 0.979–1.034 | no |
| 21 | 203 | 12.260 | 12.617 | 0.982× | 0.977–0.987 | no |
| 24 | 201 | 84.165 | 81.661 | 0.996× | 0.933–1.031 | no |
| 24 | 202 | 84.523 | 82.202 | 1.030× | 1.025–1.037 | yes |
| 24 | 203 | 84.054 | 81.757 | 1.019× | 1.000–1.031 | no |
| 27 | 201 | 2930.694 | 1478.574 | 2.069× | 1.888–2.371 | yes |
| 27 | 202 | 2912.124 | 1468.733 | 1.983× | 1.972–1.992 | yes |
| 27 | 203 | 2941.588 | 1477.010 | 1.992× | 1.977–2.015 | yes |

All three 27-variable comparisons qualify in this **one trial**. The first
confirmation attempt (`wide-2`) verifies every query but fails the unchanged
load contract: its maximum paired-group boundary load is 14.4453125 on 14
logical CPUs, above the predeclared limit of 14. It remains unqualified even
where its individual timings look similar. Do not count it as confirmation.

Only one 24-variable seed qualifies as a win; two 21-variable seeds show small
regressions. Both small-query trials meet the load gate, but their GPU results
are noisy: the second trial has one 18-variable interval crossing 1. No uniform
new GPU win or default-dispatch change is established by these measurements.
The affine stage is CPU code; requested Metal on 24/27 variables records CPU
shape fallback. Complete query cost includes proof production and checking.

## Exact work on the 27-variable seed 203 control

- Previous independent checker: 52,350,464 original residual assignments.
- New checker: 102,241 checked affine identities and 3,072 assignments.
- New producer: 6,168,399 matrix rows and 49,620,935 pivot-row XORs; six
  failed certificate attempts correspond to the six branches with roots.
- Both paths return the same six roots, reduced basis, selected assignment
  and full curve witness. No partial answer or heuristic rejection is used.
- New accounted producer workspace is 65,024,050 bytes; the checker table is
  48,234,496 bytes. These counters are not peak RSS or total process memory.

The failed 32-Mi-work development candidate, including its partial diagnostic
counts and inconclusive status, remains in the `prototype2` archive. The final
64-Mi-work policy is frozen in source and verified independently.

Fresh two-repetition small/wide correctness bundles are retained in `results/`
for rebuild-and-audit CI on Linux and macOS. Their timings are explicitly
correctness-only and cannot add performance wins. Further confirmation
attempts, if any, must retain their own admission records and full reports.
