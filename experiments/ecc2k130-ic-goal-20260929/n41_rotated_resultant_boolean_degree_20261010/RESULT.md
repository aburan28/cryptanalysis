# Exact Boolean support of the rotated four-atom resultant

On the frozen N41 product spaces, the 266-term rotated four-atom resultant
has Boolean degree **six** and **656 nonzero field coefficients** for each of
two fixed proposed outputs. Every allowable mixed monomial appears: the
only absent terms under the bidegree-three ceiling are the 20 pure cubic
monomials. An independent tensor-coefficient construction reproduced both
1,024-coefficient SHA-256 digests. This identifies a compact *bivariate
power circuit* as the useful representation for a joint solver; expanding
the block condition into Boolean ANF does not create sparse equations on
this control.

## Exact method and input

The [frozen protocol](protocol.json) binds the [direct evaluator](run.py),
the checked [266-term resultant](../n131_w15_rotated_fouratom_inverse_20261010/resultant.json),
and the archived N41 public-relation block before evaluation. The field is
`GF(2)[t]/(t^41+t^3+1)`, the W6 seed mask is 4 (field element 8), and the
two pair rotations are 10 and 15. The product image for that seed is a
five-dimensional binary space with basis `[20,36,384,1152,4608]`; each
rotated side has 32 states. The known block output is
`z=1413738195736`; the separately fixed rejection input is `z=3`.

For each output, the evaluator computes `H(a,b,P,Q,z)` at all 1,024
ordered product pairs and applies an exact field-valued Möbius transform
over the ten product-basis bits. The known output has exactly one algebraic
product pair, `(289314015996,1100774207418)`, matching the previously
checked source witness. The rejection input has zero product pairs. The
first attempt used the host's Python 3.9 default and stopped at
`int.bit_count`; the unchanged frozen source then ran under Python 3.11.

| Proposed output | Product-pair zeros | Boolean degree | Nonzero ANF coefficients | Coefficient digest |
| --- | ---: | ---: | ---: | --- |
| Known N41 relation block | 1 / 1,024 | 6 | 656 / 1,024 | `d0ae0d7fe5949471c5a14343205607216a6e365696ea8b50a3ca216a26c64ab3` |
| Fixed field control | 0 / 1,024 | 6 | 656 / 1,024 | `d8fcef8e0bd43f260554b6e83e6f54f4a55e8037bc80b9251e26d6b28078ea45` |

Both degree histograms are `0:1, 1:10, 2:45, 3:100, 4:200,
5:200, 6:100`. The known-output and control coefficient values differ,
but their supports have the same full mixed-monomial pattern. The
[independent audit](audit.py) assembled the coefficient vector from
separate univariate power ANFs and tensor products, instead of evaluating
the full resultant 1,024 times. Its [receipt](audit_result.json) matches
both exact digests and histograms. The direct [result](result.json)
records 12.535 seconds of exploratory process time for both cases together
on an unisolated host; this is an algebraic diagnostic, not a CPU speedup
comparison. The declared 120-second and 4-GiB limits were not enforced by
the launcher, so the receipt establishes completion and correctness but
does not certify peak RSS.

## Source-bound N131 implication

Every resultant exponent in either product variable has binary weight at
most three. For a fixed seed and output, its ANF therefore has bidegree
at most `(3,3)` in the two product-basis bit groups. When either product
exponent is zero, the other has binary weight at most two, so pure cubic
monomials vanish identically. The N41 source has five bits per product;
this gives at most `(1+5+10+10)^2-2*10 = 656` terms, and both controls
attain that bound. The N131 W15 source has 14 bits per product. Its exact
symbolic support ceiling is

`(1+14+91+364)^2 - 2*364 = 220172` field-valued Boolean monomials.

That number is a support ceiling, not a measured N131 expansion count or
solver cost. The 266-term bivariate representation remains substantially
smaller and preserves the product-space structure. The next joint-search
test should keep both constrained four-atom blocks, their seeds, and the
public-target S3 links in this factored representation; it should measure
early family rejection on the unpinned N41 public point before an N131
worker-cap projection. The complete IC candidate remains a design proposal
with `candidate_id: null` until factor-base, relation, linear-algebra, and
target-recovery stages are specified.
