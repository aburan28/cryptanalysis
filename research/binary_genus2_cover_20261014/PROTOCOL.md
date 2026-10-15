# Same-field binary genus-two cover: protocol

Written 2026-10-14 before the native construction run. This is an exploratory
construction and correctness study, with no selection or speed claim.

## Requested result

Construct a higher-genus cover for the previously requested elliptic curves
over the prime-degree extension GF(2^83), for both a=0 and a=1. Supply an
explicit same-field map, executable Rust Jacobian transfer, and reproducible
evidence. Retain the distinction between a curve and its Jacobian.

## Fixed construction

Over any finite characteristic-two field k, use

```
E_a: y^2 + x*y = x^3 + a*x^2 + 1
C_a: v^2 + u^2*v = u^5 + a*u^4 + u^3 + u
pi(u,v) = (u^3/(u+1)^2, (u*(u+1)*v + u^2+u+1)/(u+1)^3).
```

Work on the smooth projective models. Source infinity and the points over
u=1 map to E's origin. The point (0,0) maps to (0,1).
The Artin–Schreier equation is w^2+w=u+a+1/u+1/u^3, with odd pole
orders 3 and 1; its genus is two. The cover degree is three.

For P=(x,y), x nonzero, check the reduced pullback relative to source infinity:

```
U(u)=u^2+(1/x)*u+x
V(u)=(x+(y+1)/x^2)*u+x+y+1.
```

O pulls back to the identity and (0,1) pulls back to (u,0).
The image inverse reads x=U(0), y=V(0)+x+1 and must verify that the
candidate's recomputed pullback equals the supplied divisor. It rejects
divisors outside that image. This is not a norm for arbitrary divisor classes.

## Inputs and controls

- Use exactly the `tools/ecdlp-surfaces` n83 fixtures, with polynomial basis
  z^83+z^45+z^2+z+1, modulus 0x800000000200000000007. Preserve both
  generators, subgroup orders, cofactors, and prior prime-proof provenance.
- Public known-answer Q=37P; supplied-Q mode omits a scalar unless explicitly
  supplied. No search for an unknown discrete logarithm.
- At n=83 check source membership, rP=rQ=O, nonidentity P, gcd(r,h)=1,
  gcd(r,3)=1, reduced divisors, rD_P=rD_Q=0, inverse round trips,
  and transported additions. Check Q=37P and D_Q=37D_P for the fixture.
- Exhaustive controls over GF(2), GF(4), GF(8), GF(16), both a values:
  all affine source-point maps and every pair of elliptic points under
  pullback/addition. Count smooth-projective source points by adding its
  single infinity. No field-wide or subgroup scan at n=83.
- Negative controls: invalid elliptic and source points, wrong-width input,
  invalid divisor, a valid divisor outside the image, wrong scalar witness,
  and malformed CLI arguments. Include exceptional points and identities.
- Verify the cleared map identity coefficientwise. Issue an
  identity.certificate/v1 integer-lift record with explicit even correction,
  exact integer expansion, and a distinct checker seed.

## Formalization and reporting

Attempt Lean 4 formalization of the actual characteristic-two map theorem;
pin toolchain/dependencies, retain build output and axiom audit. Keep a proof
map distinguishing checked declarations from the written geometric and
Picard-functor arguments. Record any remaining formalization gap precisely.

Use native Rust research execution only. Preserve source hashes, git bases,
commands, environment, exits, successes and failures in a fresh run directory.
Produce a source-linked report, diagram, recorded-count plot, and inspected PDF.
The report is a construction receipt, not a performance benchmark. Neither
same-field transfer nor a genus-two destination establishes a faster solver.

## Acceptance

| Requirement | Required evidence |
| --- | --- |
| Explicit genus-two curve and degree-three map | Equation, exceptional fibers, genus/degree proof, exact identity check |
| Executable group transfer | Checked Mumford pullback and inverse; exhaustive small-field controls |
| Requested field and both variants | Native n83 reports with exact source identities and subgroup checks |
| Reproducibility | Rust CLI, frozen outputs and hashes, local checks, report and PDF |
| Honest formal scope | Checked Lean declarations/axioms and explicit remaining geometric proof obligations |

No timing, independent-host replay, generic norm, generic cover search,
descent to GF(2), or target-solver advantage is an acceptance claim here.
