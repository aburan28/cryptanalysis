# Guarded symbolic reuse: an existing method and explicit failure cases

Traverso-style tracing is established work, not a new F6 invention.
[Demin's 2026 paper](https://arxiv.org/abs/2607.06372v3) describes reusable F4
traces for specializations. The [Groebner.jl interface](https://sumiya11.github.io/Groebner.jl/interface/#Learn-and-Apply)
exposes learning and application and cautions that an application success flag
can be a false positive. Our independent exact checker must remain the
acceptance criterion for any such experiment.

Over GF(2), fixing the actual support of every input polynomial fixes every
coefficient, since the only nonzero coefficient is one. Different targets must
therefore either change actual support or produce identical equations. A
target-independent *envelope* may still provide reusable column layouts, but
zero coefficients, leading terms and numerical rank need fresh treatment.

The retained counterexample uses the Boolean equations

`F_t = {x + y, xy + t*x}`, with `t` in `{0,1}`.

Its envelope is fixed. For `t=0`, the reduced Boolean basis is `{x,y}` and the
only root is `(0,0)`. For `t=1`, the basis is `{x+y}` and the roots are `(0,0)`
and `(1,1)`. Substituting `y=x` gives `x^2+t*x`, which becomes `(1+t)*x`
after the Boolean relation. Thus even this small specialization changes the
leading ideal. The unchanged native checker, separate Python algebra checker,
and exhaustive two-variable truth checker verify both results. Applying either
case's basis/proof to the other case is rejected by the native checker.

Few target parameters do not by themselves imply low-rank matrix updates:
the one-parameter family `M(t)=t*I_N` changes by rank `N` between zero and one.
Any proposed low-rank update method must establish a rank bound for its actual
Macaulay matrices, not infer it from parameter count.

The checked S4 polynomial in this workload has target exponents `0,1,2,3,4`.
The cubic target power prevents simply treating its coefficients as an affine
function of target bits: in characteristic two, cubing multiplies a Frobenius
square by the original element. This alone neither proves high update rank nor
rules out a more structured factorization.

A next experiment should compare input envelopes, actual pivot sequences,
zero-row decisions and update ranks on fresh specializations. Reuse only
immutable symbolic data; recompute numerical rows and derivation witnesses.
If a trace guard fails, charge the failed attempt and fallback to the target.
Completion and ideal equality, including Boolean field relations, must still
pass the independent checker. Such an experiment could improve constants for
an applicable family; no asymptotic or novelty claim is established here.
