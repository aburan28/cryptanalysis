---
title: "Surface and subgroup checks over GF(2^83)"
date: "2026-10-12 — run-20261012T0331Z"
---

# Result and scope

Both pinned Koblitz variants passed the native quartic-model and subgroup
checks. Each embeds into its own product and into the matching factor of
$E_0\times E_1$, with the group law on the whole product. The opposite pure
product fails the necessary transfer conditions. These are faithful
representations of the original ECDLP; a faster solver was not supplied or
measured. The default targets were public known-answer $Q=37P$.

The field is $\mathbf F_{2^{83}}$, with polynomial basis
$z^{83}+z^{45}+z^2+z+1$. The two sources are
$E_a:y^2+xy=x^3+ax^2+1$, $a\in\{0,1\}$. This is an arithmetic correctness
run on one ordinary Linux x86-64 host, not an IC/rho benchmark.

| Variant | Prime subgroup order $r$ | Cofactor $h$ |
|:--|--:|--:|
| $a=0$ | 2417851639230796216685689 | 4 |
| $a=1$ | 8569786107849059 | 1128547018 |

Field degree 83 does not specify subgroup size. The $a=0$ order has bit length
82; the $a=1$ order has bit length 53. The existing Sage proof receipt is reused
for both primes; the run additionally checks $a=1$ with deterministic u64
Miller–Rabin. No new Sage primality run or second-host replay is claimed.

![Verified inclusions and rejected opposite products. The source labels are exact representation IDs; see the records below.](destinations.pdf)

# What the checker actually ran

The modulus passed Rabin's irreducibility criterion. The Frobenius trace
recurrence reproduced the recorded orders and $rh$. Both nonidentity
generators passed $rP=O$; both targets passed $rQ=O$ and the witness check.
Each source and target had Frobenius period 83. Per variant the checker tested
166 orbit-point entries, each in its normalized and a second projective
scale, plus eight transported-addition pairs. A point on a smooth containing
quadric, outside the curve image, was rejected.

The same public targets were checked again with no scalar supplied: subgroup
membership and the transported representation passed, and scalar-verification
fields remained null. This tests the checker interface; the target values
remain known-answer fixtures, not recovered unknown logarithms.

Four CLI controls exited with status 2: unsupported degree 82, the two-torsion
point $(0,1)$ in each odd-order subgroup, and an incorrect scalar witness.
The native package's 22 tests passed. Its controls include independent
three-word carryless multiplication and long reduction, exhaustive curve
counts over degrees 1–5, and direct projective quadric counts over GF(2) and
GF(4). The certificate package's five tests passed, including rejection of
false integer lifts and the omitted characteristic-two correction.

![Recorded verification counts, one correctness run per variant. Entries are test populations, not distinct group states or performance measurements.](checks.pdf)

# Why the characteristic-two pencil works

Use the embedding and its inverse

$$
(x,y)\longmapsto[1:x:y:x^2],\qquad O\longmapsto[0:0:0:1],
$$

$$
Q_1=WZ+X^2,\qquad Q_2=Y^2+XY+XZ+aWZ+W^2.
$$

Their intersection is the curve image. On $W\ne0$, its inverse is
$(X/W,Y/W)$; on $W=0$, the equations force $X=Y=0$, leaving only the origin.
The transported law is $\operatorname{encode}(\operatorname{decode}(U)+
\operatorname{decode}(V))$. Thus the inverse preserves the source subgroup
and its ECDLP relation. A containing quadric's other points are outside that
law's domain. The control $[1:0:0:1]$ lies on the smooth member
$\lambda=a+1$ but has $Q_1=1$, so decoding rejects it.

For $S_\lambda=Q_2+\lambda Q_1$, put $c=\lambda+a$. Its polar matrix has
determinant $c^2$. It is nonsingular for $c\ne0$. At $c=0$ the point
$[1:0:1:1]$ is singular. The infinite member $Q_1$ is also singular.
Hence exactly $q-1$ finite members are smooth, where $q=2^{83}$.

