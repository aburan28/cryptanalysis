# A genus-two cover for both binary n=83 curves

2026-10-14. Explicit construction, written geometric proof, native Rust
verification, and partial Lean formalization. No novelty or solver-speed claim.
The [protocol](PROTOCOL.md) preceded the execution. The run label is
`run-20261014T1442Z`; its initial native n83 receipt was written at 14:47:07 UTC.
The final receipt additionally replays a=1 primality with the native deterministic checker.

**Result.** Over k=GF(2^83), and more generally over any finite binary field,
the smooth projective curve

```
C_a: v²+u²*v = u⁵+a*u⁴+u³+u
```

has genus two and the following separable degree-three map to
`E_a: y²+x*y=x³+a*x²+1`:

```
x = u³/(u+1)²
y = (u*(u+1)*v+u²+u+1)/(u+1)³.
```

This is a cover of curves of dimension one. The destination for group
arithmetic is the dimension-two Jacobian J(C_a), using the induced pullback
`E_a -> J(C_a)`. E_a itself still has a dimension-one Jacobian.

The [Rust tool](../../tools/binary-genus2-cover/README.md) constructs this
family, performs the pullback, and recovers elliptic points from that image.
The [PDF](report.pdf), [diagram](figures/transfer.svg), and
[recorded-count plot](figures/counts.svg) accompany this report.

## Exact requested instances

Both use modulus **0x800000000200000000007**, encoding
`z^83+z^45+z²+z+1`; coefficients are polynomial-basis masks.

| a | Registered source model | Exact subgroup order r | Cofactor |
| --- | --- | --- | --- |
| 0 | `icv1-f2m83-tm6151469093347-debefd74` | 2417851639230796216685689 | 4 |
| 1 | `icv1-f2m83-t6151469093347-cdcc5432` | 8569786107849059 | 1128547018 |

The source representation aliases are `EC1N83Ckb0h252dacc102a4` and
`EC1N83Ckb1h1f579d351b52`. Full source UIDs, P, Q, subgroup data, and
distinct target model UIDs appear in [n83-final.json](runs/run-20261014T1442Z/n83-final.json).
Target UIDs use the explicitly declared local `urn:hyperelliptic-model:sha256`
convention over compact sorted-key model JSON; they are not elliptic EC1 IDs
and do not identify a subgroup. For a=0, the cited historical Sage prime
receipt is reused. For a=1, the final checker freshly verifies primality with
the existing deterministic u64 seven-base Miller–Rabin routine.

The a=1 model here differs from the historical benchmark's other n=83
polynomial basis. No reinterpretation of those coordinates is performed.
The degree 83 is prime, but this construction does not require an intermediate
field: curves, maps, and Jacobian points all stay over GF(2^83).

## Written proof

### 1. Smoothness, connectedness and genus

On the affine chart, the v derivative of the defining equation is u².
A possible singularity therefore has u=0, which forces v=0; the u
derivative there equals one. Thus the affine chart is smooth. At infinity,
put t=1/u and z=v/u³. The equation becomes

```
z²+t*z = t+a*t²+t³+t⁵.
```

At (t,z)=(0,0), its t derivative is one. This is the unique rational
point at infinity on the smooth projective model.

On u nonzero, w=v/u² gives the Artin–Schreier equation

```
w²+w = u+a+1/u+1/u³.
```

It has exactly two poles, at zero and infinity, of odd orders 3 and 1.
An Artin–Schreier coboundary has even leading pole order, so this extension
is geometrically connected. The Artin–Schreier genus formula gives
`2g+2=(3+1)+(1+1)=6`, hence g=2.

### 2. Map equation, degree and exceptional fibers

Normalize the elliptic equation with s=(y+1)/x:
`s²+s=x+a+1/x`. Set `R=u³/(u+1)²` and s=w+1/(u+1). In characteristic two,

```
R=u+u/(u+1)²,
1/R=1/u+1/u³,
(1/(u+1))²+1/(u+1)=u/(u+1)².
```

