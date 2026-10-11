# Trace-only last-pair relaxation accepts every N41 first-pair sum

An exact **sparse-product linear gate** now rejects all 63 selected
target-derived fourth outputs that pass the trace-only relaxation, while
accepting all 1,956 exact fourth-pair outputs. The gate retains the
rotation-30 W6 seed-sum and product spans in the halftrace-cubic pair
equation. Its [frozen corrected result](linear_result_v2.json) and
[independent Sage matrix audit](linear_audit_v2.json) establish an exact
necessary rejection test at the point where the fourth output is known.

Keeping three exact source-pair outputs but replacing the fourth pair's
factor-base image by its trace-zero condition accepts **all 63** possible
first-pair seed sums on the frozen N41 public point. Restoring exact
fourth-pair membership and the eight-column rule leaves **11** sums. This
isolates the constraint
that a target-conditioned early gate must retain: the fourth pair's actual
source-image algebra, coupled to the target, before enumerating complete
four-pair combinations.

## Exact relaxation and result

The [protocol](protocol.json) fixes `GF(2)[t]/(t^41+t^3+1)`, curve
`y^2+xy=x^3+1`, subgroup order `549756390943`, the transported public point
`(920359962848,755404565011)`, the W6 source windows at rotations
`(0,0,10,10,20,20,30,30)`, actual base `B=256`, and 26 folded columns.
The first three pair outputs come from their exact 1,956-entry canonical
pair lists, with six distinct columns. The required fourth output is set
by the target group equation and accepted if it is nonexceptional, belongs
to the odd subgroup, and has trace-zero reciprocal coordinate. The two
middle points must also be nonexceptional. This relaxes only the fourth
pair's membership in its 1,956-entry exact image.

| First-pair support on the same public target | Accepted seed sums |
| --- | ---: |
| Four exact pair images and eight distinct columns, [complete fiber](../n41_target_projection_20261011/RESULT.md) | 11 / 63 |
| Three exact pair images, six distinct columns, fourth trace-only | **63 / 63** |

The checked-Sage [producer](relaxation_sage.py) found one completion for
each first-pair sum with 63 candidate checks. Its [receipt](result.json)
records 0.485935 s to build the four exact pair lists and 0.227282 s for
the target-dependent relaxed completion search, exploratory on the local
host. The [independent checked-Sage audit](audit.json) reconstructed all
63 completions from the frozen point input, verified the three exact pairs,
six distinct columns, target group sum, odd-subgroup membership, reciprocal
traces, and nonexceptional tree nodes. None of the 63 selected relaxed
fourth outputs lies in the exact fourth-pair sum set. This last count
describes the selected completions, not all possible choices for each sum.

## Why the trace gate is vacuous here

For nonexceptional curve points, set `chi(P)=Tr(1/x(P))`. The reciprocal S3
trace identity gives `chi(P+Q)=chi(P)+chi(Q)` whenever the coordinates in
that identity are defined. Therefore, if a target preimage `U` and three
pair outputs `A,B,C` have `chi=0`, the required fourth output
`D=U-A-B-C` also has `chi=0` when nonexceptional. The target equation
itself supplies the fourth trace condition; it cannot distinguish first
pair candidates. The N41 computation explicitly covers the exceptional
coordinate checks for all 63 seed sums in this frozen source policy.

The [corrected N131 transfer check](transfer_corrected.json) verifies that
every basis vector of `W18=span(t,...,t^18)` has zero trace on the exact
challenge field. With the S3 circuit's standard reciprocal `z=1/x`, the four
public raw preimages have traces **`[0,0,1,1]`**, leaving indices **`0,1`**.
The independent field and group replay checks their point coordinates and
quadrupling to the public target. For either admissible preimage, the same
additive argument makes a trace-only fourth output automatic from three
trace-zero pair outputs. The earlier [archived transfer](transfer.json)
used the input file's `1/(x+1)` coordinate and therefore reported a
different, inapplicable split `[0,1,0,1]` and indices `0,2`. The N41
relaxation and sparse-product gate measurements above are unaffected.

## Sparse-product linear gate at a known fourth output

For a proposed reciprocal fourth output `z`, let `s` lie in the rotated
six-dimensional source-sum space, `p` in its rotated 11-dimensional
product span, and `epsilon` be one branch bit. A genuine pair satisfies
`p*z + H((s+z)^2) + epsilon = 0`, where `H` is the field halftrace.
For fixed `z`, this is a binary linear system with 18 columns and 41
coordinate rows. Inconsistency safely rejects the output before solving
whether `p` factors into two rational source seeds.

The corrected frozen [protocol](linear_protocol_v2.json) uses the fourth
window's Frobenius rotation **30**. Its checked-Sage [producer](linear_last_pair_sage_v2.py)
accepted **1,956/1,956** exact fourth-pair outputs and rejected **63/63**
selected target-derived raw outputs, one from each first-pair seed-sum
family. The [independent audit](linear_audit_v2.json) rebuilt all 63
negative linear systems with Sage's `GF(2)` matrix rank, matched every
decision and rank, and checked the known public-row fourth pair as a
positive. The exploratory producer charged 44.375 s for the 1,956-positive
scan, 0.0064 s for 63 target-candidate constructions after raw pair lists
were ready, and 1.502 s for the 63 linear-gate calls. These are Python/Sage
stage costs, not a native or end-to-end timing comparison.

The first frozen version used unrotated W6/product columns for the fourth
window. Its positive control failed; the [failure receipt](linear_v1_failure.json)
records `PRODUCER_FAILURE_WRONG_ROTATION_BASIS`. The known fourth-pair
output fails that unrotated system and passes the corrected rotation-30
system. The corrected version has separate frozen sources and result files.

## Next method gate

The linear gate has the required soundness and strong rejection on the
selected N41 target-derived outputs. It currently needs all three other
pair outputs fixed to compute `z`; enumerating those triples would miss
the N131 resource goal. The next candidate must eliminate or compress an
unresolved third pair jointly with the target and the fourth pair's
rotated sparse-product equation. Its N41 test should count rejected
*families* before completing the third pair, preserve every exact row,
and compare charged construction plus probe cost with the indexed join.
The complete IC method remains a design proposal with `candidate_id: null`.
