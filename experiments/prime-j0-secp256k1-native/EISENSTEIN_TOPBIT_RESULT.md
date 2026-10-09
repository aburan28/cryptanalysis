# Carry-bit Karatsuba products in the native Eisenstein scalar path

The native Eisenstein field kernel now treats the top limb of a sum of two
balanced coefficients as a carry bit. A balanced coefficient is strictly
smaller than `R=2^128` in magnitude, so the magnitude of its signed sum
is below `2R`. The sum's third 64-bit limb is therefore zero or one.
The low 128-bit portions need a `2x2` schoolbook product; its top-bit
cross terms are shifted copies and additions. The same identity handles a
three-limb intermediate times a balanced coefficient sum. Fixed
`conjugate(pi)` coefficients have bounded top limbs and use this path too.

| Source operation | Previous signed 64-bit partial products | New partial products |
| --- | ---: | ---: |
| Balanced ring product | 17 | 12 |
| Wide-by-balanced ring product | 21 | 18 |
| Montgomery cancellation `q*pi` product | 17 | 12 |
| Product by fixed `conjugate(pi)` for balancing | 27 | 18 |
| Normalized balanced field product | 61 | 42 |
| Complete deferred-normalization `tau` point step | 263 | 192 |
| Ordinary deferred Jacobian mixed addition | 528 | 405 |

The `tau` count is two raw balanced products, three raw
wide-by-balanced products, and three final balances:
`2*(12+12)+3*(18+12)+3*18=192`. The mixed-add count is four
balanced raw products, four wide-by-balanced raw products, three
wide-by-wide raw products, and four balances:
`4*24+4*30+3*(27+12)+4*18=405`. The wide-by-wide ring product retains
its general `3x3` coefficient kernel. These counts include the
64-bit coefficient multiply loops in Montgomery cancellation, and
exclude the unchanged low-128-bit wrapping operations. They are not
CPU instruction counts or measured wall times.
The top-limb correction currently branches on coefficient values; a
secret-scalar implementation needs constant-time selection there and
throughout the existing signed-arithmetic and recoding path.

## Exact width argument

For `|a|,|b|<R`, the signed magnitude `|a+b|<2R`; its limb at index two
is at most one. The product of two such sums expands as

`(a_0+a_1 R)(b_0+b_1 R) = a_0 b_0 + (a_1 b_0+b_1 a_0)R + a_1 b_1 R^2`,

where `0<=a_0,b_0<R` and `a_1,b_1` are bits. Only `a_0 b_0` requires
four 64-bit partial products. For a three-limb left factor, the two
low limbs of the right factor require six partial products, and its
one-bit top contribution is a shifted copy of the left factor.
The fixed `conjugate(pi)` coefficient sums have top limbs at most two;
the implementation asserts these bounds and forms the top contribution
with signed additions. The deferred mixed-add bound in
[EISENSTEIN_DEFERRED_ADD_RESULT.md](EISENSTEIN_DEFERRED_ADD_RESULT.md)
keeps every wide left factor and its coefficient sum within three
64-bit limbs. No product truncates on a failed bound.

## Verification

From this directory:

```sh
cargo build --release --bin eisenstein_fixed
cargo test --release --bin eisenstein_fixed
python3 check_eisenstein_fixed.py --random-pairs 10000
python3 check_eisenstein_tau_fixed.py
python3 check_eisenstein_scalar_fixed.py --radix w1 --random-scalars 256
python3 check_eisenstein_scalar_fixed.py --radix w2 --random-scalars 256
```

All 31 release tests passed. The new test compares the carry-bit product
against arbitrary-precision integer multiplication across two-limb and
three-limb boundaries, both signs, and zero; it also compares the fixed
conjugate product against the general ring product. The field replay
passed 10,121 input pairs with five operations each. The `tau` replay
checked 6,111 exact output coordinates. Both complete scalar modes
matched an independent secp256k1 affine oracle on 281 cases each.
The checked release binary SHA-256 is
`1133c7b80323a710920a33f5138e19d4cc74b575ba13a3e01442c3440ae303b3`.

The next full-operation comparison needs a qualifying isolated CPU host
under [the benchmark protocol](../../docs/ISOLATED_BENCHMARKS.md).
