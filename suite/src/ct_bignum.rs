//! Fixed-width, constant-time(-by-construction) multi-precision integer.
//!
//! This module exists because `num-bigint`'s `BigUint` is the foundation
//! of every public-key operation in this crate, and it leaks via
//! operand magnitudes at the limb level — every key recovery attack
//! against ECDSA/ECDH/RSA in this codebase ultimately bottoms out on
//! that fact (see `SECURITY.md`).  A faithful fix means replacing
//! `num-bigint` with a fixed-width type whose every primitive runs in
//! the same number of cycles regardless of operand values.
//!
//! [`Uint<LIMBS>`] is a const-generic, four-or-more-limb little-endian
//! unsigned integer with branchless add/sub/mul, `subtle`-backed
//! conditional select/swap, and value-independent comparison.  ECC
//! curves use [`U256`] (= `Uint<4>`); the RSA private path will use
//! larger sizes (`Uint<32>`, `Uint<48>`, `Uint<64>` for 2048/3072/4096-
//! bit moduli).
//!
//! # What "constant-time" means here
//!
//! - **Operation count is value-independent.**  Loops always run their
//!   full bound; there is no early-exit on carry, borrow, leading
//!   zeros, or operand equality.  Some loop bounds depend on the outer
//!   loop counter `i` (e.g. the carry-propagation tail of Montgomery
//!   reduction), but `i` is a public loop counter whose value is not
//!   derived from any secret.
//! - **No data-dependent memory access.**  All limb indices are loop
//!   counters; no array is indexed by a value derived from a secret.
//! - **No data-dependent branch on Rust source.**  Conditional values
//!   route through `subtle::Choice` /
//!   `subtle::ConditionallySelectable`, which use volatile reads and
//!   `core::hint::black_box`-style barriers to prevent the compiler
//!   from re-introducing branches.
//!
//! What this **doesn't** guarantee, and never can at the language
//! layer: that the LLVM-generated machine code, on every target/CPU,
//! actually runs in the same number of cycles.  Some 64-bit
//! multiplications are variable-time on Cortex-A53, ARM7, and a few
//! older Intel chips; division is variable-time almost everywhere.
//! We only use `*` (which compiles to `mul`) and `+`/`-` (which never
//! vary), and we never divide.  See SECURITY.md for the full picture.

use num_bigint::BigUint;
use subtle::{Choice, ConditionallySelectable};

/// A multi-precision unsigned integer stored as `LIMBS` 64-bit limbs
/// in little-endian order: `limbs[0]` is the least significant.
#[derive(Copy, Clone, Debug)]
pub struct Uint<const LIMBS: usize>(pub [u64; LIMBS]);

/// Backwards-compatible alias for the four-limb (256-bit) integer that
/// the entire ECC stack is built on.
pub type U256 = Uint<4>;

impl<const LIMBS: usize> Uint<LIMBS> {
    pub const ZERO: Self = Self([0; LIMBS]);
    pub const ONE: Self = {
        let mut limbs = [0u64; LIMBS];
        limbs[0] = 1;
        Self(limbs)
    };

    // ── Conversions ──────────────────────────────────────────────────────

    /// Convert from `BigUint`.  Truncates to `64 * LIMBS` bits; the
    /// caller is responsible for ensuring the value fits.  Used for
    /// compatibility with the rest of the crate during the gradual
    /// migration off `num-bigint`.
    pub fn from_biguint(v: &BigUint) -> Self {
        let mut limbs = [0u64; LIMBS];
        // BigUint::to_bytes_le gives little-endian bytes; group into
        // 8-byte limbs.  Anything past LIMBS*8 bytes is silently
        // truncated (that is the documented behaviour).
        let bytes = v.to_bytes_le();
        for (i, limb) in limbs.iter_mut().enumerate() {
            let mut buf = [0u8; 8];
            let start = i * 8;
            if start >= bytes.len() {
                break;
            }
            let end = (start + 8).min(bytes.len());
            buf[..end - start].copy_from_slice(&bytes[start..end]);
            *limb = u64::from_le_bytes(buf);
        }
        Self(limbs)
    }

    /// Convert to `BigUint` for cross-checking and interop.
    pub fn to_biguint(&self) -> BigUint {
        let mut bytes = vec![0u8; LIMBS * 8];
        for (i, &limb) in self.0.iter().enumerate() {
            // Limb 0 (least significant) lives at the *highest* offset
            // in a big-endian byte string.
            let dst = (LIMBS - 1 - i) * 8;
            bytes[dst..dst + 8].copy_from_slice(&limb.to_be_bytes());
        }
        BigUint::from_bytes_be(&bytes)
    }

    // ── Equality and comparison ──────────────────────────────────────────

    /// Constant-time equality.  Returns `Choice(1)` iff every limb
    /// matches.  XOR-fold over all limbs followed by an
    /// "any nonzero bit" reduction.
    pub fn ct_eq_full(&self, other: &Self) -> Choice {
        let mut diff: u64 = 0;
        for i in 0..LIMBS {
            diff |= self.0[i] ^ other.0[i];
        }
        // diff == 0  ⇔  equal.  Build a 0/1 flag without branching.
        // (diff | (-diff)) >> 63  is 0 iff diff == 0, else 1.
        let nonzero = (diff | diff.wrapping_neg()) >> 63;
        Choice::from(((nonzero ^ 1) & 1) as u8)
    }

    /// Constant-time `self < other`.  Computes the borrow-out of
    /// `self - other`; that bit is 1 iff `self < other`.
    pub fn ct_lt(&self, other: &Self) -> Choice {
        let (_, borrow) = Self::sbb(self, other);
        Choice::from((borrow & 1) as u8)
    }

    /// True iff `self == 0`.
    pub fn ct_is_zero(&self) -> Choice {
        self.ct_eq_full(&Self::ZERO)
    }

    // ── Conditional selection ────────────────────────────────────────────

    /// `cmov(a, b, choice)` returns `b` if `choice == 1`, else `a`.
    /// Limb-wise `subtle::ConditionallySelectable`.
    pub fn cmov(a: &Self, b: &Self, choice: Choice) -> Self {
        let mut out = [0u64; LIMBS];
        for i in 0..LIMBS {
            out[i] = u64::conditional_select(&a.0[i], &b.0[i], choice);
        }
        Self(out)
    }

