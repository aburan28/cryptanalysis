# Genus-2 and higher ECDLP transfers

Use this reference for higher-genus representations, hyperelliptic covers,
Mumford arithmetic, elliptic factors of Jacobians, genus-2 gluing, CM
polarizations, or Kummer models. It extends the skill's routing to existing
tools and construction workflows; it does not add an arbitrary-Jacobian
constructor to `tools/ecdlp-surfaces`.

## Select the implementation

| Case | Existing entry point | Boundary |
| --- | --- | --- |
| Genus-2 cover of `y^2=x^3+a*x+b`, characteristic greater than three | `crypto`: `hyperelliptic-cover construct` / `verify` | The fixed degree-two cover is a smooth sextic with two rational infinity points. Its construction is checked; pullback, norm, and its two-infinity Jacobian arithmetic are not implemented. |
| Genus-3 cover of an ordinary binary elliptic curve | Same CLI, plus `OrdinaryBinaryCover` in both native libraries | One-infinity Mumford arithmetic, rational elliptic point-class pullbacks, rational source-point pushforward, and typed pull/push witnesses are supported. Arbitrary Jacobian-class pushforward is unsupported. |
| Arithmetic on a supplied odd-prime genus-g hyperelliptic curve | `crypto`: `hyperelliptic-cover arithmetic` with `odd_curve` | Monic squarefree `f` of degree `2g+1`, one rational infinity point, positive genus, and deterministically checked odd prime of at most 64 bits. This alone supplies no elliptic transfer. |
| Other checked binary hyperelliptic models | `HyperellipticCurve::try_new`, `MumfordDivisor` in both libraries | Use the checked odd-degree, one-infinity API; binary field degree is bounded by 4096. The cover CLI's binary `model` selector reconstructs only its fixed genus-3 family. |
| CM polarization on `E^2` | `crypto`: `jacobian-certificate` | Bounded exact Hermitian-lattice calculation; geometric existence is conditional. It emits no curve equation or subgroup map. |
| Binary genus-2 gluing, arbitrary correspondences, nonhyperelliptic curves, other infinity models | Construction workflow below | Inspect existing native support, then implement and verify the missing components within the requested scope. Mark unconstructed maps and unperformed runs explicitly. |

In `crypto`, build the registered binaries from that checkout if they are not
already available:

```sh
cargo build --release --locked --manifest-path Cargo.toml \
  --bin hyperelliptic-cover --bin jacobian-certificate
```

A matching packaged executable can also be invoked directly. Select its
location explicitly; do not use an unrelated binary from PATH. Record its
revision or digest and confirm `--help` matches the documented interface.
If a build fails, retain the compiler error and distinguish that execution
blocker from mathematical nonexistence.

```sh
hyperelliptic_cli=./target/release/hyperelliptic-cover
jacobian_cli=./target/release/jacobian-certificate
surface_run_dir="$(mktemp -d "${TMPDIR:-/tmp}/ecdlp-jacobians.XXXXXX")"
"$hyperelliptic_cli" --help
```

In `cryptanalysis`, the bounded mirror is in `suite/src/binary_ecc/` and
`suite/src/prime_hyperelliptic/`. It has no `hyperelliptic-cover` or
`jacobian-certificate` CLI. Use the sibling `crypto` checkout or a matching
packaged executable for those commands, and use the mirror's native APIs for
transfer work. Source parity is an implementation check, not proof that a
particular subgroup transfer was executed:

```sh
cargo run --release --locked --manifest-path suite/Cargo.toml \
  --bin hyperelliptic-source-parity --
```

Read the mirror's [supported boundary](https://github.com/aburan28/cryptanalysis/blob/abc266927f22047ea33ae315860b28e311149c9b/experiments/hyperelliptic-cover-infrastructure/README.md).
For sparse checkouts, locate tracked paths before treating files as absent and
follow that repository's sparse-checkout instructions.

## Require a group-preserving transfer

For a smooth genus-g curve `C`, the group is `J(C)=Pic^0(C)`. Freeze the exact
field and basis, both curve models, genus, infinity configuration, source
prime subgroup order r, generator P, and target Q. The same characteristic
or extension degree alone does not identify a field representation.

Require an explicit homomorphism `i:E -> J(C)` with trivial kernel on
`<P>`. Then `Q=kP` implies `i(Q)=k*i(P)`. A morphism `phi:C -> E` of degree d
provides pullback and norm maps satisfying `phi_* phi^*=[d]`; if `gcd(d,r)=1`,
pullback is injective on the order-r subgroup. Account for any required
`d^-1 mod r` normalization. If d and r share a factor, the composition does
not establish injectivity; inspect the actual kernel intersection.

Check source membership in the actual cyclic subgroup, validity of reduced
divisors, nonidentity of `i(P)`, its exact order r, exceptional points, and
addition/scalar compatibility. A known-answer Q is a correctness control.
Checking only `rQ=O` is insufficient when rational r-torsion has rank two.
Map-domain checks must include the origin and ramified fibers; a sampled
identity does not replace the algebraic homomorphism argument.

