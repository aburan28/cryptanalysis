# Exact reusable F6 boundary bitplanes

The four-summand S3 chain over GF(2^9) has a 12-variable boundary after
target-independent elimination. Precomputing exact Boolean truth planes for
its affine target equations reduces a fresh target query to bitwise XOR and
intersection, followed by witness reconstruction and independent equation and
curve-point checks. This is an opt-in bounded-width specialization; default
routing is unchanged.

The source was frozen at `7cef9f3ed08a4404a5252bb15e43160f6553a578`
before the final build and measurements. The candidate compiled at `-O3`
and with undefined-behavior sanitization. Random systems with 1–6 variables
passed 1,140 exhaustive target calls across both builds. All 512 frozen
abscissae matched the independent S3 reference and the packed-ANF baseline:
2 satisfiable assignments passed equation and point replay, and 510 queries
were unsatisfiable. The initial randomized test failed because its oracle
treated repeated ANF monomials as a set; the oracle was corrected to cancel
terms modulo two before the source freeze. The native algorithm did not
change in that correction.

The final local macOS arm64 panel used one warmup and six alternating,
paired repetitions per target. Each timed interval includes target-specific
native solve and independent equation/point verification where applicable;
target-independent setup is separate. Median times and paired median ratios
are shown below. All 84 executions completed and passed their status and
answer checks. These timings are exploratory because this host has no
auditable exclusive-CPU isolation receipt.

| Target abscissa | Status | Packed query, µs | Bitplane query, µs | Median paired bitplane/packed | Paired ratio range |
| ---: | --- | ---: | ---: | ---: | ---: |
| 0 | satisfiable | 217.667 | 102.562 | 0.4881 | 0.4271–0.5775 |
| 1 | satisfiable | 236.709 | 118.291 | 0.5077 | 0.4466–1.0468 |
| 2 | unsatisfiable | 121.396 | 6.188 | 0.0495 | 0.0463–0.0713 |
| 9 | unsatisfiable | 158.020 | 6.062 | 0.0344 | 0.0302–0.0455 |
| 100 | unsatisfiable | 168.542 | 6.458 | 0.0390 | 0.0312–0.0696 |
| 511 | unsatisfiable | 171.333 | 6.417 | 0.0335 | 0.0308–0.1712 |

The exact bitplane layer stores 5,760 64-bit words (46,080 bytes) for 90
target-zero and target-delta truth planes and enumerates 4,096 boundary
assignments and 368,640 template evaluations at setup. The final panel
recorded 82.817 ms of bitplane-index setup and 95.239 ms for the packed
reference setup. An earlier source-frozen panel, whose only subsequent source
change was a portable temporary-lock path, recorded 855.646 ms and 438.771
ms respectively. That large variation reinforces the exploratory status of
the local wall times. The full context and native static-elimination costs
are retained in both raw panel artifacts.

The exactness condition is explicit. Let `S` be the set of boundary assignments
with a valid static witness, and suppose each target equation has the form
`f_j(x,u) = a_j,0(x) + sum_k u_k a_j,k(x)` over GF(2), where `x` contains
only boundary variables. The setup stores the truth plane of each `a_j,k`
and the bitset of `S`. For a fresh target `u`, bitwise XOR gives exactly the
truth plane of `f_j(x,u)`; intersecting its complement for every `j` with
`S` therefore gives precisely the feasible boundary assignments. A selected
bit reconstructs the stored static witness, and the original equations and
curve point are checked again. This proves the returned satisfiable answer;
an empty intersection proves unsatisfiability under the stated static-witness
and affine-target preconditions.

For boundary width `b`, equation count `e`, target-bit count `t`, total
template monomial occurrences `L`, `R` residual static factors, and
`W = ceil(2^b/64)`, the current direct evaluator adds
`O((L+R) 2^b + teW)` setup operations and
`O((t+1)eW + W)` words beyond reusable static elimination and witnesses.
A fresh target uses at most `O(eW(1+popcount(u)))` word operations before
witness reconstruction and verification. The explicit caps are 16 boundary
variables and 31 target bits. A dense dynamic equation with support on all
`n` variables makes `b=n` for this layout, so its table grows as `2^n`;
a target term such as `u_0 u_1 x_0` violates the affine-target precondition.
These are concrete structural counterexamples to extending this bound to
general Gröbner basis computation, irrespective of degree of regularity.

Reproduce from this checkout with the predecessor builds in the workflow,
then run `build.py`, `test_bitplane.py`, `semantic_replay.py`, and `profile.py`
from this directory. The [build receipt](evidence/build-receipt.json),
[512-target replay](evidence/semantic-512.json.gz),
[final paired panel](evidence/complete-query-panel.json.gz), and
[earlier paired panel](evidence/initial-complete-query-panel.json.gz)
preserve source hashes, raw executions, failures, timings, and setup costs.
An isolated-host complete-query replay is the next measurement gate; scaling
the boundary width and adding a nonaffine target control are the next
structural gates.
