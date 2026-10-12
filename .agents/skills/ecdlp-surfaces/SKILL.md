---
name: ecdlp-surfaces
description: Run and interpret the Rust elliptic-curve surface tools. Use for small-prime quadric-pencil searches, quartic-model ECDLP subgroup transfers, or necessary Frobenius-factor checks for candidate abelian surfaces, and when the user names surface_search, transfer_check, or frobenius_filter.
---

# Elliptic-curve surface tools

## Choose the tool

| Request | Tool | What the result establishes |
| --- | --- | --- |
| Find surfaces containing an elliptic curve in another model | `surface_search` | Enumerates the finite quadric pencil through the explicit quartic embedding and classifies smooth and split members. |
| Check whether that representation preserves a supplied ECDLP subgroup | `transfer_check` | Checks prime order, actual cyclic-subgroup membership, inverse round trips, and preservation of the generator's order. |
| Check a proposed abelian surface's Frobenius compatibility | `frobenius_filter` | Tests necessary polynomial conditions for an elliptic factor; it supplies no homomorphism or subgroup certificate. |

Use this skill when the user requests these operations or names a CLI above.
The implemented transfer is the fixed quartic-model embedding, not a search
over arbitrary maps. General high-genus models, deformation searches, extension
fields, and cryptographic-size point arithmetic need other implementations.
Keep any broader requested task open and state the precise implementation gap.

## Prepare the input

1. Work at the root of the requested checkout containing
   `tools/ecdlp-surfaces/Cargo.toml`. Both `crypto` and `cryptanalysis` contain
   the same tool. In a workspace with both, select the repository the user named.
2. Read its `AGENTS.md` and the [CLI README](../../../tools/ecdlp-surfaces/README.md).
   Use Rust 1.70 or newer. The main crate is dependency-free and has its own
   workspace; use `--manifest-path` as below to select it explicitly.
3. For point operations, require a nonsingular short Weierstrass model
   `y^2 = x^3 + a*x + b` over a prime field with `3 < p <= 10,000`.
   A general genus-one curve first needs an elliptic-curve model with a chosen
   rational origin; this tool does not perform that conversion.
4. For a supplied transfer, record the exact field, `a`, `b`, prime subgroup
   order `r`, generator `P`, and target `Q`. Use `x,y` for affine points and `O`
   for the origin. Coordinates are reduced modulo `p`. An unknown scalar is
   allowed; omit `--scalar`. Do not silently replace supplied parameters with
   defaults. If an illustration is requested without parameters, label the
   public fixture below as a demonstration.
5. For polynomial filtering, require an actual finite-field size `q`, the
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
- An equivalent representation preserves the same ECDLP. A faster target
  solver and its complete transport costs are separate, unimplemented work.
  The point arithmetic is variable-time demonstration code.

## Validate and hand off

Run the existing package checks after changing the tool or its fixtures:

```sh
tools/ecdlp-surfaces/check.sh
```

This checks formatting, release tests, Clippy, example replay, and invalid-input
controls. Do not regenerate committed examples just to collect a new run.
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