Substitution proves the map equation on the common open set. The cleared
polynomial identity extends that verification to u=0 and is checked both
coefficientwise in Rust and symbolically in Lean. Its native integer-lift
certificate is **IDC1h7cbc5bff87f8b59d**; see
[certificate and replay](runs/run-20261014T1442Z/identities/).
The integer lift includes an explicit twice-polynomial correction before
reduction modulo two; the IDC1 evaluation field is not the binary field.

R has rational-function degree three and derivative u²/(u+1)², which is
not identically zero. Both C/k(u) and E/k(x) have degree two; the function
field tower therefore gives `[k(C):k(E)]=3`. The relevant extensions are
separable. A nonconstant rational map from a smooth projective curve to a
projective smooth curve extends uniquely to a morphism.

- (u,v)=(0,0) maps to T=(0,1), with ramification index three.
- The two geometric points over u=1 satisfy v²+v=a+1; both map to O,
  unramified. For a=0 over the odd-degree field GF(2^83), they are quadratic
  conjugates; for a=1 they are the rational points (1,0) and (1,1).
- Source infinity also maps to O, unramified.

Thus `pi*O=infinity+F_1+F_2`. Since
`div(u+1)=F_1+F_2-2*infinity`, this is linearly equivalent to 3*infinity.

### 3. Reduced pullback and explicit inverse

For finite P=(x,y) with x nonzero, its cubic fiber is represented by

```
A(u)=u³+x*u²+x
B(u)=kappa*u²+x*u+x,  kappa=(y+1+x)/x.
```

The elliptic equation implies `kappa²+kappa=x+a+1/x` and exact division gives

```
(f+u²*B+B²)/A = u²+(1/x)*u+x = U.
(u²+B) mod U = (x+(y+1)/x²)*u+x+y+1 = V.
```

These are precisely one step of characteristic-two Cantor reduction for the
class of the fiber minus 3*infinity. They give `pi*([P]-[O])=(U,V)`.
At T, `pi*T=3*(0,0)` and `div(u)=2*(0,0)-2*infinity`; consequently its
reduced pair is (u,0). O gives the identity pair (1,0).

The constant coefficients recover `x=U(0)` and `y=V(0)+x+1` in the generic
case. Handle the identity and T separately, validate the divisor, then
recompute the whole pullback and demand equality. This supplies an explicit
inverse on the image. Uniqueness of reduced Mumford representatives proves
injectivity on E(k), including exceptional points.

Pullback on Picard groups is a homomorphism. Therefore Q=kP implies
`D_Q=k*D_P`, and the group law holds in J(C). Independently, the general
pullback/norm theorem gives `pi_* pi^*=[3]`; gcd(3,r)=1 implies subgroup
injectivity for both requested r. The implementation uses the explicit
image inverse; it does not implement a norm on arbitrary Jacobian classes.

## Executed checks

[n83-final.json](runs/run-20261014T1442Z/n83-final.json) records, for each a:
source membership and subgroup checks, valid reduced D_P and D_Q,
nonidentity D_P, rD_P=rD_Q=0, both inverse round trips, eight sampled scalar
relations, eight sampled additions, and the known-answer relation D_Q=37D_P.
These use native BigUint binary-field/Cantor arithmetic for the Jacobian
and the separate u128 fixture implementation for elliptic arithmetic.

| Field size | a | #E(k) | #C(k) | Ordered addition pairs checked |
| --- | --- | --- | --- | --- |
| 2 | 0 | 4 | 2 | 16 |
| 2 | 1 | 2 | 4 | 4 |
| 4 | 0 | 8 | 8 | 64 |
| 4 | 1 | 8 | 8 | 64 |
| 8 | 0 | 4 | 8 | 16 |
| 8 | 1 | 14 | 10 | 196 |
| 16 | 0 | 16 | 24 | 256 |
| 16 | 1 | 16 | 24 | 256 |

Every source rational point, including infinity and poles, and every elliptic
addition pair over these small fields passed. Counts are exhaustive,
deterministic observations, with no statistical error bars. They count curve
points, not Jacobian orders. No 2^83 enumeration is performed.

