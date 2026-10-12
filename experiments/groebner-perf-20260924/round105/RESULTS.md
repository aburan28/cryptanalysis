# Round105 diagnostic results

The per-query quotient map removes repeated hash-set division from reverse
membership on the applicable frozen controls. Every original generator is
checked by XORing its monomial images, while forward derivation, reducedness,
Boolean completion and independent equation/curve replay remain required.
Sparse or excessive-dimension cases retain the ordinary membership checker.

Source freeze: `194b89b2` (81 bound sources; 20 optimized/UBSan native libraries).
The first full validation completed successfully. All eight preexisting
generated native/Python sources match round104 byte for byte; only the new
normal checker is additional. No timing cells were selected or rerun after
inspection. [results.tar.gz](results.tar.gz) retains the full records, proofs,
sources, binaries, independent model and publication controls; [archive.json](archive.json)
binds and verifies the lossless archive.

## Complete-query observations

Milliseconds, median ± median absolute deviation, four observations per cell
after one warmup, with the frozen arm rotation. The local ARM64 macOS host has
no auditable isolation receipt: **qualified, aggregate and IC online speedups
remain null**. These are planted correctness controls, not the original
18-variable query or an unknown-target IC/rho comparison.

Both arms use proof-buffer transfer. F4 pairs return the same list API; matrix
pairs return the same owned binary API. Fresh coefficient computation, producer,
map construction, independent certificate checking, proof ownership, extraction,
equation/curve replay and teardown remain inside the PDP query. MQ controls end
at the algebraic certificate. Reusable setup and artifact serialization/storage
are separate. Optional packed-to-list decoding is separately retained in the raw
records for both matrix arms; it is not silently included in the query times.

| Case | F4 hash membership | F4 quotient map | Matrix hash membership | Matrix quotient map |
| --- | ---: | ---: | ---: | ---: |
| pdp-6-seed-1 | 4.081 ± 0.118 | 3.894 ± 0.244 | 3.005 ± 0.090 | 2.714 ± 0.124 |
| pdp-6-seed-3 | 3.937 ± 0.129 | 3.897 ± 0.163 | 3.657 ± 0.105 | 3.283 ± 0.110 |
| planted-dense-mq-12 | inconclusive (0/4) | inconclusive (0/4) | 7.510 ± 0.036 | 7.812 ± 0.101 |
| pdp-9-seed-1 | inconclusive (0/4) | inconclusive (0/4) | 16.681 ± 0.212 | 10.562 ± 0.095 |
| pdp-9-seed-2 | inconclusive (0/4) | inconclusive (0/4) | 16.746 ± 0.067 | 9.677 ± 0.349 |
| pdp-9-seed-3 | inconclusive (0/4) | inconclusive (0/4) | 16.948 ± 0.447 | 10.199 ± 0.057 |
| pdp-9-seed-4 | 61.143 ± 0.463 | 54.568 ± 0.101 | 12.328 ± 0.298 | 8.186 ± 0.104 |
| pdp-9-seed-5 | inconclusive (0/4) | inconclusive (0/4) | 16.299 ± 0.283 | 11.160 ± 0.443 |
| pdp-12-seed-1 | inconclusive (0/4) | inconclusive (0/4) | inconclusive (0/4) | inconclusive (0/4) |
| pdp-12-seed-2 | inconclusive (0/4) | inconclusive (0/4) | inconclusive (0/4) | inconclusive (0/4) |
| pdp-12-seed-3 | inconclusive (0/4) | inconclusive (0/4) | inconclusive (0/4) | inconclusive (0/4) |
| pdp-12-seed-4 | inconclusive (0/4) | inconclusive (0/4) | inconclusive (0/4) | inconclusive (0/4) |
| pdp-12-seed-5 | inconclusive (0/4) | inconclusive (0/4) | inconclusive (0/4) | inconclusive (0/4) |

Coverage is unchanged. Matrix arms certify every nine-variable PDP control and
MQ12; F4 certifies only nine-variable seed 4 at the frozen producer budget.
All five twelve-variable PDP controls remain inconclusive for every arm. Those
outcomes and every failed matrix attempt/F4 fallback remain recorded.
MQ12 takes the density fallback, and its candidate full-query median is worse
in this run. No uniform improvement or production promotion is inferred.

## Membership phase and exact operation accounting