For hyperelliptic models `v^2+h(u)*v=f(u)`, the one-infinity implementation uses
canonical Mumford pairs `(U,V)`, with U monic, `deg U<=g`, `deg V<deg U`, and
`U` dividing `V^2+h*V-f`. Coefficient arrays are in ascending powers; the
zero polynomial is `[]` and redundant trailing zeros are invalid. Infinity
and divisor conventions must match the curve. Do not apply this representation
to a two-infinity cover or a nonhyperelliptic curve without the required adapter.

A Kummer model `J(C)/{+1,-1}` identifies opposite divisor classes. Its
differential addition does not supply an ordinary group law on every Kummer
point. Keep sign/lift information and scalar ambiguity explicit in any transfer.

## Construct and replay a cover

`construct` accepts the bare elliptic model object, not an EC1 record or a
registry row. `verify` accepts exactly `{model,certificate}`. The documented
model inputs, arithmetic requests, and output statuses are in the
[CLI wire contract](https://github.com/aburan28/crypto/blob/a575f1a57d3e0f2c37fc2046a6bfa09cbb1db203/docs/curves/HYPERELLIPTIC_INFRASTRUCTURE.md).
Use a fresh directory; preserve frozen catalogs and evidence.

The public odd-prime demonstration from the surface skill is:

```json
{"v":"1","form":"y^2=x^3+a*x+b","p":"101","field":"fp-101","a":"1","b":"46"}
```

For characteristic greater than three, the fixed genus-2 family is
`C: v^2=F(u^2+c)`, with `F(x)=x^3+a*x+b`, the first c in `{0,1,2,3}` with
`F(c)!=0`, and `phi(u,v)=(u^2+c,v)`. This is a cover construction, not the
implemented one-infinity arithmetic model.

For the pinned n=83 a=0 curve, the exact bare model is:

```json
{"v":"1","form":"y^2+xy=x^3+a*x^2+b","modulus":"0x800000000200000000007","field":"f2m-83-a1d5abfa","a":"0x0","b":"0x1"}
```

For a=1, change only `a` to `"0x1"`. The modulus encodes
`z^83+z^45+z^2+z+1`. The CLI's field label uses the first eight SHA-256 hex
digits of `f2m-modulus:0x800000000200000000007`; it is not the EC1 field-record
digest. Copy the requested model into `$surface_run_dir/model.json`, then run:

```sh
"$hyperelliptic_cli" construct \
  --input "$surface_run_dir/model.json" --output "$surface_run_dir/cover.json"
jq -e '.status == "ok"' "$surface_run_dir/cover.json"
jq '.result | {model,certificate}' "$surface_run_dir/cover.json" \
  > "$surface_run_dir/verify.json"
"$hyperelliptic_cli" verify \
  --input "$surface_run_dir/verify.json" --output "$surface_run_dir/verified.json"
```

The ordinary binary family, with `d=sqrt(b)`, is
`C: v^2+u^2*v=u^7+a*u^4+d*u` and `phi(u,v)=(u^3,u*v+d)`. For the n=83
fixtures b=d=1. Successful construction verifies genus three and map degree
three. It accepts no subgroup order and makes no unconditional subgroup claim.
The prior n=83 surface run did not execute this Jacobian transfer.

## Call divisor arithmetic and binary pullback

For the constructed binary cover, form a complete identity request:

```sh
jq '{schema:"hyperelliptic-jacobian-operation/v1",model:.,operation:"identity"}' \
  "$surface_run_dir/model.json" > "$surface_run_dir/operation.json"
"$hyperelliptic_cli" arithmetic \
  --input "$surface_run_dir/operation.json" --output "$surface_run_dir/identity.json"
```

Supported operations are `validate`, `identity`, `equal`, `negate`, `add`, and
`scalar_multiply`. Supply canonical `left` and `right` divisors as required;
`scalar_multiply` also requires an unsigned decimal or `0x` string `scalar`.
An identity calculation only initializes arithmetic; it is not a transfer test.

The CLI has no pullback or transfer subcommand. In native Rust, import
`OrdinaryBinaryCover` and the field/point types from `crypto_lib::binary_ecc`
or `cryptanalysis_suite::binary_ecc`, then use these checked entry points:

1. `OrdinaryBinaryCover::new(m, irreducible, a, b)` and `verify_certificate()`.
2. `pullback_point_class(&P)` and `pullback_point_class(&Q)` to obtain divisor
   classes; `pull_push_composition_certificate(&P)` for the typed degree-three
   composition witness. Use the declared exact field for both points.
3. `subgroup_transfer_status(&r)` after independently establishing the exact
   source subgroup order. Its `InjectiveIfExactSubgroupOrder` result is
   conditional, not a primality or order proof. The n=83 fixture primes are
   coprime to three, but their actual pullbacks must still be checked in a run.
4. Use checked `MumfordDivisor` operations to test image order, addition, and
   a supplied scalar witness. Report algebraic, sampled, and executed checks
   separately, including the ramified two-torsion and infinity cases.

`pushforward_rational_point_divisor` handles rational source-point classes.
`pushforward_arbitrary_jacobian_class` returns an explicit unsupported result.
Do not use the typed pullback witness as a norm for arbitrary classes produced
by a relation collector. An end-to-end solver requiring that norm needs its
own verified implementation.

For separate genus-2 odd-prime arithmetic, this complete request validates the
branch-point divisor on `v^2=u^5+u` over F5. It is a demonstration, not an n=83
model or a transfer from the supplied elliptic curve:

```json
{"schema":"hyperelliptic-jacobian-operation/v1","odd_curve":{"family":"odd_prime_one_infinity_v1","p":"5","genus":2,"f":["0","1","0","0","0","1"],"infinity":"one_rational"},"operation":"validate","left":{"u":["0","1"],"v":[]}}
```

Save it to a fresh operation file and invoke the same `arithmetic` command.
For higher genus, use the caller's checked monic squarefree polynomial of exact
degree `2g+1`; changing only the `genus` field does not change the curve.

## Search other genus-2 and higher targets

For genus 2, separate two search routes:

- **Torsion gluing:** select E' and a suitable Galois-equivariant
  anti-isometry on prime-to-characteristic torsion; construct the quotient of
  `E x E'` by its graph. Verify the induced principal polarization is
  geometrically indecomposable, construct the smooth genus-2 curve over the
  declared field, and give the explicit elliptic-factor map. In characteristic
  two, use a characteristic-two-compatible construction; odd-characteristic
  2-gluing/Richelot formulas cannot be applied unchanged. Check the quotient
  kernel on the chosen order-r subgroup; choosing gluing order coprime to r
  supplies the relevant isogeny injectivity condition.
- **CM polarization:** for a supplied `jacobian-candidates/v1` file, run the
  bounded native lattice checker into fresh outputs:

```sh
"$jacobian_cli" --input candidates.json \
  --output "$surface_run_dir/polarizations.json" --budget 2000000
```

Follow its [certificate contract](https://github.com/aburan28/crypto/blob/a575f1a57d3e0f2c37fc2046a6bfa09cbb1db203/docs/curves/JACOBIAN_CERTIFICATES.md).
Bounds include fundamental discriminant `-1000000<=D<=-3`, `1<=a,d<=1000`,
and `|b_i|<=1000`. Independently establish ordinarity, the actual geometric
maximal endomorphism order, and its action over the base field before applying
the geometric consequence. `conditional_existence` is not an explicit curve,
map, or subgroup certificate, and `exists_over_base_field` remains null.
Metadata binding alone does not verify those hypotheses. Budget exhaustion or
a rejected lattice does not rule out other polarizations or covers.

For any same-field genus-g Jacobian candidate, the elliptic Frobenius quadratic
must divide its degree-2g Frobenius polynomial over the integers for a nonzero
homomorphism from E. This is a necessary filter, not a curve or map construction.
The existing `frobenius_filter` handles only degree four and its documented
u64/i128 range; it cannot test arbitrary genus or q=2^83. Preserve trace signs
and use an appropriate checked native integer backend for a broader filter.

A product or a compatible characteristic polynomial does not establish a
smooth Jacobian with the required polarization. In higher dimension, even a
principally polarized abelian variety need not be a Jacobian. Obtain actual
curve equations and explicit divisor maps; require the correct arithmetic
backend for nonhyperelliptic curves. Preserve bounded failures and distinguish
construction gaps, untested hypotheses, and proved obstructions.

## Validate and report

Cover CLI responses use `ok`/exit 0, `unsupported`/exit 2, `invalid_input`/exit 3,
and `error`/exit 1. Inspect the result's individual geometry, arithmetic, and
subgroup fields as well as the exit status. These statuses differ from the
standalone surface CLIs; do not reuse their exit-code interpretation.

Run relevant native tests after changing higher-genus implementations. In
`crypto`, the existing targets include `cargo test --release --locked --bin
hyperelliptic-cover`, `cargo test --release --locked --bin jacobian-certificate`,
and the binary `cover_transfer` and hyperelliptic library tests. Replay the
matching certificates and exact subgroup checks; a surface test pass does not
validate the Jacobian path. The toy BSGS/rho solvers are exponential; invoking
them at n=83 is not evidence of a new transfer or a scalable destination solver.

Report construction, executable map, kernel/subgroup preservation, arithmetic,
destination solving, scalar recovery, and measured costs separately. Before
calling a route faster, include discovery/setup, transfer, relation collection,
linear algebra, descent, norm/projection, verification, failed attempts, memory,
and a matched elliptic reference on the same subgroup and targets. A reduction
to a higher-genus Jacobian alone establishes no speedup.

This reference documents existing contracts and pending construction routes;
its example commands are not receipts of new higher-genus runs. For requested
research runs, preserve a protocol and raw evidence and follow the repository's
report-evidence and research-visuals workflows. Existing construction proofs
are documented in [COVERS.md](https://github.com/aburan28/crypto/blob/a575f1a57d3e0f2c37fc2046a6bfa09cbb1db203/docs/curves/COVERS.md).
