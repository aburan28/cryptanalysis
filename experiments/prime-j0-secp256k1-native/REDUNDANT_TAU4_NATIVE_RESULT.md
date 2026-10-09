# Native redundant tau-four scalar path

The native secp256k1 fixed-generator path now evaluates the two-orbit
`tau^4` digit set with depth-two rollout. Its recoding exactly matches the
frozen Python screen on 214 scalars: the Eisenstein representative, number
of `tau` steps, mixed additions, and alternate-digit uses agree in every
case. Each resulting point matches an independent Python scalar
multiplication. The 36 release-mode Rust tests pass, including small-pair
reconstruction and all 18 affine seed points against the existing signed
digit scalar path.

## Operation accounting

On the existing 86-scalar fixed-generator fixture, the native path executes
10,938 `tau` steps and 2,256 mixed additions after the terminal point.
The source point-formula proxy is `5 * 10,938 + 11 * 2,256 = 79,506`
field-product units. The earlier fixed-generator affine width-three path
uses 11,119 `tau` steps, 3,125 mixed additions, and 89,970 units on the
same fixture. The source point-formula reduction is 10,464 units (11.63%).
On the separate 128-scalar holdout panel, the new path has 20,084 `tau`
steps, 4,180 mixed additions, and 146,400 units. These counts omit integer
recoding, table lookup, and affine point conversion; they do not establish
a CPU time ratio.

The 18 affine seed points and their signed unit orbits are cached once per
process. Table construction uses one `tau` step for the generator, 116
`add_mixed` calls in seed construction (the first call for each seed merely
sets an identity accumulator), 19 affine inversions, and 36 `omega`
applications. The single-scalar online interval excludes this reusable
fixed-generator preparation. The benchmark case command starts timing
after fixture loading, scalar parsing, and table preparation; it includes
short-representative selection, integer recoding, point evaluation,
affine conversion, and fixture equality checking. A cold-start experiment
must charge the table preparation separately.

## Reproduction

```sh
cd experiments/prime-j0-secp256k1-native
cargo test --release --bin eisenstein_fixed
cargo build --release --bin eisenstein_fixed
PYTHONDONTWRITEBYTECODE=1 python3 check_redundant_tau4_native.py
target/release/eisenstein_fixed --check-scalar-w4-redundant-case eisenstein-pair-fixture.json 85
target/release/eisenstein_fixed --benchmark-scalar-w4-redundant-case eisenstein-pair-fixture.json 85
```

Batch scalar input uses `--scalar-w4-redundant` and emits the representative,
point, `tau_steps`, `nonzero_digits`, `alternate_uses`, and 18 orbit counts.
Digit selection uses variable-time integer branches and hash maps, as is
appropriate for this public-scalar research executable.
The checked-in replay script reads the `cases` array in
[`redundant-tau4-result.json`](redundant-tau4-result.json), feeds its scalars
to that mode, compares all recoding counts to `rollout_2`, and compares
every point with `lazy_tau_screen.point_multiply`. It passed with no
mismatches. Its SHA-256 is
`0be937aded9cb40ac3c74c4658c9930b69d0056f3d40faaccc33035ba3ecd0f0`.
The verified Rust source SHA-256 is
`7adeb7b55356fd4e458a1637c7d5f4c4a3745c5bb52c8acc1249aa4aafacb6ab`;
the release executable SHA-256 is
`6005181ffeb9ebabb89c468251262d8d6e1f5c3444d32da356eff909e76a64f7`.

The next engineering step is to reduce depth-two integer recoding cost,
then compare paired full-operation wall times on an isolated host with a
passing receipt from [`docs/ISOLATED_BENCHMARKS.md`](../../docs/ISOLATED_BENCHMARKS.md).
The current RunPod container's strict preflight rejected CPU timing, so
its online speedup field remains unknown.