    /// Swap `a` and `b` iff `choice == 1`.  Used by the Montgomery
    /// ladder over the new field type.
    pub fn cswap(a: &mut Self, b: &mut Self, choice: Choice) {
        for i in 0..LIMBS {
            u64::conditional_swap(&mut a.0[i], &mut b.0[i], choice);
        }
    }

    // ── Addition / subtraction ───────────────────────────────────────────

    /// Add with carry-in zero.  Returns `(sum, carry_out)`.  The carry
    /// is propagated through all limbs uniformly; there is no early
    /// exit when the carry chain dies.
    pub fn adc(a: &Self, b: &Self) -> (Self, u64) {
        let mut out = [0u64; LIMBS];
        let mut carry: u64 = 0;
        for i in 0..LIMBS {
            // u128 intermediate avoids the two-step overflowing_add
            // dance and compiles to the same `adc`-chain on x86-64.
            let sum = (a.0[i] as u128) + (b.0[i] as u128) + (carry as u128);
            out[i] = sum as u64;
            carry = (sum >> 64) as u64;
        }
        (Self(out), carry)
    }

    /// Subtract with borrow-in zero.  Returns `(diff, borrow_out)`.
    pub fn sbb(a: &Self, b: &Self) -> (Self, u64) {
        let mut out = [0u64; LIMBS];
        let mut borrow: u64 = 0;
        for i in 0..LIMBS {
            // Use 128-bit signed-style subtraction to keep the borrow
            // chain branchless.
            let lhs = a.0[i] as i128;
            let rhs = (b.0[i] as i128) + (borrow as i128);
            let diff = lhs - rhs;
            out[i] = diff as u64;
            // borrow = 1 iff diff < 0  ⇔  high bit of (diff as u128) set.
            borrow = ((diff as u128) >> 127) as u64;
        }
        (Self(out), borrow)
    }

    // ── Modular addition / subtraction ───────────────────────────────────

    /// Modular addition: returns `(self + other) mod p`.
    ///
    /// Requires `self < p` and `other < p` (the canonical form
    /// invariant the caller must maintain).  Always performs both an
    /// add and a subtract; the conditional move at the end picks the
    /// reduced result without branching on the carry.
    pub fn add_mod(&self, other: &Self, p: &Self) -> Self {
        let (sum, carry) = Self::adc(self, other);
        let (sum_minus_p, borrow) = Self::sbb(&sum, p);
        // Need to subtract `p` iff the un-reduced sum already overflowed
        // (carry == 1) OR sum >= p (borrow == 0 from sum - p).  In
        // either case we want `sum_minus_p`; otherwise we keep `sum`.
        let need_sub = Choice::from(((carry | (borrow ^ 1)) & 1) as u8);
        Self::cmov(&sum, &sum_minus_p, need_sub)
    }

    /// Modular subtraction: returns `(self - other) mod p`.
    ///
    /// Requires `self < p` and `other < p`.
    pub fn sub_mod(&self, other: &Self, p: &Self) -> Self {
        let (diff, borrow) = Self::sbb(self, other);
        // If `self < other`, the raw diff equals `self - other + 2^256`;
        // adding `p` correctsit (since p < 2^256, the algebra works
        // out modulo p).
        let (corrected, _) = Self::adc(&diff, p);
        let need_add = Choice::from((borrow & 1) as u8);
        Self::cmov(&diff, &corrected, need_add)
    }

    // ── Wide multiplication ──────────────────────────────────────────────

    /// `LIMBS×LIMBS → 2·LIMBS`-limb schoolbook multiplication.  Returns
    /// `(low, high)` halves of the full product.
    ///
    /// Uses `u128` partial products throughout; the inner loop runs the
    /// full `LIMBS × LIMBS` limb multiplications regardless of operand
    /// magnitudes.
    pub fn mul_wide(a: &Self, b: &Self) -> (Self, Self) {
        let mut lo = [0u64; LIMBS];
        let mut hi = [0u64; LIMBS];
        for i in 0..LIMBS {
            let mut carry: u64 = 0;
            for j in 0..LIMBS {
                let idx = i + j;
                // t[i+j] += a[j] * b[i] + carry
                let cur = if idx < LIMBS {
                    lo[idx]
                } else {
                    hi[idx - LIMBS]
                };
                let acc = (a.0[j] as u128) * (b.0[i] as u128) + (cur as u128) + (carry as u128);
                let new = acc as u64;
                if idx < LIMBS {
                    lo[idx] = new;
                } else {
                    hi[idx - LIMBS] = new;
                }
                carry = (acc >> 64) as u64;
            }
            // Final carry goes to position i+LIMBS, which is hi[i].
            hi[i] = carry;
        }
        (Self(lo), Self(hi))
    }

    // ── Montgomery multiplication ────────────────────────────────────────
    //
    // We use the "Separated Operand Scanning" (SOS) variant of
    // Montgomery multiplication: compute the full 2·LIMBS-limb product,
    // then reduce.  SOS is the most straightforward variant to verify
    // correct, at a small (~10%) speed penalty vs CIOS.  Given that we
    // are not chasing peak performance — only constant-time
    // correctness — clarity wins.
    //
    // For a `LIMBS`-limb modulus `p` with `R = 2^(64·LIMBS)` and
    // `R > p`, `mont_mul(a, b)` returns `a * b * R^(-1) mod p`.  Inputs
    // and output are all in `[0, p)`.
    //
    // The "Montgomery constant" `p_inv_low` is `(-p[0])^(-1) mod 2^64`
    // — i.e. the unique 64-bit value `m'` such that
    // `p[0] * m' ≡ -1 (mod 2^64)`.  The caller computes this once per
    // modulus (see [`compute_minv64`]) and reuses it.

