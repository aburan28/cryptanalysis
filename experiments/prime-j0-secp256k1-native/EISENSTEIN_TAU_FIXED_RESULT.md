# Native deferred-normalization tau point step

The fixed-width Rust Eisenstein kernel now evaluates a complete Jacobian
tau step with five raw Montgomery products, integer linear combinations,
and three final coordinate balances. The final normalizer uses a
256-bit arithmetic shift, at most one quotient correction, and the four
nearest coordinate-floor corners proved in
[LAZY_TAU_RESULT.md](LAZY_TAU_RESULT.md). On 2,003 field triples and 34
curve points, all 6,111 native output coordinates matched the independent
Python reference exactly. The 34 affine points also matched `P-omega(P)`
from ordinary elliptic-curve addition.

## Fixed-width path and operation structure

`src/bin/eisenstein_fixed.rs --tau` accepts six decimal coefficients for
balanced Montgomery pairs `X`, `Y`, and `Z`. Decimal conversion is outside
the arithmetic path. The raw reducer cancels the low 128 bits with a
two-coordinate Montgomery step and leaves the bounded quotient
unnormalized. The tau formula is:

```
X3    = raw(raw(X*X)*X)
RX    = 4*raw(Y*Y) - 3*X3
RY    = raw(Y*(3*X3 - 2*RX))
RZ    = raw(((1-omega)*X)*Z)
output = balance(RX), balance(RY), balance(RZ)
```

This evaluates five raw field products and three final balances. In the
current fixed-width source, a raw product uses six `U256::mul_wide` calls
for its ring product and Montgomery cancellation; a balance uses three
more for `u*conjugate(pi)`. Thus the tau path uses 39 such wide-product
calls, plus 15 low-128-bit wrapping products for cancellation. Balancing
each of its five product outputs alone would use 45 wide-product calls;
the deferred schedule saves six before counting additive intermediates.
These are source-operation counts, not CPU timings. The generic wide
products still process four limbs even when the coefficients are shorter.

The normalizer checks the width precondition derived in the earlier proof:
each `t=u*conjugate(pi)` coordinate must be below `22*2^256`. If it is not,
the diagnostic binary stops instead of silently truncating the quotient.
It resolves exact nearest-lattice ties in lexicographic order. The current
signed arithmetic and correction selection branch on field values, so
constant-time selection is required before use with secret scalars.

## Verification

From `experiments/prime-j0-secp256k1-native`:

```sh
cargo build --release --bin eisenstein_fixed
cargo test --release --bin eisenstein_fixed
python3 check_eisenstein_tau_fixed.py
python3 check_eisenstein_fixed.py --random-pairs 10000
```

The tau replay uses seed `20261010`, 2,003 field triples, and 34 curve
points with independently generated scalars and random projective scales.
It compares every balanced pair with the Python lazy tau screen, every
decoded coordinate with the canonical field formula, and every curve
point with independent `P-omega(P)` group addition. The Rust suite passed
25 tests, including 246 constructed quotient-boundary cases, 119 of which
needed the one-step correction. The earlier five-operation field replay
still passed on 10,121 input pairs. The checked release binary SHA-256 was
`472becac3a29cf1aadfd619d377d525cd02ef18d31563e007b6e9250fd6e281a`.

The next step is to implement the same bounded schedule for rho and the
remaining point operations, then wire it into a full scalar multiplication
path. A physical isolated CPU receipt is needed for any wall-time ratio.
