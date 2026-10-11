# Quartic factorization of the rotated four-atom resultant

The 266-term rotated four-atom resultant has an exact **two-quartic
factorization** whenever its two rotated seeds differ by an
Artin–Schreier image and the proposed reciprocal output is also an
Artin–Schreier image. For the same-seed Frobenius geometry used by the
N41 and N131 sources, the seed condition holds automatically. Thus a
proposed output with `Tr(z)=0` admits a factored block constraint of
bidegree `(4,4)` in the two pair products, instead of bidegree `(8,8)`.
The [symbolic factors](symbolic_result.json) were independently checked
by sparse GF(2) polynomial multiplication over all five variables.

This gives a lower-degree constraint for a future joint target solver.
A direct two-GCD replacement in the existing fixed-output inverse was
slower in the measured N131 stage, so the factorization's useful role is
in symbolic family rejection rather than that scan loop.

## Universal identity

The archived resultant `H(a,b,P,Q,z)` eliminates the two pair reciprocal
coordinates and their upper S3 relation. Set

`b = a + v² + v`, `z = u² + u`.

The [checked-Sage derivation](derive_symbolic.py) factors the substituted
polynomial as `F₀(a,v,u,P,Q) F₁(a,v,u,P,Q)`. Both factors have degree four
in `P` and in `Q`. The substituted polynomial contains 1,452 monomials;
the two factors contain 114 and 138 monomials in the five-variable
representation. The [independent audit](audit_symbolic.py) expanded the
original 266 terms under both substitutions and multiplied the archived
factor supports using a separate sparse GF(2) implementation. Both sides
have the same exact 1,452 monomials. The
[symbolic protocol](symbolic_protocol.json) and
[audit protocol](symbolic_audit_protocol.json) bind the sources before
their respective runs.

For a binary field, `w²+w=c` has a field solution exactly when
`Tr(c)=0`. Here `a=s^(2^r₀)` and `b=s^(2^r₁)` come from the same source
seed, so Frobenius invariance gives `Tr(a+b)=0`. Any proposed `z` with
`Tr(z)=0` therefore specializes the universal identity to two quartics
over the original field. The identity proves factorization under these
conditions; it does not assert that the two quartics are irreducible or
that `Tr(z)=1` always makes `H` irreducible.

## Frozen finite-field controls

The N41 field is `GF(2)[t]/(t^41+t³+1)`, W6 seed mask 4, rotations
`(10,15)`. The N131 field is
`GF(2)[t]/(t^131+t^13+t²+t+1)`, W15 seed mask 13686,
rotations `(26,39)`. Each fixed-seed, fixed-output specialization has
37 nonzero `P,Q` terms and bidegree `(8,8)` before factorization. The
[case protocol](protocol.json) binds the checked Sage runtime, resultant,
and controls. Five [individual factorizations](n41_positive.json) cover
the N41 known output, field control, public point, and the two N131
controls. The [torsion-shift screen](torsion_result.json) adds paired
`z+1` outputs and all four archived N131 public-target raw lifts.

| Field | Proposed outputs | `Tr(z)=0`: two 13-term quartics | `Tr(z)=1`: degree-eight irreducible in tested cases |
| --- | ---: | ---: | ---: |
| N41 | 5 | 2 / 2 | 3 / 3 |
| N131 | 7 | 3 / 3 | 4 / 4 |

The N131 public raw lifts at indices 0 and 2 split; indices 1 and 3,
whose reciprocal coordinates differ from 0 and 2 by one, stay degree
eight in this fixed-seed specialization. The archived public target and
four-lift receipts define these exact inputs. The pattern is evidence for
the algebraic character above, while the universal identity supplies the
proof for every trace-zero specialization.

## Boolean width and native product-space replay

On the N41 five-bit product basis, [all 1,024 product pairs](boolean_result.json)
give Boolean degree four and **236 nonzero coefficients** for each
quartic, for both the known relation block and the public point used as a
proposed block output. All allowable mixed bidegree-at-most-`(2,2)`
monomials appear; only pure quadratic monomials are absent. The known
block's single product root occurs in one factor. The public point has
zero roots in this fixed four-atom family. The full resultant on the same
N41 basis had degree six and 656 coefficients.

The 13-term quartic support gives a source-bound Boolean ANF ceiling for
a W15 fixed-seed factor with 14 product bits on each side:

`(1+14+91)² - 2·91 = 11,054` field coefficients per factor.

Two factors therefore have at most 22,108 coefficients before sharing,
versus the full resultant's 220,172-coefficient ceiling. These are
symbolic support bounds; the N131 factor ANFs were not expanded or
timed. A joint solver can retain the 13-term power forms and introduce
the Artin–Schreier variables `u,v` with quadratic equations.

The [frozen native replay](native_protocol.json) used the archived N131
constructed block output and all 16,384 first-product states. It found
the same single `(P,Q)` root as the degree-eight scan. The
[independent bit-field audit](split_audit_result.json) recovered the
degree-one GCD root from both receipts, checked the known product pair,
evaluated both factors, and evaluated the original resultant. One worker
completed under the 100-second query and 4-GiB native RSS checks.

| N131 fixed-output inverse | Query time | Peak RSS | Product roots |
| --- | ---: | ---: | ---: |
| Archived degree-eight GCD scan | 6.522 s | 2,359,296 B | 1 |
| Two degree-four GCD scans | 27.090 s | 2,293,760 B | 1 |

These CPU times are exploratory runs on an unisolated host and different
native implementations. The observed two-GCD scan costs more for this
fixed-output stage. Its [receipt](split_receipt.json) preserves the exact
source, binary, input, query interval, process wall, exit status, and
memory counter. The next experiment should put the quartic equations
inside a *target-conditioned joint N41 search* with both constrained
blocks and the free pairs unpinned. It must count rejected product and
seed families before mask expansion, replay an ordinary public relation,
then project the complete N131 work and RSS under the one-worker
600-second/4-GiB gate. This block method is a design proposal with
`candidate_id: null` until the complete IC pipeline is fixed.
