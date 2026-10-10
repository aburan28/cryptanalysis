# Round104 diagnostic results

The opt-in checker transfers the word buffer of a distinct XOR operand on its
last use to the result. Exact proofs, logical term lifetimes and conservative
work charges match the allocating checker. A separate ownership simulation
checks physical allocation, transfer, release and peak-buffer counts.

Source freeze: `6f6ab08aace35cc1dab184540b579b7e6200da64` (75 bound sources;
18 optimized/UBSan libraries). The later predecessor merge changes only round98
formatting; all 75 executed source hashes remain identical. The lossless
[evidence archive](results.tar.gz), bound by [archive.json](archive.json), retains
the failed first validation, full successful second validation, raw proofs,
summary, phase analysis and publication controls.

The first build passed but unit tests caught an audit helper that removed timing
fields from dictionaries/lists without traversing tuples. Fixing that traversal
changed no numerical kernel. No timing panel ran before the fix. The complete
preset panel ran once after the fix. The first synthetic publication-control
attempt later exited 120 without a completed receipt during storage pressure;
its partial files and empty log remain preserved. The second attempt passed all
15 negative controls. Its interruption record distinguishes the undetermined
exit cause from a separate inspection-command path error.

## Complete-query observations

Milliseconds, median ± median absolute deviation, four observations per cell
following one warmup, with the frozen arm rotation. **Qualified, aggregate and
IC online speedups are null:** the local ARM64 macOS host has no auditable
isolation receipt. These are small planted algebra controls, not the original
18-variable query or a complete IC/rho comparison.

F4 pairs have identical list output. Matrix pairs have identical owned binary
output. Query timing includes fresh coefficients, production, independent
certification, proof ownership, extraction, equation/curve replay and teardown
for PDP controls; MQ controls end at the certified algebraic result. Reusable
setup and artifact serialization/storage remain separately recorded. Optional
packed-to-list conversion stays outside both matrix arms and is reported in
the raw observations. No paired arm changes the output API.

| Case | F4 allocating | F4 reuse | Matrix allocating | Matrix reuse |
| --- | ---: | ---: | ---: | ---: |
| pdp-6-seed-1 | 4.146 ± 0.080 | 4.330 ± 0.121 | 3.007 ± 0.060 | 3.048 ± 0.088 |
| pdp-6-seed-3 | 3.906 ± 0.106 | 3.939 ± 0.109 | 3.438 ± 0.010 | 3.492 ± 0.013 |
| planted-dense-mq-12 | inconclusive (0/4) | inconclusive (0/4) | 9.604 ± 0.085 | 7.749 ± 0.109 |
| pdp-9-seed-1 | inconclusive (0/4) | inconclusive (0/4) | 16.817 ± 0.482 | 16.432 ± 0.129 |
| pdp-9-seed-2 | inconclusive (0/4) | inconclusive (0/4) | 16.633 ± 0.163 | 16.059 ± 0.124 |
| pdp-9-seed-3 | inconclusive (0/4) | inconclusive (0/4) | 17.568 ± 0.186 | 17.101 ± 0.365 |
| pdp-9-seed-4 | 61.418 ± 0.362 | 61.045 ± 0.182 | 12.790 ± 0.077 | 12.629 ± 0.142 |
| pdp-9-seed-5 | inconclusive (0/4) | inconclusive (0/4) | 16.854 ± 0.309 | 16.629 ± 0.306 |
| pdp-12-seed-1 | inconclusive (0/4) | inconclusive (0/4) | inconclusive (0/4) | inconclusive (0/4) |
| pdp-12-seed-2 | inconclusive (0/4) | inconclusive (0/4) | inconclusive (0/4) | inconclusive (0/4) |
| pdp-12-seed-3 | inconclusive (0/4) | inconclusive (0/4) | inconclusive (0/4) | inconclusive (0/4) |
| pdp-12-seed-4 | inconclusive (0/4) | inconclusive (0/4) | inconclusive (0/4) | inconclusive (0/4) |
| pdp-12-seed-5 | inconclusive (0/4) | inconclusive (0/4) | inconclusive (0/4) | inconclusive (0/4) |

