---
name: ecdlp-surfaces
description: Select, run, and interpret elliptic-curve surface and genus-2+ Jacobian transfer tools. Use for quadric pencils, quartic subgroup transfers, GF(2^83) Koblitz a=0/a=1 checks, hyperelliptic covers, Mumford arithmetic, genus-2 gluing or polarization candidates, higher-genus ECDLP transfers, and Frobenius-factor checks. Also use when the user names surface_search, transfer_check, binary_surface_check, frobenius_filter, hyperelliptic-cover, or jacobian-certificate.
---

# Elliptic-curve surfaces and Jacobian transfers

## Choose the tool

| Request | Tool | What the result establishes |
| --- | --- | --- |
| Find surfaces containing an elliptic curve in another model | `surface_search` | Enumerates the finite quadric pencil through the explicit quartic embedding and classifies smooth and split members. |
| Check whether that representation preserves a supplied ECDLP subgroup | `transfer_check` | Checks prime order, actual cyclic-subgroup membership, inverse round trips, and preservation of the generator's order. |
| Check a proposed abelian surface's Frobenius compatibility | `frobenius_filter` | Tests necessary polynomial conditions for an elliptic factor; it supplies no homomorphism or subgroup certificate. |
| Check the repository's n=83 binary Koblitz variants | `binary_surface_check` | Uses the pinned GF(2^83) basis and subgroups, classifies the binary pencil analytically, verifies quartic transfers, and checks the same/opposite products. |
| Construct or replay a supported genus-2 or genus-3 cover | `hyperelliptic-cover construct` / `verify` in `crypto` | Checks the fixed cover's equation, smoothness, genus, degree, and field; subgroup preservation is a separate obligation. |
| Compute with supported genus-2+ divisor classes | `hyperelliptic-cover arithmetic`, or the native Jacobian APIs | Checks Mumford arithmetic in the declared curve and infinity model; it does not construct an elliptic-subgroup map. |
| Transfer into the binary genus-3 Jacobian | `OrdinaryBinaryCover` Rust API in both repositories | Constructs rational-point-class pullbacks and typed degree-three composition witnesses; injectivity requires an independently verified exact subgroup order coprime to three. |
| Check a supplied CM genus-2 polarization candidate | `jacobian-certificate` in `crypto` | Certifies bounded Hermitian-lattice findings; genus-2 existence remains conditional on independently audited geometric hypotheses. |
| Search for genus-2 gluing or other higher-genus targets | [Higher-genus workflow](references/higher-genus.md) | Routes construction, map, kernel, arithmetic, and cost checks; a search proposal is not an executable transfer. |

Use this skill when the user requests these operations, asks about genus 2 or
higher for ECDLP transfers, or names a CLI above. Read the
[higher-genus reference](references/higher-genus.md) before selecting a Jacobian,
cover, gluing, polarization, or divisor-arithmetic path.

The standalone `tools/ecdlp-surfaces` crate implements the fixed quartic-model
transfer and pinned binary product checks. Higher-genus work uses the separate
tools and APIs above. It does not extend that crate's CLI input bounds.
Arbitrary maps, general deformation searches, and unsupported field or infinity
models require further implementation. Keep the user's requested case open and
identify its exact remaining construction or validation step.

## Prepare the input

1. Work at the root of the requested checkout containing
   `tools/ecdlp-surfaces/Cargo.toml`. Both `crypto` and `cryptanalysis` contain
   the same tool. In a workspace with both, select the repository the user named.
2. Read its `AGENTS.md` and the [CLI README](../../../tools/ecdlp-surfaces/README.md).
   The standalone surface crate needs Rust 1.70 or newer, is dependency-free,
   and has its own workspace; use `--manifest-path` below to select it.
   Higher-genus tools use their own checkout's toolchain and Cargo manifest.
3. For the odd-prime point operations, require a nonsingular short Weierstrass model
   `y^2 = x^3 + a*x + b` over a prime field with `3 < p <= 10,000`.
   A general genus-one curve first needs an elliptic-curve model with a chosen
   rational origin; this tool does not perform that conversion.
   For a binary n=83 surface request, use the dedicated section below. For a
   genus-2+ request, follow the higher-genus reference and record the target
   curve's model, genus, infinity configuration, Jacobian representation, and
   explicit map domain as well. In binary-curve
   notation n or m is the extension degree; GF(2^83) and F_83 are different
   inputs. Clarify ambiguous field notation before selecting a CLI.
