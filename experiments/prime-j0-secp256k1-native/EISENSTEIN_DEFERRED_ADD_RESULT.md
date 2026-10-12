# Deferred normalization in native Eisenstein mixed addition

The native scalar evaluator now carries raw Eisenstein Montgomery quotients
through a Jacobian mixed addition. It balances the difference `h = U-X` to
detect equal and inverse points, then balances the three final projective
coordinates. An ordinary addition uses eleven raw field products and four
nearest-lattice balances. The previous schedule balanced after each of its
eleven field products and after several field additions.

With the fixed rectangular coefficient kernels, the new ordinary path has
four balanced-by-balanced raw products at 34 signed 64-bit partial products
each, four wide-by-balanced products at 38 each, three wide-by-wide products
at 44 each, and four 27-product balances:

`4*34 + 4*38 + 3*44 + 4*27 = 528`.

The previous eleven normalized balanced field products alone used
`11*61 = 671` such partial products; its addition/subtraction balances add
more. These are source-level counts of the signed coefficient multiply loops.
The low-128-bit wrapping products used in Montgomery cancellation are
unchanged. A CPU wall-time comparison requires an isolated-host receipt.

## Width and correctness argument

Write `R = 2^128`. A balanced pair has both coefficient magnitudes below
`R`. If two pairs have coefficient bounds `cR` and `dR`, their ring product
has coefficient magnitudes below `3cd R^2`. The Montgomery cancellation
pair has coefficients below `R`, and each coefficient of its product with
`pi` is below `3R^2`. Exact division by `R` therefore bounds every raw
field product by `(3cd+3)R` coefficientwise.

Applying that recurrence to the mixed-add formula gives conservative
coefficient bounds in units of `R`:

| Intermediate | Bound |
| --- | ---: |
| `Z^2`, `y_Q Z` | 6 |
| `U=x_Q Z^2` | 21 |
| `S=y_Q Z^3` | 111 |
| `h_raw=U-X`, `v=S-Y` | 22, 112 |
| balanced `h`; `h^2`; `h^3`; `X h^2` | 1, 6, 21, 21 |
| `v^2`; `X'=v^2-h^3-2Xh^2` | 37,635; 37,698 |
| `Xh^2-X'`; `Y'=v(Xh^2-X')-Yh^3` | 37,719; 12,673,653 |
| `Z'=Zh` | 6 |

The largest raw output is below `2^26 R`, so its coefficients fit three
64-bit limbs. Multiplying by `conjugate(pi)` gives coefficients below
`3*12,673,653 R^2 = 38,020,959 R^2 < 2^26 R^2`. The native corner-balancing
routine asserts this high-word cap before calculating a correction. The
initial quotient `floor(t/R^2)` differs from `floor(t/p)` by at most one:
`p=R^2-(2^32+977)` and `|t|<2^26 R^2`. The routine corrects that quotient
with an exact remainder comparison. A nearest Eisenstein-lattice correction
lies among the floor/ceiling choices in each coordinate because the
Voronoi cell has coordinate extent at most `2/3`; the existing three
Voronoi inequalities choose the canonical corner. Binary doubling now
computes the potentially larger correction multiples in logarithmically
many signed additions.

Balancing `h` before its zero check is required: an unbalanced difference
can be a nonzero multiple of `pi` even when its field value is zero. The
inverse/equal-point branch also balances `v` before testing it. The other
raw intermediates remain in the Montgomery domain, so the projective
polynomial gives the same curve point modulo `pi`.

## Verification

From this directory:

```sh
cargo build --release --bin eisenstein_fixed
cargo test --release --bin eisenstein_fixed
python3 check_eisenstein_scalar_fixed.py --radix w1 --random-scalars 256
python3 check_eisenstein_scalar_fixed.py --radix w2 --random-scalars 256
python3 check_eisenstein_tau_fixed.py
python3 check_eisenstein_fixed.py --random-pairs 10000
```

All 30 release tests passed, including exact balancing after large positive
and negative lattice offsets. Each scalar mode passed 281 cases against the
independent secp256k1 affine oracle. The field replay passed 10,121 input
pairs with five operations each, and the tau replay checked 6,111 exact
output coordinates. The native release binary SHA-256 for the recorded replay is
`9bf4f3cf879011e733ca578e5910b12d6b1f5f991c217969bc1e6c8fed913cdc`.

The next experiment is to compare complete scalar evaluation against a
conventional secp256k1 field on the same inputs and calibrated isolated
CPU, including preparation, conversion, and output verification where the
chosen timing boundary requires them. The current RunPod CPU Pod rejects
the [strict isolation preflight](../../docs/ISOLATED_BENCHMARKS.md).
