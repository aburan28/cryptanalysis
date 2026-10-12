# Rectangular limb products in the native Eisenstein scalar path

The native Eisenstein field kernel now selects multiplication widths from
the proved formula stage. Balanced coefficients fit two 64-bit limbs;
deferred `tau` intermediates fit three. A balanced ring product therefore
uses `2x2`, `2x2`, and `3x3` signed coefficient products, while a
wide-by-balanced ring product uses `3x2`, `3x2`, and `3x3`. The Montgomery
cancellation pair and `pi` both have two-limb coefficients. Every selected
width is asserted before multiplication, so an invalid bound stops the
calculation rather than truncating a product.

| Operation | Previous fixed 64-bit partial products | Rectangular partial products |
| --- | ---: | ---: |
| Balanced ring product | 27 | 17 |
| Wide-by-balanced ring product | 27 | 21 |
| Balanced raw field product, including `q*pi` | 54 | 34 |
| Wide-by-balanced raw field product, including `q*pi` | 54 | 38 |
| Normalized balanced field product, including final balance | 81 | 61 |
| Complete deferred-normalization `tau` point step | 351 | 263 |

The `tau` step has two balanced raw products, three wide-by-balanced raw
products, and three final balances: `2*34 + 3*38 + 3*27 = 263`. The
remaining three balances still use the conservative 3x3 ring product.
The 15 low-128-bit wrapping products in Montgomery cancellation are
unchanged and listed separately from the 64-bit partial-product column.
These counts describe the Rust source's multiplication loops, not CPU
instructions or measured wall time. They make no assumption that a 64-bit
partial product has the same cost as an entire field multiplication.

The rectangular dimensions are public properties of the formula stage;
the limb loop counts do not depend on field values. The current signed
arithmetic and nearest-lattice selection elsewhere in this research binary
still branch on data. The full scalar path is the width-two unit-digit
evaluator in [EISENSTEIN_SCALAR_FIXED_RESULT.md](EISENSTEIN_SCALAR_FIXED_RESULT.md).

## Verification

From this directory:

```sh
cargo build --release --bin eisenstein_fixed
cargo test --release --bin eisenstein_fixed
python3 check_eisenstein_fixed.py --random-pairs 10000
python3 check_eisenstein_tau_fixed.py
python3 check_eisenstein_scalar_fixed.py --radix w1
python3 check_eisenstein_scalar_fixed.py --radix w2
```

All 29 release Rust tests passed, including independent big-integer
products at two- and three-limb boundaries. The field replay passed
10,121 input pairs with five operations each; the `tau` replay checked
6,111 exact output coordinates; both full scalar modes matched an
independent secp256k1 affine oracle for 73 scalar cases each. The checked
release binary SHA-256 is
`6ed71f264e9e221286343a7fc744c2d220ad8a402a398201d38b16ad8914f626`.

The next arithmetic step is to specialize the fixed-conjugate-`pi`
normalization product and reduce mixed-add normalization. A full-operation
CPU comparison remains gated by the physical-host isolation protocol in
[docs/ISOLATED_BENCHMARKS.md](../../docs/ISOLATED_BENCHMARKS.md).
