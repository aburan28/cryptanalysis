# Solinas reduction proof

Let `B = 2^256`, `c = 2^32 + 977`, and `p = B - c`, the secp256k1 field
prime. For a nonnegative integer `n`, define

`F(n) = (n mod B) + c * floor(n / B)`.

Since `B = p + c`, replacing the high part of `n` by `c` preserves its
residue modulo `p`: `F(n) ≡ n (mod p)`. Four applications also preserve that
residue. For canonical field operands `a,b < p`, their product `n = ab` is
less than `B²`. The successive bounds used in the proof are

| Stage | Bound |
| --- | --- |
| `F(n)` | `< B(c + 1)` |
| `F²(n)` | `< B + c²` |
| `F³(n)` | `< B + c` |
| `F⁴(n)` | `< B + c < 2p` |

Here `c² < B` and `3c < B` hold for the exact secp256k1 constants. The final
value is therefore either already below `p` or needs one subtraction of `p`.
In both cases the output is `ab mod p` and lies in `[0,p)`.

## Lean proof map

[`SolinasReduction.lean`](SolinasReduction.lean) uses only Lean 4's bundled
libraries and the pinned toolchain in [`lean-toolchain`](lean-toolchain).

| Mathematical step | Lean declaration | Hypotheses | Status |
| --- | --- | --- | --- |
| Exact prime/radix relationship | `PrimeJ0Solinas.radix_eq_prime_add_foldConstant` | None | Checked |
| One high/low fold preserves the residue | `PrimeJ0Solinas.product_fold_mod` | `low high : Nat` | Checked |
| Full-width fold preserves the residue | `PrimeJ0Solinas.fold_mod` | `n : Nat` | Checked |
| Four folds preserve the residue | `PrimeJ0Solinas.foldFour_mod` | `n : Nat` | Checked |
| Four folds fit within one final subtraction | `PrimeJ0Solinas.foldFour_lt_twoPrime` | `n < B²` | Checked |
| One conditional subtraction computes the canonical remainder | `PrimeJ0Solinas.subtractIfNeeded_mod` | input `< 2p` | Checked |
| Canonical field operands give the exact product | `PrimeJ0Solinas.canonical_product_reduction` | `a,b : Nat`, `a < p`, `b < p` | Checked |
| The result is canonical | `PrimeJ0Solinas.canonical_product_result_lt_prime` | `a,b : Nat`, `a < p`, `b < p` | Checked |

Run from this directory:

```sh
ELAN_TOOLCHAIN=leanprover/lean4:v4.34.1 lean SolinasReduction.lean
```

The build output in `lean-build.txt` includes `#print axioms` for each
reported theorem. It reports only the standard Lean foundations `propext`
and `Quot.sound` where required. The source contains no `sorry`, `admit`,
custom research axioms, or native-evaluation proof step. `lean4checker`
was unavailable on this host.

The Lean declarations model unbounded natural-number folds. The Rust
`u256_mul_solinas` routine implements the first fold over a 512-bit product,
three fixed carry folds, and one conditional subtraction using `u64` limbs.
The equivalence between those bit-level operations and `foldFour` is not
mechanically linked; the deterministic field-product test and the 4,096
point replay check that implementation bridge.