All matrix observations certify the five nine-variable PDP controls and MQ12.
F4 certifies only nine-variable seed 4 at the same fixed producer budget. Every
arm remains inconclusive on all five twelve-variable PDP controls. No failed or
fallback attempt was removed. Small six-variable controls show no consistent
benefit, and the nine-variable complete-query change is small. Reuse remains
opt-in; allocation reduction alone is not a timing acceptance gate.

## Mechanism and remaining costs

| Case / matrix arm | Payload allocations | Buffer transfers | Scoped peak bytes | Checker ms |
| --- | ---: | ---: | ---: | ---: |
| pdp-9-seed-4 / matrix-packed | 39,409 | 0 | 1,447,652 | 5.239 ± 0.035 |
| pdp-9-seed-4 / matrix-reuse | 486 | 38,923 | 1,447,588 | 4.967 ± 0.125 |
| planted-dense-mq-12 / matrix-packed | 68,845 | 0 | 2,866,004 | 5.017 ± 0.023 |
| planted-dense-mq-12 / matrix-reuse | 798 | 68,047 | 2,865,492 | 3.461 ± 0.087 |

Reference allocation counts follow directly from its one-payload-per-created-
value implementation; candidate counts are native counters cross-checked by
independent simulation. Peak bytes cover the explicitly budgeted dense-checker
scope, not process RSS. Peak savings are just 64 bytes for nine-variable seed 4
and 512 bytes for MQ12: existing liveness already kept few payloads alive.
The frozen proofs have no unreachable stored nodes, so reachability pruning was
a negative structural finding. The inherited word-work counters retain
conservative initialization charges and are not hardware instruction counts.

For nine-variable seed 4, candidate derivation takes 0.752 ms and reverse
membership 3.960 ms out of 4.967 ms total checker time (phase medians). For MQ12,
derivation takes 3.325 ms out of 3.461 ms. Medians of individual phases need not
sum to the median total. These distinct profiles motivate different next tests:
ordered-bitset or cached-order normal forms for reverse membership, and a
compact derivation representation for the matrix-generated proof. Both remain
hypotheses requiring applicability checks, CPU fallback and full-query timing.

## Correctness and evidence

Eight unit-test groups pass in optimized and UBSan configurations, covering
random ideals, all reclamation policies and phase schedules, left/right donors,
aliased operands, zero/unused/output-pinned values, exact work/term/byte budget
boundaries, exception recovery, malformed proofs, changed coefficients,
concurrency and native-free import. Tests include word boundaries, wide equation
limbs and sparse fallback for rings with 13, 32 and 64 variables.

- 104 control cells: 44 algebra certificates, 40 solved PDP controls, 60
  inconclusive outcomes, zero process failures, 52 exact trace pairs, 44 lifetime
  checks, 28 equal-basis comparisons and 20 retained fallbacks.
- 260 diagnostic cells including 52 warmups: 110 algebra certificates, 100 solved
  PDP controls, 150 inconclusive outcomes, zero process failures, 130 exact trace
  pairs and 50 retained fallbacks.
- All 43 corrupted-artifact controls rejected, including forged transfer,
  allocation and release counts and changed reuse policy.
- Fifteen synthetic publication-admission corruptions rejected. They test the
  admission auditor and are not actual remote CI receipts.

Independent artifact checks verify ideal equality, Boolean Gröbner completion,
exact producer/proof correspondence, equations and curve replay, budget/lifetime
accounting, ownership simulation and source/resource custody. Linux/macOS CI
rebuilds and verifies the final published source before merge. No GPU result,
ordinary relation yield, F4/F5 leadership or asymptotic F6 claim follows from
these diagnostics.
