# Trace-only last-pair relaxation accepts every N41 first-pair sum

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

The [N131 transfer check](transfer.json) verifies that every basis vector
of `W18=span(t,...,t^18)` has zero reciprocal trace on the exact challenge
field. The public raw target preimages have traces `[0,1,0,1]`, leaving
indices `0` and `2` under the already established trace gate. For either
admissible preimage, the same additive argument makes a trace-only fourth
output automatic from three trace-zero pair outputs. This is an exact
necessary-condition statement; it does not enumerate N131 pair outputs.

## Next method gate

A useful early constraint must retain more than trace and subgroup
membership for the unresolved fourth pair. The next candidate is a sound
blockwise eliminant that keeps the fourth pair's sparse seed sum/product
relation with its reciprocal output and substitutes the target-conditioned
required output from the other partial sums. Its N41 test should count
rejected partial states before constructing complete fourth-pair witnesses,
then compare the charged cost with the indexed join. The complete IC method
remains a design proposal with `candidate_id: null`.