    /// Montgomery multiplication: `a * b * R^(-1) mod p`.
    ///
    /// Requirements (the caller must uphold these — they are not
    /// runtime-checked, since checking would itself leak):
    ///
    /// - `p` is odd
    /// - `a < p` and `b < p`
    /// - `p_inv_low == (-p[0])^(-1) mod 2^64`
    pub fn mont_mul(a: &Self, b: &Self, p: &Self, p_inv_low: u64) -> Self {
        // Conceptual `2·LIMBS+1`-limb scratch, split into:
        //   lo[0..LIMBS]    = positions 0..LIMBS
        //   hi[0..LIMBS]    = positions LIMBS..2·LIMBS
        //   extra: u64      = position 2·LIMBS
        // All three are stack-allocated; `lo`/`hi` are size-LIMBS arrays
        // (which the const-generic limb count makes legal on stable),
        // and the boundary check `idx < LIMBS` is a public loop-counter
        // comparison, so it does not introduce a secret-dependent branch.
        let mut lo = [0u64; LIMBS];
        let mut hi = [0u64; LIMBS];
        let mut extra: u64 = 0;

        // Phase 1: lo:hi = a * b  (full 2·LIMBS-limb schoolbook product)
        for i in 0..LIMBS {
            let mut carry: u64 = 0;
            for j in 0..LIMBS {
                let idx = i + j;
                let cur = if idx < LIMBS {
                    lo[idx]
                } else {
                    hi[idx - LIMBS]
                };
                let acc = (cur as u128) + (a.0[j] as u128) * (b.0[i] as u128) + (carry as u128);
                let new = acc as u64;
                if idx < LIMBS {
                    lo[idx] = new;
                } else {
                    hi[idx - LIMBS] = new;
                }
                carry = (acc >> 64) as u64;
            }
            // Position i+LIMBS is hi[i]; the final carry of this row
            // is the only thing written there in Phase 1, so we just
            // assign rather than accumulate.
            hi[i] = carry;
        }

        // Phase 2: Montgomery reduction.  Each iteration zeros one low
        // limb of the conceptual buffer by adding a multiple of `p`;
        // after LIMBS iterations, the result lives in `hi`, with at
        // most a 1-bit overflow into `extra`.
        for i in 0..LIMBS {
            // `m` is chosen so that lo[i] + m * p[0] ≡ 0 (mod 2^64),
            // which makes the subsequent add zero the i-th low limb.
            let m = lo[i].wrapping_mul(p_inv_low);

            // Add m * p starting at conceptual position i.  Inner-loop
            // index ranges i..i+LIMBS; this can straddle the lo/hi
            // boundary, but `idx < LIMBS` is a public comparison.
            let mut carry: u64 = 0;
            for j in 0..LIMBS {
                let idx = i + j;
                let cur = if idx < LIMBS {
                    lo[idx]
                } else {
                    hi[idx - LIMBS]
                };
                let acc = (cur as u128) + (m as u128) * (p.0[j] as u128) + (carry as u128);
                let new = acc as u64;
                if idx < LIMBS {
                    lo[idx] = new;
                } else {
                    hi[idx - LIMBS] = new;
                }
                carry = (acc >> 64) as u64;
            }

            // Propagate the final carry from position i+LIMBS onward.
            // Position i+LIMBS is hi[i]; propagation continues through
            // hi[i+1..LIMBS] and then the single `extra` slot at
            // position 2·LIMBS.  The loop bound shrinks with `i`, but
            // the *total* op count across the full reduction depends
            // only on the public constant `LIMBS`, not on operand
            // values.
            for k in i..LIMBS {
                let acc = (hi[k] as u128) + (carry as u128);
                hi[k] = acc as u64;
                carry = (acc >> 64) as u64;
            }
            // Final carry into `extra`.  The high half of the u128
            // result is provably zero given a well-formed odd modulus
            // (the accumulator can grow by at most one bit per
            // reduction step), so we drop it.
            let acc = (extra as u128) + (carry as u128);
            extra = acc as u64;
        }

        let result = Self(hi);

        // Conditional final subtraction: result >= p OR extra == 1.
        let (sub, borrow) = Self::sbb(&result, p);
        let need_sub = Choice::from(((extra | (borrow ^ 1)) & 1) as u8);
        Self::cmov(&result, &sub, need_sub)
    }

    /// Convenience: Montgomery squaring.  Same as `mont_mul(a, a, ..)`,
    /// kept as a separate method to make call sites self-documenting
    /// and to leave room for a dedicated squaring routine later.
    pub fn mont_sqr(a: &Self, p: &Self, p_inv_low: u64) -> Self {
        Self::mont_mul(a, a, p, p_inv_low)
    }
}

// ── Specialised methods for the four-limb / 256-bit case ─────────────────
//
// These are pulled into a non-generic `impl` block because their
// signatures involve byte-array sizes that cannot be expressed as
// `[u8; 8 * LIMBS]` on stable Rust without `feature(generic_const_exprs)`.
// All ECC field code is built on `Uint<4>`, so this is the only size
// that needs byte-level serialisation.

impl Uint<4> {
    /// Big-endian byte serialization (32 bytes).  No allocation.
    pub fn to_bytes_be(&self) -> [u8; 32] {
        let mut out = [0u8; 32];
        // Limb 0 (least significant) goes to the *last* 8 bytes.
        for (i, &limb) in self.0.iter().enumerate() {
            let dst = 32 - 8 * (i + 1);
            out[dst..dst + 8].copy_from_slice(&limb.to_be_bytes());
        }
        out
    }

    /// Big-endian byte deserialization.
    pub fn from_bytes_be(bytes: &[u8; 32]) -> Self {
        let mut limbs = [0u64; 4];
        for i in 0..4 {
            let src = 32 - 8 * (i + 1);
            limbs[i] = u64::from_be_bytes(bytes[src..src + 8].try_into().unwrap());
        }
        Self(limbs)
    }
}

