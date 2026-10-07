# Held-out gauge-carrying paired-τ result

Source, exhaustive table verifier, tests, protocol, and checker were
frozen in `f0e96b24`; independent affine fixtures were frozen in
`0ad830d0` before either candidate ran. The serial unsteered,
steered, steered, unsteered gate passed in Release and UBSan on each
curve. All 16 raw trials, including failures, source and binary hashes,
operation counters, and independent affine output digests, are in
`panel-release.json` and `panel-ubsan.json`. The counters agree exactly
across builds.

| Curve; 1,024 pairs | Fused τ pairs | Free Z scales, unsteered → steered | Rotations, unsteered → steered | Net field multiplications saved |
| --- | ---: | ---: | ---: | ---: |
| `glv-j0-32` | 5,256 | 759 → 3,838 | 1,342 → 1,360 | 3,061 |
| `j0-56` | 13,166 | 2,010 → 9,382 | 1,765 → 1,776 | 7,361 |

The frozen net count is the increase in multiplication-free Z scales
minus the increase in digit and final rotations. All arms use the same
1,104-byte prepared object and exactly the same recoding, pair scores,
τ steps, fused-pair count, mixed additions, output inversions, and
point outputs. The steered arm adds one 78-entry table lookup per
fused pair. The source-level field-multiplication saving is exact for
the current formulas on these nonidentity subgroup trajectories;
table lookups and control flow still need CPU measurement.

The two-repeat Release median `online_ms` values were
`0.929/0.918` for unsteered/steered on `glv-j0-32` and
`1.904/1.850` on `j0-56`. UBSan medians were `9.308/9.175`
and `19.218/19.070`. The local host has no verified exclusive CPUs,
NUMA isolation, fixed frequency, or noise gates. Both panels keep
`cpu_speedup_claim: null` and `isolation_receipt: null`.
These scalar-stage batches do not replace a one-target online result.

Release passed all 16 CTest tests with warnings as errors; UBSan
`joint_tau` passed. The new mode remains opt-in. A paired one-target
rho-restart replay and host-isolated timing are the next gates.
Academic novelty is unestablished: τ, the tripling formula, and
unit-invariant precomputation have prior art in the supplied paper;
this experiment tests their gauge-carrying combination.
