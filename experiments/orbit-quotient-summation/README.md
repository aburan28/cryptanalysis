# Orbit-valued factor base → quotient-native summation

Date: 2026-09-26.

This experiment implements the structural gate we wanted to answer **before**
optimizing Gröbner, SAT, or final relation linear algebra:

> If the factor base consists of signed Frobenius orbits, does eliminating the
> phases leave a small, low-degree quotient-native summation relation?

The answer from these exact toy experiments is **not in the current payload
coordinates**. Orbit folding dramatically changes relation density, but the
eliminated compatibility predicate looks algebraically generic at the largest
toy case. This does not rule out another quotient presentation or an
auxiliary-variable correspondence.

## Construction

We use E0: y^2+xy=x^3+1. For prime degree n, with s dividing n-1, the
cubic-quotient factor-space construction gives a linear s-bit payload for the
auxiliary subfield W=F_(2^s). A nonzero payload names one x-coordinate orbit
under Frobenius. After rational lifting and odd-subgroup filtering, that
payload is an **orbit-valued factor-base key**.

For a key q, let O(q)={+/- sigma^a P_q : 0<=a<n}. For a target T, the
phase-free three-key predicate is true exactly when representatives from
O(q1), O(q2), O(q3) sum to T. The four-key predicate is analogous. The Boolean
inputs are only quotient payload bits; signs and Frobenius phases are
existentially eliminated by exact toy-group enumeration.

The fixed-phase control uses phases (0,1,2) or (0,1,2,3), with signs still
free. Both methods receive the same factor base and the same planted blind
targets. The tiny-group BSGS in the harness only converts verified points to
scalar labels so the exact relation can be enumerated cheaply. It is an
independent measurement oracle, not part of a proposed attack.

## Frozen cases

The normal generators are reused from the earlier Frobenius experiments.

| n | s | normal generator | subgroup r | Frobenius eigenvalue | usable orbit keys |
|---:|---:|---:|---:|---:|---:|
| 13 | 4 | 5475 | 2003 | 89 | 7 |
| 19 | 6 | 112679 | 130873 | 41811 | 23 |

Each case uses eight deterministic target orbits, seed 20260926.

## 1. Phase elimination changes relation density exactly as expected

For three summands, the median number of compatible key triples is:

| case | key-triple domain | fixed phase | phase free | phase-free density |
|---|---:|---:|---:|---:|
| n=13,s=4 | 343 | 2 | 337.5 | 0.9840 |
| n=19,s=6 | 12,167 | 2 | 3,970 | 0.3263 |

At n=19 the phase-free positive tuples usually have a single concrete
sign/phase witness. The uniform-group heuristic uses mean witness count
mu_m=(2n)^m/r and compatibility probability approximately 1-exp(-mu_m).

For n=19,m=3 this gives mu=0.4193 and probability 0.3425, close to the
measured median 0.3263. The hidden phase condition is therefore behaving much
like a real matching constraint, not like a large family of redundant
solutions.

For four summands at n=19 the regime flips: mu=15.93. Across the eight
targets, 279,036–279,413 of 279,841 orbit-key quadruples are compatible
(median density 0.997829), and the median compatible tuple has 16 concrete
sign/phase witnesses. The uniform prediction is essentially one.

This is a useful control: quotient folding does not destroy relations. It
moves the phase/sign entropy into the compatibility predicate.

## 2. The exact phase-free predicate is not low degree in these coordinates

We measured two different notions of Boolean complexity.

### Full payload cube

Invalid payloads are set to false. For the first target:

| case | fixed phase ANF | phase-free ANF |
|---|---|---|
| n=13,s=4 (12 variables) | degree 12, 704 monomials | degree 11, 946 monomials |
| n=19,s=6 (18 variables) | degree 18, 16,384 monomials | degree 18, 94,262 monomials |

The n=19 phase-free predicate reaches the maximum possible degree and is much
denser than the fixed-phase control.

### Valid-key domain only

To avoid charging factor-base membership to the summation relation, we also
ask for the minimum degree of any Boolean polynomial that agrees with the
predicate only on valid key triples.

At n=13 the valid domain has 343 points. Degree <=5 has evaluation rank 335.
Seven of eight phase-free target predicates are inconsistent there; degree 6
has full rank 343 and represents all eight.

At n=19 the valid domain has 12,167 points. Degree <=8 has rank 12,159 and
**all eight phase-free predicates are inconsistent**. Degree 9 has full rank
12,167 and represents all eight. For this corpus the phase-free predicates
first become representable exactly when the polynomial space becomes capable
of representing every Boolean function on the valid domain.

That is the structural stopping result. We did not find a special low-degree
quotient summation law to hand to Gröbner/SAT. An invertible linear change of
the W/payload coordinates does not change Boolean algebraic degree, so merely
choosing another linear basis of the same quotient key space does not address
this result.

This is not an impossibility theorem. Nonlinear reparameterizations,
auxiliary variables, or a multi-valued correspondence can behave differently.

## 3. Degree-131 entropy accounting

The prior degree-131 construction has 2^26-1 nonzero raw quotient keys. In its
recorded sample, 68 of 256 distinct payloads produced accepted r-torsion point
orbits. Using that sample only as an acceptance estimate gives about
1.7826e7 = 2^24.087 usable orbit keys.

For the exact degree-131 subgroup order used by the harness, log2(r) is about
129. For four orbit keys, the uniform mean witness count per fixed key tuple is

    mu_4 = 262^4 / r = about 2^-96.866.

So a fixed orbit-key quadruple is compatible with a target with probability
about 2^-96.9 in the sparse degree-131 regime. Meanwhile the estimated
key-quadruple space is about 2^96.350. Their product is about 0.70 relations
per target.

The accounting is especially revealing:

- four orbit keys: about **96.35 bits**;
- four independent sign/Frobenius choices: about **32.13 bits**;
- total concrete witness space: about **128.48 bits**;
- target group: about **129 bits**.

So the ~131x representative collapse per factor-base element does **not**
remove the missing entropy. It reappears almost exactly as the phase-free
compatibility condition.

If relation collection needs on the order of 2^24.09 independent orbit
columns, a rho-sized 2^60.8 total budget leaves only about 2^36.7 work per
relation **before charging final linear algebra**. Generic search of the
2^96.35 orbit-key quadruple space is therefore short by roughly 59.6 bits.
This is a budget diagnostic, not a lower bound.

## Decision gate

**Do not spend the next cycle optimizing Gröbner/SAT/linear algebra for the
fully eliminated phase-free ANF.** The intended structural gate did not pass:
at n=19 the quotient-native predicate shows no degree <=8 representation on
the valid domain, and degree 9 is exactly the saturation point.

The orbit-valued factor base itself remains useful. The next representation
to test should retain a *small relative-phase certificate* rather than
eliminating phases completely—for example a pair correspondence indexed by a
relative Frobenius displacement in C_n, composed with cyclic
convolution/meet-in-the-middle. That keeps orbit columns while exposing the
compatibility information instead of hiding it inside a near-generic Boolean
predicate.

Only if that correspondence has a compact low-degree/sparse representation
should Gröbner/SAT optimization resume.

## Reproduce

~~~sh
cd experiments/orbit-quotient-summation
python3 run.py --out /tmp/orbit-quotient.json
~~~

The experiment is stdlib-only and reuses experiments/pdp-scaling/gf2n.py.
The frozen independently measured summary is in results/reference.json.

Scope: toy exact arithmetic plus a sample-derived n=131 projection. No
degree-131 relation was found, no DLP was solved, no attack exponent is
claimed, and the interpolation result is not a lower bound on other algebraic
representations.