With $c\ne0$, an invertible change of coordinates gives a hyperbolic plane
and the binary form

$$t^2+st+\delta_\lambda s^2,\qquad
\delta_\lambda=\lambda+c^{-2}.$$

The member is split precisely when this binary form is isotropic, equivalently
when $u^2+u=\delta_\lambda$ has a solution. The Artin–Schreier map has kernel
$\{0,1\}$ and image equal to the absolute-trace-zero hyperplane. For odd
degree 83 the trace map is nonzero since $\operatorname{Tr}(1)=1$.

For each nonzero curve coordinate $x=c$, writing $y=xv$ gives
$v^2+v=x+a+x^{-2}=\delta_{a+x}$. There are two solutions exactly for a split
member. At $x=0$ there is one point $(0,1)$, plus $O$. Therefore

$$\#E_a=2+2\,\#\{\text{smooth split finite members}\}.$$

The curve is defined over GF(2). With $\tau_0=2$ and
$\tau_1=-1$ for $a=0$, $\tau_1=1$ for $a=1$, its extension traces satisfy
$\tau_n=\tau_1\tau_{n-1}-2\tau_{n-2}$ and
$\#E_a=q+1-\tau_{83}$. These exact counts use algebra and the recurrence;
the run does not enumerate $2^{83}$ parameters.

| Variant | $\#E_a$ | $\tau_{83}$ |
|:--|--:|--:|
| $a=0$ | 9671406556923184866742756 | -6151469093347 |
| $a=1$ | 9671406556910881928556062 | 6151469093347 |

For both variants there are **9671406556917033397649407** smooth finite members.

| Variant | Smooth split | Smooth nonsplit |
|:--|--:|--:|
| $a=0$ | 4835703278461592433371377 | 4835703278455440964278030 |
| $a=1$ | 4835703278455440964278030 | 4835703278461592433371377 |

# Product surfaces and the actual obstruction

Inclusion into $E_a\times E_a$ is $P\mapsto(P,O)$; projection recovers $P$.
Inclusion into $E_0\times E_1$ uses the matching component. Both products have
componentwise elliptic addition on every point, and both inclusions have
trivial kernel. Their Frobenius polynomials contain the source factor by
construction. They leave the ECDLP on its original elliptic factor.

The source factors are $\chi_i(T)=T^2-\tau_iT+q$ over the integers. Their
difference is $(\tau_1-\tau_0)T$, nonzero here, while $\chi_i(0)=q\ne0$.
Thus they are coprime and $\chi_a$ does not divide $\chi_{1-a}^2$.
Also $r_0$ does not divide $\#E_1$ and $r_1$ does not divide $\#E_0$; the
recorded remainders are positive. Since these r are prime, neither can divide
the opposite order squared. Hence the opposite product cannot receive an
injective transfer of that prime subgroup over this field.

Frobenius polynomials retain integer coefficients and trace signs; their
coefficients are not reduced modulo 2. The separate general polynomial CLI
still has u64/i128 limits. This n=83 check handles explicit products, not
arbitrary supplied large-q polynomials or new Jacobian constructions.

# Identity records, representation IDs, and replay

Six `identity.certificate/v1` records each passed exact integer-coefficient
expansion, 32 statement-derived evaluations and 32 additional evaluations.
The four geometric lifts reduce modulo 2. The normal-form integer lift carries
an explicit $2bcus$ correction, which vanishes after reduction. The two
Frobenius identities remain over the integers. The v1 evaluator remains over
$2^{61}-1$; these records do not claim random evaluation in GF(2^83), a formal
proof, or a second host.

| Identity | Certificate |
|:--|:--|
| Quartic embedding | `IDC1h6d8ec6e3d63f147b` |
| Alternating polar determinant | `IDC1hb0891fcca2c98751` |
| Cleared-denominator normal form | `IDC1hb857d55c10efa5ac` |
| Point-count substitution | `IDC1h0869c94c259c1d1a` |
| Frobenius difference | `IDC1h4d9709f79f94a6db` |
| Frobenius product | `IDC1h240f8c156bb16781` |

