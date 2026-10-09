# Complete Eisenstein tau scalar evaluator on secp256k1

The native evaluator now computes `[k]G` entirely in the balanced
`Z[omega]/(pi)` Montgomery field after scalar recoding. It combines a short
two-dimensional subgroup-lattice representative, a terminating signed
base-`tau` expansion, the five-product deferred-normalization `tau` point
step, and native Jacobian mixed addition. The independent replay verified
all 73 supplied scalars, including 48 seeded full-width random scalars,
against affine secp256k1 multiplication.

## Scalar expansion

Let `tau = 1 - omega`, so `tau^2 - 3*tau + 3 = 0`. In the basis `(1,tau)`,
the norm is `N(a+b*tau) = a^2 + 3ab + 3b^2`. The frozen kernel lattice from
the existing scalar recoder maps `k mod n` to a short `(a,b)` satisfying
`a + b*lambda_tau = k (mod n)`. The 25 nearby lattice choices are ranked by
this exact norm and then maximum coefficient magnitude. This integer
preparation runs before the point loop.

For each nonzero, nonunit pair, choose `d` in `{-1,0,1}` with `d = a (mod 3)`.
After subtracting `d`, divide exactly by `tau`:

```text
tau * (c + d*tau) = -3d + (c+3d)*tau
(a+b*tau - digit)/tau = (a-digit+b) - ((a-digit)/3)*tau
```

The six norm-one terminal pairs represent `+/-1`, `+/-omega`, and
`+/-omega^2`. They seed the accumulator using the curve map
`(x,y) -> (beta*x,y)`; each digit is then replayed in reverse with one
`tau` point step and, for a nonzero digit, a mixed addition of `+/-G`.
The loop includes the equal-point and inverse-point cases.

This radix terminates for every integer pair. Outside zero and the six
units, an Eisenstein norm is at least three. Division gives
`N(next) = N(z-digit)/3`. The triangle inequality bounds the numerator by
`(sqrt(N(z))+1)^2`, which is strictly below `3*N(z)` for `N(z) >= 3`.
Thus the positive integer norm decreases at every step. The native debug
build asserts this descent; a grid of 6,561 signed pairs reconstructed
exactly from their digits and terminal unit.

## Native arithmetic path and replay

The field modulus is the secp256k1 prime
`p = 2^256 - 2^32 - 977`, with
`pi = 64502973549206556628585045361533709078 -
303414439467246543595250775667605759171*omega`.
The point curve is `y^2 = x^3 + 7`; the scalar modulus is
`n = fffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141`
in hexadecimal. The complete point loop uses fixed-width signed coefficient
arithmetic. The `tau` step uses five raw field products and three final
balances; the current mixed-add formula uses eleven balanced field products.
Input scalar parsing and short-lattice search use arbitrary-precision
integers outside the point loop. This research binary has data-dependent
branches and is intended for public-scalar experiments.

Run from this directory:

```sh
cargo build --release --bin eisenstein_fixed
cargo test --release --bin eisenstein_fixed
cargo test --bin eisenstein_fixed signed_tau_digits_reconstruct_small_eisenstein_pairs
python3 check_eisenstein_scalar_fixed.py
python3 check_eisenstein_tau_fixed.py
python3 check_eisenstein_fixed.py --random-pairs 10000
```

The scalar verifier (seed `20261011`) checked 25 boundary/structured
scalars and 48 random scalars. It checked lattice congruence, balanced output
coordinates, the affine curve equation, and the exact point from an
independent Python double-and-add oracle. The random scalars used 7,662
`tau` steps and 5,106 nonzero digits in total: means of 159.625 steps and
106.375 additions per scalar. Across all 73 cases, the maxima were 161
steps and 119 nonzero digits. The release Rust test suite passed 27 tests;
the existing field and `tau` replays passed 10,121 input pairs times five
operations and 6,111 output coordinates, respectively. The release binary
SHA-256 for this replay was
`af2c30ca18e871b5a88848b307545a23df6d2dac9c805e146a3f10faaa73b881`.

The next implementation step is to reduce the eleven balanced products and
repeated normalization in mixed addition. A paired wall-time comparison
with the conventional secp256k1 evaluator requires a qualifying isolated
host receipt under [the CPU benchmark protocol](../../docs/ISOLATED_BENCHMARKS.md).
