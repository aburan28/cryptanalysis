# Held-out paired-τ scalar result

Source, tests, algebraic protocol, and checker were frozen in
`bb9f1029`. Independent affine fixtures were frozen in `2e0b6c8c`
before either panel ran. Release and UBSan both passed the serial
control/paired/paired/control gate on each curve. All 16 raw trials,
including exit status, stdout, stderr, source and binary hashes, and
independent output digests, are retained in `panel-release.json` and
`panel-ubsan.json`. Operation counters agree exactly across builds.

| Curve; 1,024 pairs | τ steps | Fused pairs | Pairs with free Z scale | Formula multiplications saved |
| --- | ---: | ---: | ---: | ---: |
| `glv-j0-32` | 13,482 | 5,266 | 771 | 6,037 |
| `j0-56` | 33,671 | 13,200 | 2,029 | 15,229 |

The last column is `tau_pairs + tau_pair_cheap_z`, from the frozen
`8M+4S` versus `7M+4S` or `6M+4S` formulas. It is 11.2% and 11.3%
of the original τ-map multiplication count on the two curves. The
control and paired modes have identical scalar recoding, pair scoring,
τ-step counts, mixed additions, rotations, inversions, prepared-table
size, and verified point outputs. The source-level multiplication
reduction is real; the effect on CPU time needs controlled measurement.

The two-repeat Release medians for control/paired `online_ms` were
`0.943/0.914` on `glv-j0-32` and `1.990/1.868` on `j0-56`.
UBSan medians were `9.266/9.255` and `18.671/19.211`; the direction
is mixed. The host lacks verified exclusive CPUs, NUMA isolation, fixed
frequency, and noise gates, so both panels keep
`cpu_speedup_claim: null` and `isolation_receipt: null`. These are
scalar-stage batches, not the primary one-target online comparison.

Release passed all 16 CTest tests with warnings as errors; UBSan
`joint_tau` passed. This opt-in evaluator has no automatic routing.
The next gate is a verified one-target rho-restart integration on the
same public target, followed by paired timing in the isolated benchmark
service. Academic novelty of the τ²/tripling combination remains
unestablished.