| Case / arm | Membership ms | Total checker ms | Complete checker charged work |
| --- | ---: | ---: | ---: |
| pdp-6-seed-1 / matrix-reuse | 0.356 ± 0.016 | 0.449 ± 0.020 | 39,099 |
| pdp-6-seed-1 / matrix-quotient | 0.014 ± 0.000 | 0.093 ± 0.005 | 21,743 |
| pdp-9-seed-1 / matrix-reuse | 5.736 ± 0.017 | 6.774 ± 0.090 | 12,951,164 |
| pdp-9-seed-1 / matrix-quotient | 0.063 ± 0.003 | 1.067 ± 0.025 | 12,484,271 |
| pdp-9-seed-4 / matrix-reuse | 3.872 ± 0.044 | 4.715 ± 0.068 | 11,140,966 |
| pdp-9-seed-4 / matrix-quotient | 0.060 ± 0.001 | 0.882 ± 0.020 | 10,830,687 |
| planted-dense-mq-12 / matrix-reuse | 0.100 ± 0.003 | 3.394 ± 0.054 | 32,315,820 |
| planted-dense-mq-12 / matrix-quotient | 0.102 ± 0.004 | 3.303 ± 0.102 | 32,315,832 |

For nine-variable seed 4, the candidate map constructs 506 nonstandard monomial
images, accumulates 152 tail images and then performs 3,029 generator lookups.
Its six-dimensional values occupy 4,096 bytes. The separate map method charges
11,353 units including planning, initialization, reducer searches, Boolean
products, leading-term checks and accumulation. These are declared conservative
software charges, not calibrated hardware operations or a cross-algorithm
instruction ratio. The independent Python model verifies their exact values.

The map needs only 512 value bytes on six-variable controls. MQ12 has 181 input
terms versus a 4,096-monomial universe, so the density guard skips construction,
reserves no map payload, and charges only 12 planning units before ordinary
membership. The payload cap excludes allocator metadata, the existing decoded
input/basis sets and temporary hash products; process peak RSS is retained
separately. Construction, abandoned work and fallback all stay inside the query.

The F4 and matrix bases are equivalent but can have different reducer order,
so intermediate normal-form work counts differ. The model uses the exact
published basis order. Proofs, producer traces, liveness, ownership counts,
completed bases and assignments remain paired and independently checked.

## Correctness and evidence

Eight unit-test groups pass in optimized and UBSan configurations. They cover
random exact ideals under all reclamation policies and phase schedules,
non-Gröbner candidate bases whose own generators still map to zero, forged
proofs, empty/inconsistent ideals, repeated inputs, wide equation limbs,
concurrent fresh coefficients and proof lifetime. Boundary controls include
64 versus 65 standard monomials, exact map-byte boundaries, every small work
budget, proof-term limits, recovery after failure and sparse fallback at
13, 32 and 64 variables. No shift by 64 or allocation beyond the map cap is used.

- 104 control cells: 44 algebra certificates, 40 solved PDP controls, 60
  inconclusive outcomes, zero process failures, 52 exact pairs, 44 lifetime
  checks, 28 equal-basis comparisons and 20 retained producer fallbacks.
- 260 diagnostic cells including 52 warmups: 110 algebra certificates,
  100 solved PDP controls, 150 inconclusive outcomes, zero process failures,
  130 exact pairs and 50 retained producer fallbacks.
- All 48 artifact-corruption controls rejected, including altered map policy,
  dimension, work, payload size and lookup counts.
- Seventeen synthetic publication-admission corruptions rejected. Two mutate
  all matching worker/report counters coherently; the independent mathematical
  operation model rejects them. These are auditor controls, not remote CI runs.

The native-free audit independently checks ideal equality, Boolean Gröbner
completion, exact proofs and producer correspondence, equations/curve replay,
resource accounting and all source/resource hashes. Linux/macOS CI must rebuild
and audit the final publication commit before merge. The map remains opt-in.

A next extension could discover a bounded staircase and reduce only the
input-support closure, avoiding full-universe enumeration in larger rings.
That requires new construction/work bounds and fallback controls. For the
current successful nine-variable matrix controls, producer and extraction costs
now deserve renewed profiling. MQ12 still spends most checker time in derivation
replay. None of these observations establishes GPU acceleration, natural relation
yield, generic F4/F5 leadership or a new asymptotic F6 algorithm.
