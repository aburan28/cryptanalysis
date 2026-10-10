# Selector-weighted W24 leaf equations on fixed finite S3 controls

The [six-distinct-leaf control](../ecc2k130-263-distinct-s3-control-20261010/RESULT.md)
fixes the source and degree-263 descendant witnesses, exact targets, and twelve
solver cells. All eight one-coordinate releases reached the pinned bound. This
experiment changes only the Boolean implementation of the leaf inverse
equations, retaining the same six masks, four finite projective states, target
multiplexer, units, curve coefficients, and S3 circuits.

Let `s_j` be the 24 W24 selector bits, `b_j=t^(j+1)+Tr(t^(j+1))`, and
`h_j=halftrace(b_j)`. The existing leaf computes `w=sum_j s_j*b_j` and
`u=sum_j s_j*h_j`, then field-multiplies `w*z` and `u*(x+alpha)`. Bilinearity
over GF(2) gives the exact identities

`w*z = sum_j s_j*(b_j*z)` and
`u*(x+alpha) = sum_j s_j*(h_j*(x+alpha))`.

`wz_only` implements the first identity using a sparse monomial shift,
pentanomial reduction, and optional `+z` for each `b_j`; its second product
is the unchanged parent circuit. `both_products` also implements the second
identity using 24 exact constant-multiplication linear maps. Both variants
use the parent XCNF encoder. These identities hold for all selector and field
inputs, including zero selectors and values outside the curve.

Freeze this protocol, `CONFIG.json`, source, and auditor in a commit before
constructing variant formulas. Check the pinned parent hashes. For each
curve, compare parent and both variants on zero, full, all 24 singleton,
the six archived witness masks, and 32 seeded random masks with independently
specified 131-bit `x,z`. Require all 263 leaf equations to match direct field
arithmetic. Keep a JSON receipt with seed, cases, source hashes, and exact
status; a failure stops formula construction.

Construct one base XCNF for each variant and curve, archive it losslessly in
deterministic gzip, and retain its named input map, source hashes, size,
operation count, build time, and peak RSS. Derive the same six semantic unit
cells per curve as the parent, preserving exact full-XCNF hashes and deltas:
fixed positive and one-bit target-negative controls, then x0/z0/x5/z5 with
one 131-bit leaf coordinate free. Commit these complete inputs before the
first solver attempt. Run once each in the configuration order, using the
same CryptoMiniSat binary, one thread, 45/60 second internal/external caps
for fixed controls, 120/150 seconds for coordinate releases, and a 4-GiB
sampled-RSS guard. Keep every stdout, stderr, exit, guard, wall/RSS, and
search-progress receipt. Verify SAT assignments against the complete XCNF
and the exact signed group target using the independent archived group law.
Treat bounded searches as `BOUNDED_UNKNOWN`.

The primary comparison is XCNF size and solver status across identical
semantic cells. Positive SAT plus explicit negative UNSAT are correctness
gates. Because each released-coordinate cell fixes all 24 selectors for every
leaf, any coordinate SAT can only recover the already fixed decomposition;
its value is a propagation measurement, not a new relation. Formula build and
unisolated solver wall times are stage
diagnostics. Natural ordinary-query yield, novel rank, final matrix work,
one-target online IC time, and paired rho remain `null` in this control.
The next gate after a verified novel coordinate result is an ordinary-query
same-B relation/rank panel; otherwise use the result to choose a different
leaf/chain decomposition or pivot strategy.