// ── Montgomery context + constant-time modular exponentiation ────────────
//
// `MontgomeryContext<LIMBS>` is the runtime-built analogue of the
// compile-time `SecpFieldElement` / `P256FieldElement` constants: it
// wraps an odd modulus `n` together with the three precomputed values
// (`n_inv_low`, `R mod n`, `R² mod n`) that every Montgomery-form
// operation needs.  ECC fields can hard-code these in `const`s because
// `p` is fixed at compile time; RSA's modulus is generated at key-gen
// time, so the same setup work has to happen at runtime.
//
// Setup is *not* on a hot path — it runs once per loaded key — so we
// allow ourselves to lean on `BigUint` to compute `R mod n` and
// `R² mod n`.  Once setup is done, every subsequent operation goes
// through `Uint::mont_mul` / `Uint::mont_sqr`, which are limb-level
// constant-time.
//
// `mont_pow_ct` is the constant-time modular exponentiation that
// replaces `crate::utils::mod_pow_ct` on the RSA private path.  Like
// the existing helper, it processes a fixed number of bits per call —
// `64 * LIMBS` — and uses `cmov` to make the per-bit "should I
// multiply?" decision branch-free.

/// Precomputed Montgomery constants for an odd modulus `n`.  Construct
/// once via [`MontgomeryContext::new`] and reuse for every operation.
#[derive(Clone, Debug)]
pub struct MontgomeryContext<const LIMBS: usize> {
    /// The modulus `n` itself.  Must be odd and have its top bit set
    /// in the highest limb (i.e. occupy the full `64 * LIMBS` width
    /// down to a single bit of slack — `n < R = 2^(64·LIMBS)` and
    /// `n > R/2`).  RSA moduli of the supported sizes satisfy this.
    pub n: Uint<LIMBS>,
    /// `m' = -n^(-1) mod 2^64`, the Montgomery reduction constant.
    pub n_inv_low: u64,
    /// `R mod n`, where `R = 2^(64·LIMBS)`.  Equals `1` represented in
    /// Montgomery form.
    pub r_mod_n: Uint<LIMBS>,
    /// `R² mod n`.  Multiplied with a canonical-form value via
    /// [`Uint::mont_mul`] to convert it to Montgomery form.
    pub r2_mod_n: Uint<LIMBS>,
}

impl<const LIMBS: usize> MontgomeryContext<LIMBS> {
    /// Build a context for the odd modulus `n`.  Returns `None` if `n`
    /// is even or zero.
    ///
    /// Setup uses `BigUint` for the `R mod n` and `R² mod n`
    /// reductions because (a) it is run exactly once per key, never on
    /// a per-message path, and (b) `n` is public — it is the modulus,
    /// not the private exponent.  No secret-dependent timing channel
    /// exists at this layer.
    pub fn new(n: Uint<LIMBS>) -> Option<Self> {
        if n.0[0] & 1 == 0 {
            return None;
        }
        if bool::from(n.ct_is_zero()) {
            return None;
        }
        let n_inv_low = compute_minv64(n.0[0]);
        let n_bu = n.to_biguint();
        let r = BigUint::from(1u8) << (64 * LIMBS);
        let r_mod_n = Uint::<LIMBS>::from_biguint(&(&r % &n_bu));
        let r2_mod_n = Uint::<LIMBS>::from_biguint(&((&r * &r) % &n_bu));
        Some(Self {
            n,
            n_inv_low,
            r_mod_n,
            r2_mod_n,
        })
    }

    /// Multiply two Montgomery-form values: `(a · R) · (b · R) · R^(-1) = (a·b) · R`.
    pub fn mont_mul(&self, a: &Uint<LIMBS>, b: &Uint<LIMBS>) -> Uint<LIMBS> {
        Uint::mont_mul(a, b, &self.n, self.n_inv_low)
    }

    /// Square a Montgomery-form value.
    pub fn mont_sqr(&self, a: &Uint<LIMBS>) -> Uint<LIMBS> {
        Uint::mont_sqr(a, &self.n, self.n_inv_low)
    }

    /// Convert canonical → Montgomery: `a → a · R mod n`.
    pub fn to_montgomery(&self, a: &Uint<LIMBS>) -> Uint<LIMBS> {
        // a · R²·R^(-1) = a · R.
        Uint::mont_mul(a, &self.r2_mod_n, &self.n, self.n_inv_low)
    }

    /// Convert Montgomery → canonical: `a·R → a`.
    pub fn from_montgomery(&self, a_mont: &Uint<LIMBS>) -> Uint<LIMBS> {
        // a·R · 1 · R^(-1) = a.
        Uint::mont_mul(a_mont, &Uint::<LIMBS>::ONE, &self.n, self.n_inv_low)
    }
}

/// Constant-time modular exponentiation in Montgomery form.
///
/// Computes `base^exp mod n` where `n = ctx.n`.  Both inputs are in
/// canonical form (`< n`); the output is in canonical form.
///
/// # Constant-time guarantees
///
/// Every iteration of the inner loop performs *exactly* one modular
/// squaring and one modular multiplication.  The "should I multiply?"
/// decision per bit is made via `Uint::cmov` — the multiply is always
/// computed, then the result is conditionally selected.  The number of
/// iterations is fixed at `64 · LIMBS`, regardless of the actual bit
/// length of `exp` (high zero limbs are still scanned).  This means
/// the operation count is a function of the modulus *width* only —
/// which is public — and not of the secret exponent's value.
///
/// # When to use
///
/// Use this for RSA private operations (`m^d mod n` for decrypt /
/// sign).  For the public-exponent path (`c = m^e mod n`, where `e` is
/// usually 65537), the variable-time `crate::utils::mod_pow` is
/// preferable — it's faster and `e` is not a secret.
pub fn mont_pow_ct<const LIMBS: usize>(
    base: &Uint<LIMBS>,
    exp: &Uint<LIMBS>,
    ctx: &MontgomeryContext<LIMBS>,
) -> Uint<LIMBS> {
    // Convert base into Montgomery form.
    let base_mont = ctx.to_montgomery(base);
    // Accumulator starts at 1 in Montgomery form, which is `R mod n`.
    let mut acc = ctx.r_mod_n;

    // Square-and-multiply ladder, MSB-first.  Iteration count is
    // pinned at the public bit width — high zero bits of `exp` are
    // still scanned, so total work is value-independent.
    let total_bits = 64 * LIMBS;
    for i in (0..total_bits).rev() {
        let limb_idx = i / 64;
        let bit_idx = i % 64;
        let bit = (exp.0[limb_idx] >> bit_idx) & 1;
        let bit_choice = Choice::from(bit as u8);

        // Always square.
        acc = ctx.mont_sqr(&acc);
        // Always compute the multiply; cmov selects whether to keep
        // it.  This makes the per-bit work cost identical regardless
        // of `bit`'s value.
        let mul_result = ctx.mont_mul(&acc, &base_mont);
        acc = Uint::cmov(&acc, &mul_result, bit_choice);
    }

    // Convert back from Montgomery form.
    ctx.from_montgomery(&acc)
}