4. For a supplied odd-prime quartic transfer, record the exact field, `a`, `b`, prime subgroup
   order `r`, generator `P`, and target `Q`. Use `x,y` for affine points and `O`
   for the origin. Coordinates are reduced modulo `p`. An unknown scalar is
   allowed; omit `--scalar`. Do not silently replace supplied parameters with
   defaults. If an illustration is requested without parameters, label the
   public fixture below as a demonstration.
5. For the standalone degree-four polynomial filter, require a finite-field size `q`, the
   source trace `t`, and four coefficients `c1,c2,c3,c4` for
   `T^4+c1*T^3+c2*T^2+c3*T+c4`. The caller must establish the source trace and
   prime-power field size. The filter uses checked `i128` arithmetic and
   accepts `q <= i64::MAX`; arithmetic overflow is an error.

## Run the public demonstration

The fixture is `E/F_101: y^2=x^3+x+46`, with `#E=109`, `P=(2,37)`, and
`Q=(64,19)=37P`. Use a fresh output directory so frozen examples remain intact:

```sh
surface_run_dir="$(mktemp -d "${TMPDIR:-/tmp}/ecdlp-surfaces.XXXXXX")"
```

Find the containing quadrics:

```sh
cargo run --release --offline --locked \
  --manifest-path tools/ecdlp-surfaces/Cargo.toml --bin surface_search -- \
  --prime 101 --a 1 --b 46 --scalar 37 \
  --output "$surface_run_dir/surfaces.json"
```

Check the supplied subgroup without a scalar witness:

```sh
cargo run --release --offline --locked \
  --manifest-path tools/ecdlp-surfaces/Cargo.toml --bin transfer_check -- \
  --prime 101 --a 1 --b 46 --r 109 --p-point 2,37 --q-point 64,19 \
  --output "$surface_run_dir/transfer.json"
```

Add `--scalar 37` only to check the known-answer relation. Membership is checked
by enumerating the small subgroup; the command does not return a discrete log.

Filter the compatible polynomial `(T^2+7*T+101)^2`:

```sh
cargo run --release --offline --locked \
  --manifest-path tools/ecdlp-surfaces/Cargo.toml --bin frobenius_filter -- \
  --q 101 --trace=-7 --coeffs 14,251,1414,10201 \
  --output "$surface_run_dir/frobenius.json"
```

For a negative control, use `--coeffs 0,202,0,10201` with the same `q` and trace
and a separate output file. Each CLI accepts `--help`; omitting `--output`
prints JSON to stdout. Malformed or invalid inputs exit with status 2. A valid
but incompatible polynomial exits successfully with
`passes_necessary_conditions: false`; inspect the JSON, not only the exit code.

## Run the n=83 binary checks

For `y^2+xy=x^3+a*x^2+1` over GF(2^83), use the pinned presets:

```sh
cargo run --release --offline --locked \
  --manifest-path tools/ecdlp-surfaces/Cargo.toml --bin binary_surface_check -- \
  --degree 83 --a both --output "$surface_run_dir/n83.json"
```

Select `--a 0` or `--a 1` when only one is requested. The exact basis is
`z^83+z^45+z^2+z+1`; generators, r and cofactors are fixed by the cited fixtures.
Default Q is the public known-answer 37P. To check a supplied public Q, select
one variant and add `--q-point 0xX,0xY` or `O`; omit `--scalar` if the log is
unknown. Scalars are nonnegative u128 integers. Confirm that the caller's
basis, model, subgroup and generator match before running. A different basis
or generator needs an explicit verified conversion; do not reinterpret masks.

Require modulus irreducibility, `rP=O`, `rQ=O`, a nonidentity P, and the round-trip
checks to pass. The known group order `r*h` and `gcd(r,h)=1` supply a unique
order-r subgroup using the cited prime r, so this path avoids subgroup
enumeration. The a=0 primality proof is reused from an existing Sage receipt;
the output reports a=1's additional deterministic u64 check separately.

The binary pencil uses `Q1=WZ+X^2` and
`Q2=Y^2+XY+XZ+aWZ+W^2`. Smooth members have `lambda != a`; split members have
`Tr(lambda+1/(lambda+a)^2)=0`. Counts are derived algebraically, with small-field
exhaustive controls, not a scan of 2^83 parameters. The group law on quadrics
remains confined to the curve image. Inclusion into the same curve's `E x E`
preserves the ambient group law, as does inclusion into the matching factor of
the mixed `E_0 x E_1`. The opposite product is rejected over this
field because its Frobenius quadratic is coprime to the source's and its point
order lacks the source prime.

