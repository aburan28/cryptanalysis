# Scalar-conditioned selective normalization screen

This experiment tests a **candidate representation policy** on one
variable-base secp256k1 scalar at a time. It uses the same published
width-four digit stream and paired τ evaluator as the preceding
control. Its only new choice is made after recoding: among the eight
constructed seed points, batch-normalize a point if its seed index
occurs at least twice *after* the first (free) accumulator insertion.
Seed zero, the input base, is already affine. The rule is a fixed
source-level heuristic, not a claim of mathematical or academic
novelty. Compare it with zero normalization and normalization of all
eight constructed points on 64 fresh base/scalar pairs.

All arms use the same explicit `48M+35S` Jacobian seed chain and
prepare the nine three-point unit orbits for `9M`. The orbit works
on either Jacobian or affine coordinates. If `m` constructed points
are normalized, one Montgomery batch inversion costs `3m−3`
multiplications and one inversion; coordinate conversion costs
`3mM+mS`. Thus the incremental cost for `m>0` is
`(6m−3)M+mS+1I`, while `m=0` costs zero. A mixed addition after
initialization costs `8M+3S`; a general Jacobian addition costs
`12M+4S`. The first accumulator insertion is free in both cases.
Every paired stride is a cheap `6M+4S` stride under the prepared
unit orbit, and every ordinary τ is `4M+2S`.

Keep inversion as a separate symbol. Report each case as `M`, `S`,
and `I`, as well as the threshold inversion price in `M+S`
equivalents at which selective normalization and full normalization
tie the no-inversion projective arm. This is an arithmetic screen;
the target field kernel must determine the actual inversion price
before choosing a policy or claiming speed. The evaluator is
variable-time and depends on the scalar's digits.

For every fresh input, compare all nine prepared points with
independent Sage group expressions, and compare all three complete
scalar outputs with Sage's `kP`. Preserve raw per-case counts,
selected seed indices, source hashes, failures, and the checked
Sage runtime receipt. The source aborts on an assertion failure and
does not serialize a partial failure row; this limits its use as a
campaign collector. No CPU timing or academic novelty claim is made.

Freeze this protocol and `selective_normalization.py` before deriving
the new input set. Then run:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/prime-j0-secp256k1-scalar/selective-runtime-info.json
/Volumes/SSD990/cryptanalysis/sage -python experiments/prime-j0-secp256k1-scalar/selective_normalization.py
```