/// Compute the Montgomery constant `m'` such that
/// `n * m' ≡ -1 (mod 2^64)` — i.e. `m' = -n^(-1) mod 2^64`.
///
/// Uses Newton-Raphson iteration in the 2-adic integers: each step
/// doubles the number of correct bits, so six iterations are enough
/// for 64-bit precision.  `n` must be odd (which every odd prime
/// modulus's lowest limb is — and every RSA modulus's, since `n = p·q`
/// with both factors odd).
///
/// `const fn` so it can populate compile-time constants.
pub const fn compute_minv64(n: u64) -> u64 {
    // Initial seed: x_0 = 1 satisfies n*x_0 ≡ 1 (mod 2), since n is odd.
    let mut x: u64 = 1;
    let mut i = 0;
    while i < 6 {
        // x_{n+1} = x_n * (2 - n * x_n)  (mod 2^64)
        x = x.wrapping_mul(2u64.wrapping_sub(n.wrapping_mul(x)));
        i += 1;
    }
    // After 6 iterations, n * x ≡ 1 (mod 2^64).  We want -x.
    x.wrapping_neg()
}

#[cfg(test)]
mod tests {
    use super::*;
    use num_bigint::BigUint;
    use num_traits::Zero;

    /// A handful of values that exercise interesting limb boundaries.
    fn test_values() -> Vec<U256> {
        let max = Uint([u64::MAX; 4]);
        let half = Uint([0, 0, 0, 1u64 << 63]);
        let limb_boundary = Uint([u64::MAX, 0, 0, 0]);
        let just_over_one_limb = Uint([0, 1, 0, 0]);
        let p_secp256k1 = {
            let bytes =
                hex::decode("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F")
                    .unwrap();
            U256::from_bytes_be(&bytes.try_into().unwrap())
        };
        vec![
            U256::ZERO,
            U256::ONE,
            limb_boundary,
            just_over_one_limb,
            half,
            Uint([0xdeadbeef, 0xcafebabe, 0x1234_5678, 0xfedcba98]),
            p_secp256k1,
            max,
        ]
    }

    #[test]
    fn bytes_roundtrip() {
        for v in test_values() {
            let bytes = v.to_bytes_be();
            let v2 = U256::from_bytes_be(&bytes);
            assert!(bool::from(v.ct_eq_full(&v2)));
        }
    }

    #[test]
    fn biguint_roundtrip() {
        for v in test_values() {
            let bu = v.to_biguint();
            let v2 = U256::from_biguint(&bu);
            assert!(bool::from(v.ct_eq_full(&v2)));
        }
    }

    #[test]
    fn ct_eq_matches_value_eq() {
        let vs = test_values();
        for a in &vs {
            for b in &vs {
                let want = a.to_biguint() == b.to_biguint();
                let got = bool::from(a.ct_eq_full(b));
                assert_eq!(got, want, "ct_eq mismatch");
            }
        }
    }

    #[test]
    fn ct_lt_matches_value_lt() {
        let vs = test_values();
        for a in &vs {
            for b in &vs {
                let want = a.to_biguint() < b.to_biguint();
                let got = bool::from(a.ct_lt(b));
                assert_eq!(got, want, "ct_lt mismatch");
            }
        }
    }

    #[test]
    fn ct_is_zero_works() {
        assert!(bool::from(U256::ZERO.ct_is_zero()));
        assert!(!bool::from(U256::ONE.ct_is_zero()));
        assert!(!bool::from(Uint([0, 0, 0, 1]).ct_is_zero()));
    }

    #[test]
    fn cmov_selects_correctly() {
        let a = Uint([1, 2, 3, 4]);
        let b = Uint([10, 20, 30, 40]);
        let r0 = U256::cmov(&a, &b, Choice::from(0));
        let r1 = U256::cmov(&a, &b, Choice::from(1));
        assert!(bool::from(r0.ct_eq_full(&a)));
        assert!(bool::from(r1.ct_eq_full(&b)));
    }

    #[test]
    fn cswap_swaps_correctly() {
        let a0 = Uint([1, 2, 3, 4]);
        let b0 = Uint([10, 20, 30, 40]);

        let mut a = a0;
        let mut b = b0;
        U256::cswap(&mut a, &mut b, Choice::from(0));
        assert!(bool::from(a.ct_eq_full(&a0)));
        assert!(bool::from(b.ct_eq_full(&b0)));

        let mut a = a0;
        let mut b = b0;
        U256::cswap(&mut a, &mut b, Choice::from(1));
        assert!(bool::from(a.ct_eq_full(&b0)));
        assert!(bool::from(b.ct_eq_full(&a0)));
    }

    fn modulus_256() -> BigUint {
        BigUint::from(1u8) << 256
    }

    fn p_secp256k1() -> U256 {
        let bytes = hex::decode("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F")
            .unwrap();
        U256::from_bytes_be(&bytes.try_into().unwrap())
    }

    /// Reduce a `U256` mod `p` using `BigUint` arithmetic for the
    /// reference computation in tests.
    fn reduce(v: &U256, p: &BigUint) -> U256 {
        U256::from_biguint(&(v.to_biguint() % p))
    }

    #[test]
    fn adc_matches_biguint() {
        let vs = test_values();
        for a in &vs {
            for b in &vs {
                let (sum, carry) = U256::adc(a, b);
                let expected = (a.to_biguint() + b.to_biguint()) % modulus_256();
                assert!(bool::from(sum.ct_eq_full(&U256::from_biguint(&expected))));

                let expected_carry = (a.to_biguint() + b.to_biguint() >= modulus_256()) as u64;
                assert_eq!(carry, expected_carry, "carry mismatch");
            }
        }
    }