Exact record IDs are `EC1N83Ckb0h252dacc102a4` and
`EC1N83Ckb1h1f579d351b52`. Their full UID prefix is
`urn:ec-record:1:sha256:` followed by these digests:

`252dacc102a4f15413d4a269e2156852ad18dd6f8b25cf207146868c4592e2cc`

`1f579d351b52b0f3aba9259aa9b77738a958c3dbb995a6965bb50822ad199bb3`

The archived a=1 benchmark uses another polynomial basis and point encoding.
Its identifiers and targets are not substituted here. These new exact metadata
records preserve their own hash preimages; no archived alias is reassigned.

From the repository root, reproduce the run with:

```sh
cargo run --release --offline --locked \
  --manifest-path tools/ecdlp-surfaces/Cargo.toml \
  --bin binary_surface_check -- --degree 83 --a both --output /tmp/n83.json
cargo run --release --offline --locked \
  --manifest-path docs/ecdlp-surfaces/certificates/Cargo.toml \
  --bin binary_identities -- /tmp/n83.json /tmp/n83-identities
tools/ecdlp-surfaces/check.sh
```

Raw evidence: [both cases](../../runs/run-20261012T0331Z/n83.json),
[no-witness a=0](../../runs/run-20261012T0331Z/no_witness_a0.json),
[no-witness a=1](../../runs/run-20261012T0331Z/no_witness_a1.json),
[identity replay](../../runs/run-20261012T0331Z/identities/identity_replay.json),
[a=0 curve record](../../runs/run-20261012T0331Z/identities/curve_record_a0.json),
[a=1 curve record](../../runs/run-20261012T0331Z/identities/curve_record_a1.json),
[source and binary hashes](../../runs/run-20261012T0331Z/source_and_binary.sha256),
and the [run manifest](../../runs/run-20261012T0331Z/manifest.json).

The full `crypto` library gate was attempted and remains blocked by its
preexisting syntax error in the Koblitz factor-base source, line 1854
([diagnostic](../../runs/run-20261012T0331Z/root_library_gate.log)).
Its source is unchanged. Conductor is unavailable. An initial launch used a
root-relative manifest from the crate directory and failed with exit 101;
the corrected commands above passed. That failure and the preliminary smoke
output are retained separately from the final recorded evidence.

No IC candidate, isogeny route, performance row, or subgroup-size promotion is
made. Canonical graph and registry checks are recorded in `GRAPH_REVIEW.md`.
Arbitrary surface homomorphisms, target-solver cost, and any ECDLP advantage
remain unresolved. No task is scheduled after this report.

# Sources

- [SEC 1 v2, §§2.1.2 and 2.2.2](https://www.secg.org/sec1-v2.pdf): polynomial-basis binary arithmetic and the elliptic addition formulas used here.
- [Pinned n=83 fixtures](https://github.com/aburan28/crypto/blob/8f7f796d694fd41b4db81b25c1aff3632d012c65/src/cryptanalysis/koblitz_index_calculus.rs#L975): exact source generators, orders and cofactors.
- [Existing prime-proof receipt](https://github.com/aburan28/crypto/blob/8f7f796d694fd41b4db81b25c1aff3632d012c65/research/f6_wide_n83_20261004/prime-check.txt) and [checked-Sage source](https://github.com/aburan28/crypto/blob/8f7f796d694fd41b4db81b25c1aff3632d012c65/research/f6_wide_n83_20261004/prime_check.sage): reused proof evidence; local copies and hashes accompany this study.
- [Sutherland, MIT 18.783, Lecture 13](https://math.mit.edu/classes/18.783/2023/LectureNotes13.pdf): Frobenius characteristic-polynomial framework. The extension trace recurrence and binary classification are derived explicitly above.
- [Native checker](../../../../tools/ecdlp-surfaces/src/binary.rs), [independent native controls](../../../../tools/ecdlp-surfaces/tests/binary.rs), and [integer-lift checker](../../../../docs/ecdlp-surfaces/certificates/src/bin/binary_identities.rs).
