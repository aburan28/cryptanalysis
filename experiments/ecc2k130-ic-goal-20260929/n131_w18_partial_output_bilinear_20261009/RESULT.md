# Exact bilinear W18 pair equation with 48 output bits free

**The complete seed-product bilinear equation preserves the independently
verified N131 W18 pair, but a generic native-XOR SAT encoding did not decide
either partially known output within its 12-second solver cap.** The pinned
positive model was found in 0.038 seconds of charged stage time and passed
every saved CNF and XOR row. With the same 48 low coordinate bits free, both
the positive pair output and a frozen uniform field control returned
`INDETERMINATE`. This identifies the missing operation as efficient
propagation through the seed-product relation, rather than another reduction
of its circuit size.

## Exact equation and frozen controls

The input is the previously [independently replayed W18 pair
oracle](../n131_w18_full_width_pair_oracle/independent_sage_replay.json) on
the binary curve `y²+xy=x³+1` over
`GF(2)[t]/(t^131+t^13+t²+t+1)`. Its unrotated W18 seeds are
`w_1,w_2 ∈ span(t,...,t^18)`. Write `s=w_1+w_2`, let `H(s)` be the
half-trace preimage, let `epsilon` select the raw lift parity, and let
`z=1/(x(P_1+P_2)+1)`. The [circuit](run.py) enforces all 131 bits of

`z² = H(s)² + epsilon + (z²+z)w_1w_2`.

The two 18-bit seed vectors and the parity bit remain variables. In the
partial cases, low bits `0..47` of `z` are variables and the remaining 83
bits are fixed from the saved output. The positive is the first exact raw
pair in the prior oracle; the negative is the first seeded uniform field
control in the earlier [affine gate receipt](../n131_w18_partial_output_linear_gate.json).
The pinned case fixes both seeds, the parity, and all 48 remaining output
bits. This formula retains the bilinear relation discarded by the earlier
affine relaxation. It does not impose the separate leaf-rationality and
distinct-column conditions, so an UNSAT result would be a sound pair
rejection while a SAT result would still require exact leaf checks.

The [protocol](protocol.json) bound eleven source, input, binary, and checked
[Sage runtime](sage_runtime_info.json) hashes before the measured cases,
including the full pair oracle and its independent replay. Proposal
`Q20261009191200` has `candidate_id: null` and `target_count: 0`; this is a
local pair-gate diagnostic, not a public-target IC query. Each case used
one CryptoMiniSat worker, a 12-second internal solver cap, a 15-second
parent cap, and a 4-GiB RSS guard.

## Capped results and independent replay

| Case | Terminal status | Variables / AND gates | CNF / native XOR | Charged stage | Peak sampled solver RSS |
| --- | --- | ---: | ---: | ---: | ---: |
| [Pinned positive](pinned_positive/result.json) | `SAT` | 3,286 / 2,669 | 8,223 / 532 | 0.038482166 s | 4,407,296 B |
| [Positive, 48 bits free](positive_partial/result.json) | `INDETERMINATE` | 3,286 / 2,669 | 8,138 / 532 | 12.141934542 s | 56,279,040 B |
| [Field control, 48 bits free](field_control_partial/result.json) | `INDETERMINATE` | 3,344 / 2,704 | 8,243 / 555 | 12.117577208 s | 66,535,424 B |

The [run receipt](result.json) records exclusive formula-build, solver,
terminal-check, and interval-overhead nanoseconds for each case; those phases
sum to the charged interval. Field setup and positive-equation preflight took
39,176,375 ns outside these intervals. The raw XCNFs, stdout, stderr,
process return codes, and hashes are retained in each case directory. The
two unpinned outputs contain terminal `s INDETERMINATE` lines and no models;
they are censored decisions, not pair-membership verdicts.

The [independent audit](audit.json), launched through the checked Sage
runtime, reconstructed the positive raw curve addition and phi coordinate,
verified the half-trace identity and complete bilinear equation, and
evaluated the pinned solver model against **all 8,223 CNF clauses and 532
native XOR rows**. It separately checked the saved terminal streams,
formula hashes, source hashes, resource caps, and phase sums. These local
CPU times are solver diagnostics without host-isolation evidence.

## Next exact propagation test

The fixed-sum product map `L_s(w)=w²+sw` has an exact rank-17 image
for nonzero W18 seed sums `s`. A next solver should expose that image as a
theory constraint: when a target-linked partial assignment narrows `s` and
`z`, test consistency of the resulting linear map and learn a conflict over
the assigned bits while multiple pair leaves remain free. Its first gate
is an unpinned N41 public relation with measured pre-leaf branch rejection;
an N131 query requires a source-bound whole-search rate and memory estimate
inside 600 seconds and 4 GiB. The generic SAT pair gate here is too slow to
serve as that propagator at 48 unknown bits.