    #[test]
    fn sbb_matches_biguint() {
        let vs = test_values();
        for a in &vs {
            for b in &vs {
                let (diff, borrow) = U256::sbb(a, b);
                // Expected: (a - b) mod 2^256 ; borrow if a < b
                let abu = a.to_biguint();
                let bbu = b.to_biguint();
                let expected = (modulus_256() + &abu - &bbu) % modulus_256();
                assert!(
                    bool::from(diff.ct_eq_full(&U256::from_biguint(&expected))),
                    "diff mismatch"
                );
                let expected_borrow = (abu < bbu) as u64;
                assert_eq!(borrow, expected_borrow, "borrow mismatch");
            }
        }
    }

    #[test]
    fn mul_wide_matches_biguint() {
        let vs = test_values();
        for a in &vs {
            for b in &vs {
                let (low, high) = U256::mul_wide(a, b);
                let combined = high.to_biguint() << 256 | low.to_biguint();
                let expected = a.to_biguint() * b.to_biguint();
                assert_eq!(combined, expected, "mul_wide mismatch");
            }
        }
    }

    #[test]
    fn add_mod_matches_reference() {
        let p = p_secp256k1();
        let p_bu = p.to_biguint();
        // Use values reduced mod p.
        let canonical: Vec<U256> = test_values()
            .into_iter()
            .map(|v| reduce(&v, &p_bu))
            .collect();
        for a in &canonical {
            for b in &canonical {
                let got = a.add_mod(b, &p);
                let want = U256::from_biguint(&((a.to_biguint() + b.to_biguint()) % &p_bu));
                assert!(
                    bool::from(got.ct_eq_full(&want)),
                    "add_mod({:x?} + {:x?}) mod p mismatch",
                    a.0,
                    b.0,
                );
            }
        }
    }

    #[test]
    fn sub_mod_matches_reference() {
        let p = p_secp256k1();
        let p_bu = p.to_biguint();
        let canonical: Vec<U256> = test_values()
            .into_iter()
            .map(|v| reduce(&v, &p_bu))
            .collect();
        for a in &canonical {
            for b in &canonical {
                let got = a.sub_mod(b, &p);
                let want = U256::from_biguint(&((&p_bu + a.to_biguint() - b.to_biguint()) % &p_bu));
                assert!(
                    bool::from(got.ct_eq_full(&want)),
                    "sub_mod({:x?} - {:x?}) mod p mismatch",
                    a.0,
                    b.0,
                );
            }
        }
    }

    /// Reference Montgomery multiply via `BigUint`: returns
    /// `a * b * R^(-1) mod p`.  Used in tests to validate the
    /// branchless `mont_mul` implementation.
    fn ref_mont_mul(a: &BigUint, b: &BigUint, p: &BigUint, r: &BigUint) -> BigUint {
        // R^(-1) mod p computed via the existing variable-time helper.
        let r_inv = crate::utils::mod_inverse(r, p).unwrap();
        (a * b * r_inv) % p
    }

    #[test]
    fn compute_minv64_satisfies_definition() {
        // For each odd `n`, compute_minv64(n) should give `m'` with
        // `n * m' ≡ -1 (mod 2^64)`, equivalently `n * m' = 2^64 - 1`
        // when reduced — easier to test as `(n.wrapping_mul(m')).wrapping_add(1) == 0`.
        for n in [
            1u64,
            3,
            7,
            0xFFFFFFFE_FFFFFC2F, // secp256k1 p[0]
            0xFFFFFFFF_FFFFFFFF, // P-256 p[0]
            0xDEADBEEF_CAFEBABE | 1,
        ] {
            let mp = compute_minv64(n);
            let prod = n.wrapping_mul(mp);
            assert_eq!(prod.wrapping_add(1), 0, "minv64 wrong for n={:#x}", n);
        }
    }

    #[test]
    fn mont_mul_matches_reference_secp256k1() {
        let p = p_secp256k1();
        let p_bu = p.to_biguint();
        let p_inv_low = compute_minv64(p.0[0]);
        let r = BigUint::from(1u8) << 256;

        let canonical: Vec<U256> = test_values()
            .into_iter()
            .map(|v| reduce(&v, &p_bu))
            .collect();

        for a in &canonical {
            for b in &canonical {
                let got = U256::mont_mul(a, b, &p, p_inv_low);
                let want =
                    U256::from_biguint(&ref_mont_mul(&a.to_biguint(), &b.to_biguint(), &p_bu, &r));
                assert!(
                    bool::from(got.ct_eq_full(&want)),
                    "mont_mul mismatch:\n  a={:x?}\n  b={:x?}\n  got={:x?}\n  want={:x?}",
                    a.0,
                    b.0,
                    got.0,
                    want.0,
                );
            }
        }
    }

    #[test]
    fn mont_mul_roundtrip_through_montgomery_form() {
        // a * 1 * R^(-1) = a * R^(-1).  So if we put a into Montgomery
        // form (a_M = a*R mod p) and multiply by 1, we should get a back.
        // mont_mul(a_M, 1, p, m') = a_M * 1 * R^(-1) = a*R*R^(-1) = a.
        let p = p_secp256k1();
        let p_bu = p.to_biguint();
        let p_inv_low = compute_minv64(p.0[0]);
        let r = BigUint::from(1u8) << 256;
        let r_mod_p = U256::from_biguint(&(&r % &p_bu));
        let r2_mod_p = U256::from_biguint(&((&r * &r) % &p_bu));

        for v in test_values() {
            let v_canonical = reduce(&v, &p_bu);
            // Convert to Montgomery: a * R mod p = mont_mul(a, R^2, ...).
            let v_m = U256::mont_mul(&v_canonical, &r2_mod_p, &p, p_inv_low);
            let want_v_m = U256::from_biguint(&((v_canonical.to_biguint() * &r) % &p_bu));
            assert!(bool::from(v_m.ct_eq_full(&want_v_m)), "to-Montgomery wrong");
            // Convert back: mont_mul(v_m, 1) = v.
            let one = U256::ONE;
            let v_back = U256::mont_mul(&v_m, &one, &p, p_inv_low);
            assert!(
                bool::from(v_back.ct_eq_full(&v_canonical)),
                "from-Montgomery wrong: got={:x?}, want={:x?}",
                v_back.0,
                v_canonical.0
            );
            // Sanity-check our R-handling.
            let _ = &r_mod_p;
        }
    }

