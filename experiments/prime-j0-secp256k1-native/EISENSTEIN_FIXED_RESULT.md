# Fixed-width Eisenstein field kernel

A standalone Rust kernel now evaluates secp256k1 field multiplication,
addition, subtraction, the cube-root action, and multiplication by
`1-omega` in the balanced two-coordinate Montgomery representation. Its
hot arithmetic uses fixed-size limb arrays; arbitrary-precision integers
appear only in the diagnostic program's decimal input and output. The
cross-language replay matched the exact Python reference on 10,121 input
pairs, checking all five operations for each pair.

## Normalization by linear Voronoi tests

Let `u` be the unbalanced result of Montgomery reduction and
`t = u*conjugate(pi)`. A correction `q = a+b*omega` is nearest to `u/pi` when
all three inequalities hold:

```
|2*t.a - t.b - p*(2*a-b)| <= p
|2*t.b - t.a - p*(2*b-a)| <= p
|t.a + t.b - p*(a+b)|   <= p
```

These are the six faces of the Eisenstein lattice Voronoi cell, expressed
with integer arithmetic. The bound in
[EISENSTEIN_MONTGOMERY_RESULT.md](EISENSTEIN_MONTGOMERY_RESULT.md)
limits `q` to the 13 elements of norm 0, 1, or 3. The kernel checks those
in lexicographic order, which also resolves exact boundary ties. It then
subtracts the selected small multiple of `pi` with additions. Normalization
uses one three-product ring multiplication by the fixed conjugate of `pi`;
it does not evaluate a norm or divide by `p` for every candidate.

For one general field multiplication, the current fixed-width source makes
three ring products, each expressed as three `U256::mul_wide` calls, plus
three low-128-bit wrapping products for Montgomery cancellation. The final
small correction is addition-only. The generic `U256::mul_wide` currently
processes four limbs even when a coefficient occupies two or three, so
specialized limb multiplication and complete point formulas are the next
implementation steps. The `omega` action itself is swaps, subtraction,
and sign changes; `1-omega` then needs the same normalization as addition.

## Reproducible check

From `experiments/prime-j0-secp256k1-native`:

```sh
cargo build --release --bin eisenstein_fixed
cargo test --release --bin eisenstein_fixed
python3 check_eisenstein_fixed.py --random-pairs 10000
```

The check uses seed `20261009`, 121 edge pairs, and 10,000 random pairs.
It compares exact balanced output pairs with the independent Python
reference and also decodes each multiplication to verify its canonical
field product. All 10,121 cases and 50,605 operation outputs matched.
The 24 imported fixed-width integer tests also passed. The checked binary
SHA-256 was
`2bfdc0094f3fe09a2c6fac743550a40e109755b55308bea4d046902a334959d1`;
the reference source SHA-256 was
`ce48d817449b683832cc77cb6f0e8c6bf9851d36a5d7cdad904ba7f575bb72f1`.
This check ran on Darwin arm64 with Rust 1.93.1.

This diagnostic binary branches on field values during sign arithmetic
and correction selection. A production scalar path needs a constant-time
selection policy and full curve-point verification. CPU speed can be
assessed only after the complete point path runs through the isolated
benchmark service with its host receipt; this result is a correctness and
operation-structure record.
