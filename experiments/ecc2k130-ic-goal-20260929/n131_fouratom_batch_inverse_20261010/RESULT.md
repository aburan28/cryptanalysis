# One batched field inversion replaces 8,192 inversions in the N131 four-atom oracle

The fixed-seed, same-seed four-atom resultant scan now normalizes all
8,192 nonconstant degree-eight specializations with **one batched field
inversion**. The baseline performs one inversion for each specialization.
The batched method first multiplies their leading coefficients into a
prefix product, inverts the total once, and traverses the products backward
to recover every individual inverse. It retains the exact resultant,
linearized product space, polynomial remainders, and GCD decisions. On
the archived N41 positive and control inputs and eight interleaved N131
runs, it returned the same complete output and GCD coefficients as a
byte-identical baseline source compiled with the same flags. The
[audit](audit.json) binds the inputs, source and binary hashes, raw receipts,
prior independent Sage group replay, and all decisions.

This is an implementation improvement to a proposed-output inverse. Its
full oracle times vary across repetitions on an unisolated host, and the
batch run spends **91.5–94.7%** of its query interval in polynomial GCD
work. The measured panel therefore identifies the GCD as the next native
cost center; it does not establish an isolated wall-time speedup or generate
target-conditioned outputs.

## Exact arithmetic and matched panel

The degree-131 field is `GF(2)[t]/(t^131+t^13+t²+t+1)` on
`EC1N131Ckb1heb5f1998f20b`. The four-atom oracle takes a proposed raw
sum reciprocal coordinate `z` and a fixed source seed sum `s=t` in W14.
For each product `p` in the **13-dimensional** space
`V_s={w²+sw : w in W14}`, it specializes the previously
[derived degree-eight resultant](../n131_w14_coupled_fouratom_inverse_20261010/RESULT.md)
as a polynomial in the other pair product `q`, then intersects its roots
with the exact product-space polynomial. The positive case is a constructed
four-atom output with two algebraic product hits; the independent
trace-zero control has none. The [prior Sage audit](../n131_w14_coupled_fouratom_inverse_20261010/sage_audit.json)
replays the exact product roots and curve-point sums.

The [protocol](protocol.json) fixes both source and binary hashes, the
archived inputs, one worker, a 4 GiB RSS cap, 120 seconds per run, and an
interleaved order before the N131 panel. The [baseline source](baseline.cpp)
is byte-for-byte the earlier native implementation. Both variants were
built with Apple clang 17.0.0 using `c++ -O3 -std=c++17 -DNDEBUG -Wall -Wextra`.
The checked [Sage runtime receipt](sage_runtime_info.json) precedes the
measured runs. All N41 controls and N131 rows completed with exact matching
hits and no resource-cap failure.

| N131 proposed output | Repetition | Baseline complete scan | Batch complete scan | Baseline / batch query ratio | Batch GCD share |
| --- | ---: | ---: | ---: | ---: | ---: |
| Constructed positive | 1 | 3.063870 s | 2.197565 s | 1.394 | 91.5% |
| Constructed positive | 2 | 3.028484 s | 3.141948 s | 0.964 | 94.7% |
| Trace-zero control | 1 | 2.219074 s | 2.119085 s | 1.047 | 91.8% |
| Trace-zero control | 2 | 3.347626 s | 2.912329 s | 1.149 | 94.4% |

The intervals are producer query times, including resultant evaluation,
normalization, all polynomial GCDs, and hit output, with process launch
and input loading outside the interval. Parent wall and sampled RSS are
saved for every row under [runs](runs). Batch normalization itself used
0.006–0.007 seconds in these four N131 runs. The baseline and batch
queries were interleaved; host isolation was not established, and four
paired observations are insufficient for a controlled CPU speedup claim.
The prior archived native binary used a different build receipt, so its
7.5–9.7-second timings are kept separate from this source-matched panel.

The algebraic oracle still requires a proposed four-atom output. A
target-conditioned five-pair method must derive and reject whole block
output families under the public target equation before calling this
inverse. Its first gate is an unpinned N41 public relation with independent
group and folded-column replay, then an N131 work/RSS projection covering
all proposal and GCD costs under one worker, 600 seconds, and 4 GiB.
Relation rank, factor-base logs, target recovery, and the matched
single-target rho comparison remain the full IC gates. This component has
`candidate_id: null`.