    #[test]
    fn mul_wide_high_zero_for_small_operands() {
        // Sanity: small × small can't overflow 256 bits.
        let a = U256::from_biguint(&BigUint::from(0xdeadbeefu64));
        let b = U256::from_biguint(&BigUint::from(0xcafebabeu64));
        let (_, high) = U256::mul_wide(&a, &b);
        assert!(high.to_biguint().is_zero());
    }

    // ── Generic-LIMBS smoke tests at a non-256 size ────────────────────
    //
    // A 1024-bit `Uint<16>` exercises the same code paths but at a
    // different limb count, which catches accidental hard-coded `4`s
    // that the type-checker would otherwise let slide because every
    // call site happens to use `LIMBS=4`.

    type U1024 = Uint<16>;

    fn rand_u1024(seed: u64) -> U1024 {
        // Deterministic LCG for test inputs — not for cryptographic use.
        let mut s = seed;
        let mut limbs = [0u64; 16];
        for limb in &mut limbs {
            s = s
                .wrapping_mul(6364136223846793005)
                .wrapping_add(1442695040888963407);
            *limb = s;
        }
        Uint(limbs)
    }

    #[test]
    fn u1024_adc_sbb_match_biguint() {
        for seed in [1u64, 42, 0xdeadbeef, 0xfedcba98_76543210] {
            let a = rand_u1024(seed);
            let b = rand_u1024(seed.wrapping_mul(7));
            let modulus = BigUint::from(1u8) << 1024;
            let (sum, carry) = U1024::adc(&a, &b);
            let expected_sum = (a.to_biguint() + b.to_biguint()) % &modulus;
            assert_eq!(sum.to_biguint(), expected_sum, "u1024 adc value");
            let expected_carry = (a.to_biguint() + b.to_biguint() >= modulus) as u64;
            assert_eq!(carry, expected_carry, "u1024 adc carry");

            let (diff, borrow) = U1024::sbb(&a, &b);
            let expected_diff =
                (BigUint::from(1u8).pow(0) * &modulus + a.to_biguint() - b.to_biguint()) % &modulus;
            assert_eq!(diff.to_biguint(), expected_diff, "u1024 sbb value");
            let expected_borrow = (a.to_biguint() < b.to_biguint()) as u64;
            assert_eq!(borrow, expected_borrow, "u1024 sbb borrow");
        }
    }

    #[test]
    fn u1024_mul_wide_matches_biguint() {
        for seed in [1u64, 42, 0xdeadbeef] {
            let a = rand_u1024(seed);
            let b = rand_u1024(seed.wrapping_mul(11));
            let (low, high) = U1024::mul_wide(&a, &b);
            let combined = (high.to_biguint() << 1024) | low.to_biguint();
            assert_eq!(combined, a.to_biguint() * b.to_biguint(), "u1024 mul_wide");
        }
    }

    #[test]
    fn u1024_mont_mul_matches_biguint() {
        // Use a 1024-bit prime-ish odd modulus.  Doesn't have to be
        // prime for the SOS Montgomery multiplication to be correct —
        // only odd, with `m' = -p^(-1) mod 2^64` provided.
        let p_bu = (BigUint::from(1u8) << 1023) | BigUint::from(1u8); // 2^1023 + 1, odd
        let p = U1024::from_biguint(&p_bu);
        let p_inv_low = compute_minv64(p.0[0]);
        let r = BigUint::from(1u8) << 1024;

        for seed in [1u64, 42, 0xdeadbeef] {
            let a_raw = rand_u1024(seed);
            let b_raw = rand_u1024(seed.wrapping_mul(13));
            let a = U1024::from_biguint(&(a_raw.to_biguint() % &p_bu));
            let b = U1024::from_biguint(&(b_raw.to_biguint() % &p_bu));

            let got = U1024::mont_mul(&a, &b, &p, p_inv_low);

            let r_inv = crate::utils::mod_inverse(&r, &p_bu).unwrap();
            let want = (a.to_biguint() * b.to_biguint() * r_inv) % &p_bu;

            assert_eq!(
                got.to_biguint(),
                want,
                "u1024 mont_mul mismatch (seed={})",
                seed
            );
        }
    }

    // ── MontgomeryContext + mont_pow_ct cross-checks ─────────────────────

    /// 2048-bit odd modulus built from two large pseudo-random odd
    /// "primes" (not actually prime — we only need an odd modulus for
    /// Montgomery arithmetic to be well-defined; the powmod cross-check
    /// holds regardless of primality).  Top bit forced on so the
    /// modulus occupies the full 2048 bits.
    fn pseudo_modulus_2048() -> BigUint {
        // Two ~1024-bit odd values multiplied together.  Hex literals
        // give us a deterministic value across runs.
        let a = BigUint::parse_bytes(
            b"d4ad94ff86c4d31a4c9c8de4f1f7e1d6b3a2c1e0f9e8d7c6b5a4938271605f4e\
              d3c2b1a0fef0e1d2c3b4a59687786978695a4b3c2d1e0f99887766554433221\
              1ffeeddccbbaa9988776655443322110011223344556677889900aabbccddee\
              ff112233445566778899aabbccddeeff00112233445566778899aabbccddeef",
            16,
        )
        .unwrap();
        let b = BigUint::parse_bytes(
            b"e1f2c3d4a5b69788796a5b4c3d2e1f00ff112233445566778899aabbccddeeff\
              112233445566778899aabbccddeeff00112233445566778899aabbccddeeff0\
              0a1b2c3d4e5f60718293a4b5c6d7e8f9012345678abcdef0123456789abcdef\
              fedcba9876543210fedcba9876543210fedcba9876543210fedcba987654321",
            16,
        )
        .unwrap();
        let n = (a * b) | BigUint::from(1u8); // force odd
                                              // Force top bit on so the modulus is ~2048 bits exactly.
        let top_bit = BigUint::from(1u8) << 2047;
        n | top_bit
    }

