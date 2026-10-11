# Q20261010173300: torsion-invariant t-coordinate gate

On the same Koblitz curve `y²+xy=x³+1`, define `t(P)=x/(x²+x+1)` for affine
points. The denominator has no root in the odd-degree fields N53, N83, and
N131. The complete binary Edwards model with `d1=d2=1` is isomorphic to
this Weierstrass model; its coordinate `x_E+y_E` simplifies to this `t`.
The model is a coordinate change on the same curve, so record `ISO0`.

The binary Edwards three-point polynomial becomes

`f3(a,b,c) = c² + h(c²+c) + (a+b)²`, where
`h = ab(ab+a+b+1)`.

This follows from the general binary Edwards summation polynomial in
[Galbraith and Gebregiyorgis, 2014](https://eprint.iacr.org/2014/806.pdf)
after setting `d1=d2=1`. The source paper's general coefficient form is used
because search-engine extraction of its special-case display loses factors.
The implementation checks the polynomial against independently added curve
points, negation, 2-torsion translation, and Frobenius.

Freeze sources and the Q1419 exact curve/target protocol before measuring.
Measure one unfixed S3-link XCNF shape for N53, N83, and N131 against the
existing factored x link. Enumerate the exact N53 normal-basis `t`-weight≤3
base: every nonzero mask of weight 1, 2, or 3; solve the two-to-one x map,
lift to the curve, project by cofactor 428, and deduplicate signed-Frobenius
subgroup columns. Preserve counts, packed base digest, operation/timing
boundaries, and any exceptional values. Test 32 deterministic subgroup
triples on N53 and N83. No N83 or N131 `t` base count is inferred from the
N53 result.

This is proposal `Q20261010173300`, with `candidate_id: null`,
`run_id: null`, and `isogeny: "none"`. A useful solver comparison requires
an exact N83 `t` base, ordinary-query relation yield, rank novelty, and
charged downstream stages.
