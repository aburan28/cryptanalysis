# P-256 isogeny-class model eligibility audit

## Requested outcome and scope

The requested outcome is a dramatic ECDLP speedup on a curve explicitly
reachable from P-256. No numerical threshold for "dramatic" was supplied. This
audit tests whether standard curve-model or coefficient shortcuts can appear on
an isogenous neighbor while remaining unavailable to P-256. It does not claim
that untested formula families or unknown non-generic ECDLP algorithms are
impossible.

The machine-readable certificate is
[`model-eligibility.json`](model-eligibility.json), replayed by
[`../../scripts/verify_model_eligibility.py`](../../scripts/verify_model_eligibility.py).
The exact CM and endomorphism facts come from
[`../initial/structural-report.json`](../initial/structural-report.json).

## Observed and certified facts

- Every curve in the `F_p` isogeny class has the same odd prime group order
  `n`, with `n mod 2 = 1` and `n mod 3 = 1`. Consequently no curve in the class
  has an `F_p`-rational point of order two or three.
- A nonsingular Montgomery model has the rational two-torsion point `(0,0)`.
  Twisted Edwards models likewise require rational two-torsion. Neither model
  can represent a member of this class over `F_p`.
- `a = 0` and `b = 0` short-Weierstrass models would have `j = 0` and
  `j = 1728`; the class-wide CM certificate excludes both.
- `p mod 4 = 3`. The fourth powers in `F_p*` are therefore exactly the squares.
  Every nonzero short-Weierstrass `a` can be normalized to either `1` or the
  least positive nonsquare, which is `3` here. The certificate explicitly maps
  P-256 from `a = -3` to `a = 1` and verifies the transported generator.
- The retained native rho loop calls the same complete addition formula for
  every candidate. That addition performs three full multiplications by `a`
  and two by `3b`, with no candidate-dependent formula branch. Candidate timing
  differences in that backend do not constitute coefficient structure.
- No embedding degree at most 1000 was found. Because `p` and `n` are isogeny
  invariants here, this check cannot differ between candidates.

## Requirement-to-evidence status

| Requested search axis | Status | Evidence and boundary |
| --- | --- | --- |
| Extra rational automorphisms | Refuted class-wide | Fundamental CM discriminant excludes `j = 0,1728`; geometric automorphism order is two. |
| Efficient low-norm endomorphism | Refuted class-wide | The certified non-scalar norm lower bound is `ceil(abs(D_K)/4)`. |
| Montgomery or Edwards arithmetic shortcut | Refuted class-wide over `F_p` | Odd prime group order excludes rational two-torsion. |
| Exceptional short-Weierstrass coefficient | Refuted as neighbor-only advantage | Exceptional `a=0` or `b=0` is excluded; small-`a` normalization is available to P-256 itself. |
| Small MOV embedding degree | Refuted through degree 1000 | Exact modular-order checks for `k=1..1000`; not a proof about all `k`. |
| Dramatic measured ECDLP speedup | Not established | This deterministic audit is not a timing experiment or a collision solve. |

## Typed correspondence and costs

The coefficient normalization is an `F_p`-isomorphism, not an isogeny to a new
isomorphism class. It maps `(x,y)` to `(x/u^2,y/u^3)` and preserves the scalar
relation exactly. Construction requires one reusable fourth-root exponentiation;
two point evaluations are the per-key conversion cost. No timing is reported,
because the class-wide eligibility result is algebraic and P-256 receives the
same optimization.

The isogeny correspondence remains `E_0(F_p)[n] -> E_i(F_p)[n]` through the
explicit retained separable maps. The destination logarithm equals the source
logarithm because every path degree is coprime to prime `n`. That statement does
not by itself reduce ECDLP work.

## Finding and open obligation

No dramatic speedup is established. Standard model shortcuts are either
class-wide unavailable or equally available to the P-256 baseline. A positive
result now requires a genuinely different ECDLP algorithm or a new end-to-end
formula implementation, followed by explicit path costs, verified logarithm
transport, fresh controls, and the repository isolation gate.

The transfer skill's main methodology was applied directly. Its linked
methodology and JSON-template resources were unavailable from the skill store
during this run; that tooling limitation does not change the algebraic checks
above.