The native tests also reject invalid points, invalid/reducible fields,
wrong-width coefficients/points, an invalid divisor, and a valid divisor
outside the image. The CLI check rejects wrong witnesses and malformed input.
The certificate tool rejects a false identity and a tampered digest, checks
exact integer expansions, and checks 32 certificate plus 32 extra points.
All are same-host checks; no independent-host claim is made.

Reproduce with `tools/binary-genus2-cover/check.sh`. Source, compiler,
binary and input hashes, exact commands, local validation and failed
preflights are in [the run directory](runs/run-20261014T1442Z/).

## Formalization scope and proof map

Lean 4.24.0, commit 797c613eb9b6d4ec95db23e3e00af9ac6657f24b, is pinned.
There are no external Lean dependencies. Both `lake build` and direct
`lean BinaryGenusTwo.lean` pass. The
[axiom audit](runs/run-20261014T1442Z/lean-axioms.log) reports only
`propext`, `Classical.choice`, and `Quot.sound`; there is no `sorryAx` in
the checked result. `lean4checker` was not installed.

| Report claim | Lean declaration or status | Exact scope |
| --- | --- | --- |
| Cleared equation identity | `BinaryGenusTwo.cleared_map_identity` | All elements u,v,a of any `Lean.Grind.Field K` of characteristic two |
| Affine points map to E | `BinaryGenusTwo.map_affine_point` | Source equation and u+1 nonzero; actual inverse-denominator coordinate formulas |
| Constant-coordinate recovery | `BinaryGenusTwo.image_constants_recover_point` | Characteristic-two field equality for the two recovered constants |
| Genus, projective extension, degree, fibers | Written proof above; not formalized | Needs actual smooth projective function-field objects and their geometric theorems |
| Picard pullback, canonical Mumford formula, homomorphism, injectivity | Written proof plus native checks; not formalized | Needs divisor-class equivalence, Cantor-reduction correctness and Picard functoriality |

This is a **partial** formalization of the construction, not a fully formal
Jacobian-cover theorem. The named remaining problem is
[genus-two geometric formalization](https://github.com/aburan28/crypto/blob/ad73d4bea330eddc4e7db0c660aa91a0255ff3a1/problems/binary-genus2-cover-geometric-formalization.md).
The original geometric claims remain visible rather than being replaced by
the weaker polynomial theorem.

## Scope, canonical graphs and remaining work

The scoped native package checks pass in both repositories. The required
`crypto` whole-library run completed with **4087 passed, 2 failed, 117 ignored**.
The failures are the unchanged `jv_cover` stopped/replayed F4 tests: their
minimum completed-case assertions see 19 and 17 cases. An isolated replay
and the serial pair both pass on the same built binary. The library source and root manifest/lockfile
are unchanged from the pinned base. The
[named validation problem](https://github.com/aburan28/crypto/blob/ad73d4bea330eddc4e7db0c660aa91a0255ff3a1/problems/jv-f4-minimum-completed-cases.md)
retains the full failure and diagnostic; a green whole-library gate is not claimed.

Construction and executable image transfer are verified for both requested
fixtures. Generic norms, other b values, arbitrary curve/cover searches,
nonhyperelliptic arithmetic and a faster destination solver are outside this
tool. No unknown logarithm was recovered. The larger Jacobian contains the
elliptic subgroup; its size alone does not lower that subgroup's DLP cost.

The `crypto` curve-cover catalog explanation is updated to link this additional family.
The existing `hyperelliptic-cover` constructor still selects its earlier
binary genus-three family; this new tool is a separate entry point.
The index-calculus scoreboard, `docs/ic/progress-timeline.json`, performance
figures and existing price tables remain unchanged because this study supplies
no admitted solver-cost or timing observation. Its graph shows a concrete
geometric and arithmetic route, without a speedup edge.

References: Stichtenoth, *Algebraic Function Fields and Codes*, second edition,
§3.7 (Artin–Schreier extensions); Milne,
[*Jacobian Varieties*](https://www.jmilne.org/math/xnotes/JVs.pdf)
(divisors and induced maps); the repository's checked
`binary_ecc/hyperelliptic.rs` (characteristic-two Cantor reduction).
