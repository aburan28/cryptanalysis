# Exact W24 base cardinality on the ECC2K-130 degree-263 route

This deterministic census will enumerate every nonzero mask in the
24-dimensional trace-zero space `W24 = span(t^j + Tr(t^j), 1 <= j <= 24)`
over `GF(2^131)` with modulus `t^131+t^13+t^2+t+1`. It will compare the
Koblitz source and the verified first degree-263 descendant on the **same**
`w` values. The route manifest, field, curve IDs, and normalized descendant
coefficient are pinned in [CONFIG.json](CONFIG.json). There are no selected
targets, sampled relation queries, or timing-ratio claims in this census.

For `y^2+xy=x^3+b`, let `alpha^4=b`, `w=u^2+u != 0`, and
`x=alpha(1+1/u)`. A rational lift exists exactly when
`Tr(alpha/w)=0`. Its two `u` roots give points differing by the rational
order-two point; after multiplication by four they represent one signed
subgroup pair. The source uses `alpha=1`; the descendant uses the exact
`alpha` derived from its route's Weierstrass coefficients by the checked
normalization in the existing W-screen.

**New duplicate rule to check.** The rational order-four point is
`T4=(alpha,alpha^2)`. Translation by `T4` sends `w` to `alpha/w`. To see
this, put `y=x*z` and `A=u(u+1)=w`. The addition law gives
`x(P+T4)+alpha=A*z+alpha*u^2`. Replacing `z` by `z+1` gives the other
sign choice, and the product of these two denominators is `alpha*A`.
The corresponding `u' = alpha/(x(P+T4)+alpha)` values differ by one,
so their product, and hence `u'^2+u'`, is `alpha/A`. Since `[4]` has the
four rational torsion points as its kernel on these curves, two admissible
`w` values yield the same signed projected subgroup point precisely when
they are equal or related by this reciprocal involution. The independent
Sage replay must check the full point law and this equivalence before the
count is accepted.

The producer will compute all inverses in bounded batches. For each curve
it will retain the number `R` of rational `w` values, the number `P` of
two-element reciprocal pairs wholly inside `W24`, and any fixed points.
The exact sign-folded column count is `C=R-P`, and the actual number of
distinct nonidentity subgroup points before sign folding is `B=2C`.
It will digest the ascending list of canonical mask representatives and
record the exact source/input hashes, compiler/backend, elapsed time,
memory peak, and any failure. Both curves must have `Tr(alpha)=1`, no
fixed rational reciprocal point, and subgroup cofactor four; otherwise
the count is rejected pending a revised proof.

An independent Sage verifier will exhaust all masks at small dimensions,
check each full-width sampled representative using curve points and
`T4`, and independently rederive the exact `R`, `P`, `C`, and `B` from
the producer's canonical mask streams. The full census is repeated with
two batch sizes and compared byte for byte. The two native runs share
field code, so the Sage controls remain necessary. The checked repository
`sage` launcher and saved `--runtime-info` receipt are mandatory for
every Sage verification job.

This is an exact **factor-base geometry** gate. It does not time or solve
a natural point decomposition, collect independent relations, construct
the final matrix, descend a target, recover a logarithm, or compare rho.
`candidate_id`, natural PDP yield, rank, online/cold IC costs, and speedup
remain `null`. A `B` at or above the already derived W24/m6 1% necessary
threshold of 4,121,293 only admits the next ordinary-query PDP test; it
does not predict its hit rate or cost. A smaller `B` rejects this W24/m6
policy at that one-shot uniform-target threshold.
