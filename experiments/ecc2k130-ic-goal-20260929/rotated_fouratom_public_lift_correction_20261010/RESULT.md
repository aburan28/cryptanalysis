# Correct public raw lifts for the rotated four-atom resultant

The public-target raw lifts have now been expressed in the **`1/x`
coordinate required by the rotated four-atom resultant**. In both N41
and N131, genuine lift indices 0 and 1 have trace-zero `1/x` and give
two 13-term quartic factors under the frozen same-seed specialization;
indices 2 and 3 have trace-one `1/x` and remained one degree-eight
factor in the exact finite-field calculations. The previously verified
N41 twelve-point public relation sums to **raw lift 1**. Its three
four-atom block outputs each have trace-zero `1/x`, giving a precise
positive assignment target for the next joint solver.

## Coordinate correction

The archived N131 [target preimage producer]
(../n131_fixed_seed_eight_pair_circuit_20261010/target_preimages.py)
stores `u=1/(x+1)` for a transformed S3 circuit. The rotated
four-atom [resultant](../n131_w15_rotated_fouratom_inverse_20261010/RESULT.md)
uses `z=1/x`. The earlier
[factorization torsion screen](../rotated_fouratom_factorization_20261010/torsion_result.json)
fed all four archived `u` values to `H` as if they were `z`. Those four
polynomial factorizations remain valid evaluations at their recorded
field elements, but their `public_raw_lift_*` labels do not describe
the corresponding public points in `H`'s coordinate. Its N41 `z+1`
rows likewise are field-XOR controls, not additions of the rational
order-two point in the `1/x` coordinate.

For the curve `y²+xy=x³+1`, adding the rational order-two point
`T₂=(0,1)` sends `x` to `1/x`. Thus the two coordinates transform as

`z_H(P+T₂)=1/z_H(P)`, while `u(P+T₂)=u(P)+1`.

The [corrected producer](correct.py) reconstructs all four raw lifts
of the N41 public subgroup point and replays all four archived N131
raw points. It checks `4R=Q` for every lift, computes both reciprocal
coordinates, and factors `H` at `z_H=1/x(R)`. The
[protocol](protocol.json) binds the source points, checked Sage runtime,
resultant, and earlier screen before execution. An
[independent integer-field audit](audit_result.json) separately checks
each point on the curve, its fourfold projection, both coordinate
inversions, the order-two translation, and the archived N131 `u` values.

| Field | Corrected raw lift indices | `Tr(1/x)` | Fixed-seed `H` factors |
| --- | --- | --- | --- |
| N41 | 0, 1 | 0 | two `(4,4)` factors, 13 terms each |
| N41 | 2, 3 | 1 | one `(8,8)` factor, 37 terms |
| N131 | 0, 1 | 0 | two `(4,4)` factors, 13 terms each |
| N131 | 2, 3 | 1 | one `(8,8)` factor, 37 terms |

The earlier **universal Artin–Schreier factor identity**, its independent
GF(2) product audit, and the N131 fixed-output native root replay use
their stated coordinates and remain valid. The earlier claim that raw
public lift indices 0 and 2 split is superseded by the table above.
The finite-field irreducibility observations are specific to these
inputs; the universal identity proves the trace-zero split.

## Exact source-character reduction to two lifts

For this curve, define `χ(P)=Tr(x(P))` for finite points and `χ(O)=0`.
The characteristic-two addition law gives
`x(P+Q)=λ²+λ+x(P)+x(Q)` for distinct affine inputs; doubling has
`x(2P)=λ²+λ`. Taking traces proves that `χ` is a group homomorphism.
For every rational point with `x≠0`, dividing the curve equation by
`x²` shows `Tr(x)=Tr(1/x)`. Each raw diagonal source point has
`x=1/w`, where `w` lies in `span(t,...,t^d)` for `d=6` or `15`.
Every one of those basis elements has trace zero in its stated field.
Consequently every permitted raw source sum has `χ=0`.

The [source-trace certificate](source_trace_result.json) checks every
W6 and W15 basis trace, the 32 archived rational W6 masks, the
archived W15 trace support, and the corrected raw-lift characters.
The existing [W15 cofactor-class study]
(../n131_w15_cofactor_class_gate_20261010/RESULT.md) independently
established that the raw W15 source lies in `2E`. This correction
binds that known source property to the correct four public raw lifts:
**indices 2 and 3 cannot be sums of these source points**. The public
joint search needs lift indices 0 and 1, both of which admit the
two-quartic block representation. The source-character gate removes
half the raw target choices before any product-family search; it does
not by itself reduce the constrained-block Cartesian work enough for
an N131 relation.

## N41 public-relation control and next gate

The [known-row replay](lift_result.json) independently rebuilt all
twelve raw source points from the frozen masks and signs, checked their
cofactor-four projected leaves, summed the raw points, and matched the
sum to corrected public raw lift **1**. Its first free four-atom block
and the two shared-seed constrained blocks all have trace-zero
reciprocal outputs. This is a correctness control; the next solver's
public query must leave those source masks, signs, block outputs, and
lift choice unpinned.

The target-conditioned joint circuit should use `z_H=1/x(R_j)` for raw
lifts `j=0,1`, with the source-character certificate as its exclusion
rule for `j=2,3`. Both retained lifts satisfy the Artin–Schreier
condition for the quartic blocks. First measure unpinned N41 family
rejection and independently
replay a relation. A source-bound projection of the *complete* algorithm
must then fit one N131 worker, 600 seconds, and 4 GiB before promotion.
The complete IC configuration still has `candidate_id: null`.
