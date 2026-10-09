# Complete Eisenstein tau scalar evaluator on secp256k1

The native evaluator computes `[k]G` entirely in the balanced
`Z[omega]/(pi)` Montgomery field after scalar recoding. It combines a short
two-dimensional subgroup-lattice representative, terminating signed
base-`tau` digits, the five-product deferred-normalization `tau` point step,
and native Jacobian mixed addition. A width-two unit digit set reduced mixed
additions from 5,106 to 3,068 over the same 48 full-width random scalars
while preserving the exact point in all 73 replay cases.

Xu, Yu, Han, and Lu's supplied manuscript, *On Efficient Computations of
`y^2=x^3+b/Fp` for Primes `p≡1 (mod 3)`*, establishes the `tau=1-omega`
point map, window `tau`-NAF, and unit-invariant precomputation for this curve
family. Earlier work also studies Eisenstein-integer scalar expansions.
The implementation contribution here is the complete coupling of a native
Eisenstein Montgomery field, deferred field normalization in the `tau` map,
and a verified scalar loop. The signed width-one loop is a correctness
control for that field representation. The width-two mode uses the
three-point unit orbit; larger window sets and their unit-invariant
precomputation remain the next recoding step.

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

The width-two mode chooses one of the six units as its nonzero digit. Since
`tau^2` is a unit multiple of `3`, reduction modulo `tau^2` is reduction of
both `(a,b)` coefficients modulo three. The six units give exactly the six
residue pairs with `a` nonzero modulo three. Subtracting the matching unit
makes both coefficients divisible by three, so the following `tau` quotient
has a zero digit. The mode prepares the three affine points
`G`, `omega G`, and `omega^2 G`; a sign change supplies their negatives.
Every two adjacent digits contain at most one nonzero digit.

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
cargo test --bin eisenstein_fixed unit_width_two_digits_are_sparse_and_reconstruct_small_pairs
python3 check_eisenstein_scalar_fixed.py --radix w1
python3 check_eisenstein_scalar_fixed.py --radix w2
python3 check_eisenstein_tau_fixed.py
python3 check_eisenstein_fixed.py --random-pairs 10000
```

The scalar verifier (seed `20261011`) checked 25 boundary/structured
scalars and 48 random scalars in each mode. It checked lattice congruence,
balanced output coordinates, the affine curve equation, and the exact point
from an independent Python double-and-add oracle. The paired random panel
gave:

| Radix | Total tau steps | Total mixed additions | Mean additions/scalar |
| --- | ---: | ---: | ---: |
| Signed width one | 7,662 | 5,106 | 106.375 |
| Unit width two | 7,671 | 3,068 | 63.917 |

The width-two mode removes 2,038 mixed additions, or 39.9%, on this frozen
panel. Its maximum over all 73 cases was 161 tau steps and 70 mixed
additions. These are point-operation counts; the width-two path also prepares
a three-point orbit before its loop. The counts are not a CPU wall-time ratio. The release
Rust test suite passed 28 tests;
the existing field and `tau` replays passed 10,121 input pairs times five
operations and 6,111 output coordinates, respectively. The release binary
SHA-256 for this replay was
`9de1ac039b1b52ba0b1dbb8457915559f504067edfb79fdd2b8624d7023c7c03`.

The next implementation step is to reduce the eleven balanced products and
repeated normalization in mixed addition. A paired wall-time comparison
with the conventional secp256k1 evaluator requires a qualifying isolated
host receipt under [the CPU benchmark protocol](../../docs/ISOLATED_BENCHMARKS.md).