Frobenius characteristic polynomials have integer coefficients: preserve their
trace signs when comparing a=0 and a=1. Large exact integers are JSON decimal
strings; field elements are hexadecimal masks. The general `frobenius_filter`
still has its documented u64/i128 limits. The binary command handles these
specific product tests and does not construct arbitrary surface maps.

The [n=83 protocol](../../../research/ecdlp_surfaces_n83_20261012/PROTOCOL.md)
records the scope. The archived a=1 benchmark uses another polynomial basis;
its points and curve identity are kept separate from these presets.

## Route genus 2 and higher

The group law is on `J(C) = Pic^0(C)`, not on the points of a genus-2+ curve.
Require an explicit homomorphism `i: E -> J(C)` that is injective on the chosen
order-r subgroup before calling the result an ECDLP transfer. For a cover
`phi: C -> E` of degree d, use the induced pullback and norm with
`phi_* phi^* = [d]`; `gcd(d,r)=1` gives injectivity on that subgroup.
Do not confuse the map `C -> E` with an inverse point map `E -> C`.

For either n=83 variant, the existing binary family is
`C_a: v^2+u^2*v=u^7+a*u^4+u`, with
`phi(u,v)=(u^3,u*v+1)`. It is a same-field genus-3 construction. The n=83
surface study did not run its Jacobian pullbacks; preserve that execution gap
until the requested native transfer checks are performed. The reference gives
exact model JSON and library entry points for doing so.

For genus 2, distinguish the existing odd-characteristic degree-two cover,
conditional CM polarization checks, and a proposed binary torsion-gluing
construction. A product `E x E'` or passing Frobenius polynomial is not a
certificate of a smooth genus-2 curve and its explicit subgroup map.
The reference covers higher genus, nonhyperelliptic targets, Kummer quotients,
kernel checks, unsupported operations, and complete solver-cost accounting.

## Interpret the output

- For the fixture, `surface_search` reports 101 smooth finite quadrics and 54
  split quadrics. These counts depend on the source curve. The singular pencil
  member at infinity is excluded. The search selects its own largest-prime
  subgroup for its demonstration; use `transfer_check` for user-supplied points.
- The embedding is `(x,y) -> [1:x:y:x^2]`, with `O -> [0:0:0:1]`.
  The group law lives on the curve image, the intersection of two quadrics.
  `ambient_quadric_group_law` is false. A containing quadric is not an abelian
  surface. The separately described map `P -> (P,O)` into `E x E` does preserve
  a componentwise ambient group law.
- Require `P_has_prime_order_r`, `Q_in_generated_subgroup`, and both round-trip
  fields in a transfer report to be true, with `image_P_order = r`.
  Without a witness, `scalar_mod_r` and `scalar_relation_verified` are null.
  Checking only `rQ=O` would not establish membership when rational torsion
  has rank two; the checker verifies membership in the actual cyclic subgroup.
- A Frobenius report must pass divisibility, reciprocity, quotient shape, and
  the quotient Hasse bound to set `passes_necessary_conditions` true.
  `subgroup_transfer_certified` remains false. Passing does not prove existence
  of a target variety, construct a map, determine its kernel, or show injectivity
  on the ECDLP subgroup. Rejecting a polynomial only rejects that supplied input.
- An equivalent representation preserves the same ECDLP. For a higher-genus
  destination, curve construction, Jacobian arithmetic, subgroup transfer, and
  a faster target solver with complete transport costs are separate claims.
  The point arithmetic is variable-time demonstration code.

## Validate and hand off

Run the existing package checks after changing the tool or its fixtures:

```sh
tools/ecdlp-surfaces/check.sh
```

This checks formatting, release tests, Clippy, example replay, and invalid-input
controls. Do not regenerate committed examples just to collect a new run.
For changes to higher-genus implementations, run the relevant existing native
cover/Jacobian tests and replay the matching geometry and transfer receipts;
the surface package checks do not validate those separate implementations.
For an algebraic-identity replay, follow the
[certificate README](../../../docs/ecdlp-surfaces/certificates/README.md) and
write generated evidence to a fresh directory. Those certificates concern the
embedding and determinant identities; they do not certify an arbitrary surface
transfer or constitute an independent-host replay.

Report the selected tool, exact input, command, exit status, output paths, and
what was established. Preserve failures and remaining gaps. For substantive
research, follow the repository's research-visuals and report-evidence rules
where present. Refer to the [integration report](../../../docs/ecdlp-surfaces/REPORT.md)
and [protocol](../../../docs/ecdlp-surfaces/PROTOCOL.md) for the existing evidence.