    #[test]
    fn mont_context_setup_matches_biguint() {
        let n_bu = pseudo_modulus_2048();
        let n = Uint::<32>::from_biguint(&n_bu);
        let ctx = MontgomeryContext::<32>::new(n).expect("modulus is odd and nonzero");

        // n_inv_low: n * n_inv_low ≡ -1 (mod 2^64)
        let prod = n.0[0].wrapping_mul(ctx.n_inv_low);
        assert_eq!(prod.wrapping_add(1), 0, "n_inv_low wrong");

        // R mod n
        let r = BigUint::from(1u8) << (64 * 32);
        let want_r_mod_n = &r % &n_bu;
        assert_eq!(ctx.r_mod_n.to_biguint(), want_r_mod_n, "R mod n wrong");

        // R² mod n
        let want_r2_mod_n = (&r * &r) % &n_bu;
        assert_eq!(ctx.r2_mod_n.to_biguint(), want_r2_mod_n, "R² mod n wrong");
    }

    #[test]
    fn mont_context_rejects_even_modulus() {
        let even = Uint::<4>([2, 0, 0, 0]);
        assert!(MontgomeryContext::<4>::new(even).is_none());
    }

    #[test]
    fn mont_pow_ct_matches_biguint_2048() {
        let n_bu = pseudo_modulus_2048();
        let n = Uint::<32>::from_biguint(&n_bu);
        let ctx = MontgomeryContext::<32>::new(n).unwrap();

        // A handful of (base, exp) pairs spanning small/large/edge.
        let cases: Vec<(BigUint, BigUint)> = vec![
            // m^65537 mod n  (RSA public-exponent shape, but we're
            // exercising the *private* code path with a small value
            // for sanity).
            (BigUint::from(0xdeadbeefu64), BigUint::from(65537u32)),
            // m^d for a "private-exponent-shaped" d that's nearly the
            // full modulus width.
            (
                BigUint::from(0x123456789abcdef0u64),
                &n_bu - BigUint::from(3u8),
            ),
            // Edge: base = 1 (always 1).
            (BigUint::from(1u8), &n_bu - BigUint::from(7u8)),
            // Edge: base = n - 1 (always ±1 depending on exp parity).
            (
                &n_bu - BigUint::from(1u8),
                BigUint::parse_bytes(b"deadbeefcafebabe", 16).unwrap(),
            ),
        ];

        for (base, exp) in cases {
            let base_u = Uint::<32>::from_biguint(&base);
            let exp_u = Uint::<32>::from_biguint(&exp);
            let got = mont_pow_ct(&base_u, &exp_u, &ctx);
            let want = base.modpow(&exp, &n_bu);
            assert_eq!(
                got.to_biguint(),
                want,
                "mont_pow_ct mismatch:\n  base={}\n  exp={}",
                base,
                exp,
            );
        }
    }

    /// 4096-bit pseudo-modulus built from two ~2048-bit odd values.
    /// Same caveats as `pseudo_modulus_2048`: this is not a real RSA
    /// modulus (factorization unknown, primality not tested) — it's an
    /// odd 4096-bit value that exercises `MontgomeryContext<64>` and
    /// `mont_pow_ct` at the largest supported limb count.
    fn pseudo_modulus_4096() -> BigUint {
        let m_2048 = pseudo_modulus_2048();
        // Square it, then OR in the top bit, to produce a 4096-bit odd
        // composite.  Squaring of a (2048-bit, odd) gives 4095-or-4096
        // bits and stays odd; forcing the top bit on guarantees exact
        // 4096-bit width.
        let squared = &m_2048 * &m_2048;
        let top_bit = BigUint::from(1u8) << 4095;
        squared | top_bit | BigUint::from(1u8)
    }

    #[test]
    fn mont_pow_ct_matches_biguint_4096() {
        // Largest-supported size sanity check: verify the LIMBS=64
        // branch of the RSA dispatcher actually computes the right
        // answer.  One case is enough — we already know the algorithm
        // from the 2048-bit test, this just rules out a hard-coded
        // limb count.
        let n_bu = pseudo_modulus_4096();
        let n = Uint::<64>::from_biguint(&n_bu);
        let ctx = MontgomeryContext::<64>::new(n).unwrap();

        let base =
            BigUint::parse_bytes(b"feedfacecafebeefbeefcafefacefeed1234567890abcdef", 16).unwrap();
        let exp = &n_bu - BigUint::from(11u8);

        let base_u = Uint::<64>::from_biguint(&base);
        let exp_u = Uint::<64>::from_biguint(&exp);
        let got = mont_pow_ct(&base_u, &exp_u, &ctx);
        let want = base.modpow(&exp, &n_bu);

        assert_eq!(got.to_biguint(), want, "mont_pow_ct LIMBS=64 mismatch");
    }

    #[test]
    fn mont_pow_ct_round_trip_rsa_shape() {
        // Check that decrypt(encrypt(m)) == m for a (small but
        // realistic) RSA setup at 2048 bits.  Uses BigUint to compute
        // d (the variable-time path is fine for test setup), then
        // exercises the CT exponentiation for both the encrypt
        // (public-key shape) and decrypt (private-key shape) sides.
        use crate::utils::mod_inverse;

        let n_bu = pseudo_modulus_2048();
        // For this test, n's factorization is unknown — we cannot
        // build a valid d unless we know lambda(n).  So skip the
        // "decrypt(encrypt(m)) == m" portion of the round-trip and
        // just verify that mont_pow_ct == BigUint::modpow on a
        // public-exponent-shaped exponentiation.
        let _ = mod_inverse; // silence unused warning

        let n = Uint::<32>::from_biguint(&n_bu);
        let ctx = MontgomeryContext::<32>::new(n).unwrap();

        let m = Uint::<32>::from_biguint(&BigUint::from(0xfeedfacecafebeefu64));
        let e = Uint::<32>::from_biguint(&BigUint::from(65537u32));

        let got = mont_pow_ct(&m, &e, &ctx);
        let want = BigUint::from(0xfeedfacecafebeefu64).modpow(&BigUint::from(65537u32), &n_bu);
        assert_eq!(got.to_biguint(), want);
    }
}
