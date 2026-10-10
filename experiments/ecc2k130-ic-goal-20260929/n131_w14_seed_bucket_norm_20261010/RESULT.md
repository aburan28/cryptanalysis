# Exact N131 W14 seed-bucket norm isolates polynomial GCD as the cost center

The source-filtered `s=t` W14 bucket now has **4,124 exact raw pair-output
x coordinates** at each of Frobenius rotations 26 and 39. A balanced
product-of-roots norm checked the two frozen degree-131 proposed outputs
within one worker, 600 seconds, and 4 GiB: the trace-zero control gave
GCD degree zero; the constructed four-atom output gave its independently
audited degree-one witness. The complete two-query producer took
261.418 seconds and peaked at 1,126,039,552 bytes process RSS. This
identifies the next native arithmetic target: polynomial GCD consumed
106.588 and 111.304 seconds of the two output-query intervals.

The exact curve is `y²+xy=x³+1` over
`GF(2)[t]/(t^131+t^13+t²+t+1)`, with subgroup order
`680564733841876926932320129493409985129` and curve ID
`EC1N131Ckb1heb5f1998f20b`. The source is the audited W14 rational-mask
set; only pairs with distinct folded columns and mask XOR seed `1` enter
the bucket. The [root builder](prepare.py) enumerated **2,062** such
unordered mask pairs, solved their exact pair-output quadratics, batched
all 4,124 field inversions into one, and applied the two frozen Frobenius
rotations. The [root receipt](roots.json) retains the sorted, distinct
raw x-coordinate lists and source hashes. Root construction took
2.015 seconds and 254,902,272 bytes peak self RSS, before any proposed
output was supplied.

For known raw output x coordinate `q`, the [query](query.py) forms

`S3(X,b,q) = (X+q)^2 b^2 + q X b + (q X)^2 + 1`

for every right-bucket root `b`, multiplies those factors with a balanced
tree, reduces modulo the reusable left-bucket polynomial, and extracts
the roots of their GCD. The left and right degree-4,124 bucket
polynomials took 12.152 seconds of target-independent setup in the query
process. The [frozen protocol](query_protocol.json) fixes the source,
positive output, trace-zero control, order, resource limits, and timing
boundary before the measured query. The checked [Sage runtime](sage_runtime_info.json)
was saved before both producer runs.

| Exact N131 proposed output | Factor construction | Balanced product + remainder | GCD | Root extraction | Target query | GCD degree |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Trace-zero control | 5.726 s | 11.333 s | **106.588 s** | 0.003 s | **123.651 s** | 0 |
| Constructed positive | 3.949 s | 10.271 s | **111.304 s** | 0.007 s | **125.533 s** | 1 |

The [query receipt](query_result.json) contains exact nanosecond phases,
root values, complete producer wall, source identities, and peak RSS. The
[receipt verifier](verify.py) checks those against the prior
[independent checked-Sage group replay](../n131_w14_mixed_rotation_fouratom_join_20261010/sage_audit.json),
which reconstructed the constructed four-point sum and rejected the
trace-zero control. The host has no isolation receipt, so wall timings
are algorithmic stage diagnostics. This experiment has `target_count: 0`
and `candidate_id: null`: its input is a proposed four-atom output, not
the published public point.

The left bucket is already stored as its 4,124 known roots. A complete
root test can therefore evaluate the target-dependent norm at those
roots using a reusable subproduct/remainder tree and compare zero values,
avoiding the observed degree-4,124 GCD. The next frozen N131 gate should
measure that exact replacement on both saved outputs, including tree
setup, every failed probe, memory, and source-matched decisions. The
larger IC goal still requires a target-guided generator of such outputs
while multiple pair blocks remain free, followed by ordinary relation
yield, useful rank, factor logs, fresh-target recovery, and matched rho.
