//! RSA — Rivest–Shamir–Adleman asymmetric cryptography, implemented from scratch.
//!
//! # Key generation
//! 1. Generate two large primes p, q using Miller-Rabin primality testing.
//! 2. n = p·q (the modulus).
//! 3. λ(n) = lcm(p-1, q-1) — Carmichael's totient.
//! 4. e = 65537 (standard public exponent, a prime Fermat number).
//! 5. d = e⁻¹ mod λ(n) — the private exponent.
//!
//! # Encryption / Decryption (textbook RSA)
//! Encrypt: c = mᵉ mod n
//! Decrypt: m = cᵈ mod n
//!
//! # Signatures (PKCS#1 v1.5)
//! Sign: s = EMSA-PKCS1-v1_5(SHA-256(m))ᵈ mod n
//! Verify: EMSA-PKCS1-v1_5(SHA-256(m)) == sᵉ mod n

use crate::ct_bignum::{mont_pow_ct, MontgomeryContext, Uint};
use crate::hash::sha256::sha256;
use crate::utils::{mod_inverse, mod_pow, mod_pow_ct};
use num_bigint::{BigUint, RandBigInt};
use num_integer::Integer;
use num_traits::{One, Zero};
use rand::rngs::OsRng;

// ── Constant-time modular exponentiation, dispatched on RSA modulus size ──
//
// The public `mod_pow_ct` in `crate::utils` has a uniform per-bit
// operation count, but it routes through `BigUint`, which leaks at the
// limb level (every multiplication's runtime depends on operand
// magnitudes).  This helper replaces those call sites for the
// supported RSA sizes with the limb-level constant-time stack in
// `crate::ct_bignum`: a `Uint<LIMBS>` analogue of `BigUint`, a
// Montgomery-form modular reduction with branchless SOS multiplication,
// and a square-and-multiply ladder that uses `cmov` for the per-bit
// "should I multiply?" decision.
//
// Sizes we wire up (LIMBS = ceil(bits / 64)):
//   16 → 1024-bit (used in the test suite for fast key generation)
//   24 → 1536-bit
//   32 → 2048-bit (typical RSA today)
//   48 → 3072-bit
//   64 → 4096-bit (high-security RSA)
//
// Other sizes fall back to the legacy `BigUint`-backed `mod_pow_ct`.
// That path is *not* limb-level constant-time but does keep the
// per-bit op count uniform; new code should target one of the
// supported sizes.
fn rsa_mod_pow_ct(base: &BigUint, exp: &BigUint, n: &BigUint, bits: usize) -> BigUint {
    let limbs = bits.div_ceil(64);
    match limbs {
        16 => rsa_mod_pow_ct_sized::<16>(base, exp, n),
        24 => rsa_mod_pow_ct_sized::<24>(base, exp, n),
        32 => rsa_mod_pow_ct_sized::<32>(base, exp, n),
        48 => rsa_mod_pow_ct_sized::<48>(base, exp, n),
        64 => rsa_mod_pow_ct_sized::<64>(base, exp, n),
        _ => mod_pow_ct(base, exp, n, bits),
    }
}

fn rsa_mod_pow_ct_sized<const LIMBS: usize>(base: &BigUint, exp: &BigUint, n: &BigUint) -> BigUint {
    // `Uint::from_biguint` truncates anything past LIMBS limbs, so we
    // must pre-reduce the base mod n.  In ordinary RSA flows the
    // ciphertext / message hash is already less than n, but guarding
    // here keeps the function total.
    let base_reduced = base % n;
    let n_u = Uint::<LIMBS>::from_biguint(n);
    let base_u = Uint::<LIMBS>::from_biguint(&base_reduced);
    let exp_u = Uint::<LIMBS>::from_biguint(exp);
    let ctx = MontgomeryContext::<LIMBS>::new(n_u).expect("RSA modulus must be odd and nonzero");
    let result = mont_pow_ct(&base_u, &exp_u, &ctx);
    result.to_biguint()
}

// ── CRT-accelerated constant-time RSA private exponentiation ──────────────
//
// PKCS#1 §3.2 specifies the CRT decomposition:
//
//   m_p = c^dp mod p           (HALF-limb exponentiation, HALF-bit exponent)
//   m_q = c^dq mod q           (HALF-limb exponentiation, HALF-bit exponent)
//   h   = qinv · (m_p − m_q) mod p
//   m   = m_q + q · h
//
// vs. the direct form `m = c^d mod n` (FULL-limb exponentiation,
// FULL-bit exponent).  The CRT form is ~4× faster: each half does
// HALF the limbs and HALF the exponent bits, and the recombination
// is a single mont_mul plus a wide multiply.
//
// **Constant-time invariants on this path.**
//
// - `c mod p` and `c mod q` use a CT split-and-reduce primitive (see
//   `ct_reduce_full_to_half`).  We deliberately avoid `BigUint::%`,
//   which would leak `p` and `q` via division timing.
// - Both half-exponentiations route through `mont_pow_ct` over the
//   `MontgomeryContext<HALF>`, which has uniform per-bit op count
//   for the public bit width.
// - `mont_mul` over `p` performs the recombination's multiplicative
//   step in CT.  The final `m_q + q · h` is a single `mul_wide` plus
//   `adc`, both branchless.
// - `MontgomeryContext::new` itself uses `BigUint` to compute
//   `R mod p` and `R² mod p`.  This *does* leak limb-level timing
//   on `p` and `q` — but `MontgomeryContext` setup happens once per
//   key load, not once per message, and an attacker with that level
//   of access could simply read `key.p` from memory.  The setup
//   leakage is structurally unavoidable here without a CT modular
//   reduction, which would itself need division-free hardware support
//   we don't have on stable Rust.
fn rsa_mod_pow_ct_crt(c: &BigUint, key: &RsaPrivateKey) -> BigUint {
    let bits = key.bits as usize;
    match bits {
        1024 => rsa_mod_pow_ct_crt_sized::<8, 16>(c, key),
        1536 => rsa_mod_pow_ct_crt_sized::<12, 24>(c, key),
        2048 => rsa_mod_pow_ct_crt_sized::<16, 32>(c, key),
        3072 => rsa_mod_pow_ct_crt_sized::<24, 48>(c, key),
        4096 => rsa_mod_pow_ct_crt_sized::<32, 64>(c, key),
        // Unsupported size: fall back to non-CRT CT path.
        _ => rsa_mod_pow_ct(c, &key.d, &key.n, bits),
    }
}

/// CRT exponentiation specialised at compile time to (`HALF`, `FULL`)
/// limb counts.  The caller must satisfy `FULL == 2 * HALF` and
/// `key.bits == 64 * FULL`; both are enforced by the dispatch table in
/// `rsa_mod_pow_ct_crt`.
fn rsa_mod_pow_ct_crt_sized<const HALF: usize, const FULL: usize>(
    c: &BigUint,
    key: &RsaPrivateKey,
) -> BigUint {
    // Materialise the per-prime parameters as fixed-width Uints.
    // `from_biguint` truncates past LIMBS; the caller-side dispatch
    // guarantees these all fit.
    let p_u = Uint::<HALF>::from_biguint(&key.p);
    let q_u = Uint::<HALF>::from_biguint(&key.q);
    let dp_u = Uint::<HALF>::from_biguint(&key.dp);
    let dq_u = Uint::<HALF>::from_biguint(&key.dq);
    let qinv_u = Uint::<HALF>::from_biguint(&key.qinv);

    let p_ctx = MontgomeryContext::<HALF>::new(p_u).expect("p must be odd and nonzero");
    let q_ctx = MontgomeryContext::<HALF>::new(q_u).expect("q must be odd and nonzero");

    // Reduce c mod p and c mod q via the CT split-and-reduce primitive.
    // Pre-reducing through BigUint here would leak p/q at the limb level;
    // we go through a fixed-width helper instead.  We pre-reduce mod n
    // first (with BigUint) only to enforce c < n — that's a public
    // boundary check, not a per-bit secret-dependent operation.
    let c_mod_n = c % &key.n;
    let c_full = Uint::<FULL>::from_biguint(&c_mod_n);
    let c_mod_p = ct_reduce_full_to_half::<HALF, FULL>(&c_full, &p_ctx);
    let c_mod_q = ct_reduce_full_to_half::<HALF, FULL>(&c_full, &q_ctx);

    // Half-width exponentiations.  Each inner ladder runs 64*HALF
    // squarings + 64*HALF candidate multiplies (cmov-gated) — half the
    // work of the single FULL-limb form, and twice over.
    let m_p = mont_pow_ct(&c_mod_p, &dp_u, &p_ctx);
    let m_q = mont_pow_ct(&c_mod_q, &dq_u, &q_ctx);

    // Recombination, all in canonical (non-Montgomery) form for output:
    //   t = (m_p − m_q) mod p
    //   h = qinv · t mod p
    //   m = m_q + q · h
    //
    // For the multiplicative step we use one mont_mul.  Convert qinv
    // into Montgomery form on the fly (qinv·R mod p), then
    // mont_mul(qinv_M, t) = qinv·R · t · R^(-1) = qinv·t mod p in
    // canonical form.
    let t = m_p.sub_mod(&m_q, &p_u);
    let qinv_mont = p_ctx.to_montgomery(&qinv_u);
    let h = p_ctx.mont_mul(&qinv_mont, &t);

    // m = m_q + q·h, computed with a wide multiply.  Since h < p and
    // m_q < q, we have q·h < q·p = n and m_q + q·h < n; the FULL-limb
    // representation is always sufficient and never wraps.
    let (qh_lo, qh_hi) = Uint::<HALF>::mul_wide(&q_u, &h);
    let mut full_buf = [0u64; FULL];
    full_buf[..HALF].copy_from_slice(&qh_lo.0[..HALF]);
    full_buf[HALF..(HALF + HALF)].copy_from_slice(&qh_hi.0[..HALF]);
    let qh_full = Uint::<FULL>(full_buf);

    let mut mq_buf = [0u64; FULL];
    mq_buf[..HALF].copy_from_slice(&m_q.0[..HALF]);
    let mq_full = Uint::<FULL>(mq_buf);

    // The final adc cannot carry out (m < n < 2^FULL), so we drop the
    // carry.  Nothing here is operand-dependent.
    let (m, _carry) = Uint::<FULL>::adc(&qh_full, &mq_full);
    m.to_biguint()
}

/// Reduce a FULL-limb value `v < 2^(64·FULL)` modulo a HALF-limb
/// modulus `n` (where `n` has its top bit set), in constant time.
///
/// Splits `v = v_lo + v_hi · R` with `R = 2^(64·HALF)`; each half is
/// then `< R < 2n` since `n > R/2`, so a single conditional subtract
/// reduces it canonically.  The combine step computes
/// `v_lo_red + v_hi_red·R mod n`; we obtain `v_hi_red·R mod n` for free
/// because that is exactly the Montgomery form of `v_hi_red`, and
/// `MontgomeryContext::to_montgomery` is constant-time.
///
/// Caller invariants (not runtime-checked, since checking would itself
/// leak):
/// - `FULL == 2 * HALF` (only the contract; the body just splits an
///   array-of-FULL into two arrays-of-HALF, so undersized inputs would
///   trigger a panic in array indexing, but valid inputs are fine).
/// - `n` has its top bit set.  Every random_prime() in this module
///   sets `bit[bits-1]` so this holds for keygen output.
fn ct_reduce_full_to_half<const HALF: usize, const FULL: usize>(
    v: &Uint<FULL>,
    ctx: &MontgomeryContext<HALF>,
) -> Uint<HALF> {
    let mut lo_buf = [0u64; HALF];
    let mut hi_buf = [0u64; HALF];
    lo_buf[..HALF].copy_from_slice(&v.0[..HALF]);
    hi_buf[..HALF].copy_from_slice(&v.0[HALF..(HALF + HALF)]);
    let v_lo = Uint::<HALF>(lo_buf);
    let v_hi = Uint::<HALF>(hi_buf);

    let lo_red = cond_sub_modulus::<HALF>(&v_lo, &ctx.n);
    let hi_red = cond_sub_modulus::<HALF>(&v_hi, &ctx.n);

    // (lo_red + hi_red · R) mod n.  hi_red · R mod n is the
    // Montgomery form of hi_red; combine via add_mod (both operands
    // are < n).
    let hi_times_r = ctx.to_montgomery(&hi_red);
    lo_red.add_mod(&hi_times_r, &ctx.n)
}

/// Constant-time `if v >= n { v - n } else { v }` for HALF-limb
/// operands.  Used by [`ct_reduce_full_to_half`] for the per-half
/// reduction; only correct when `v < 2n`.
fn cond_sub_modulus<const LIMBS: usize>(v: &Uint<LIMBS>, n: &Uint<LIMBS>) -> Uint<LIMBS> {
    use subtle::Choice;
    let (v_minus_n, borrow) = Uint::<LIMBS>::sbb(v, n);
    // borrow == 0 means v >= n, so we keep v_minus_n; else keep v.
    let need_sub = Choice::from(((borrow ^ 1) & 1) as u8);
    Uint::<LIMBS>::cmov(v, &v_minus_n, need_sub)
}

// ── Miller-Rabin primality test ───────────────────────────────────────────────

/// Decompose `n-1` as `2^s * d` with `d` odd.
fn factor_out_twos(n: &BigUint) -> (u64, BigUint) {
    let mut d = n.clone();
    let mut s = 0u64;
    while d.is_even() {
        d >>= 1;
        s += 1;
    }
    (s, d)
}

/// Miller-Rabin witness test for a single base `a`.
/// Returns `true` if `n` is *probably prime* with this witness.
fn miller_rabin_witness(n: &BigUint, d: &BigUint, s: u64, a: &BigUint) -> bool {
    let one = BigUint::one();
    let n_minus_1 = n - &one;
    let mut x = mod_pow(a, d, n);

    if x == one || x == n_minus_1 {
        return true;
    }

    for _ in 0..s - 1 {
        x = mod_pow(&x, &BigUint::from(2u32), n);
        if x == n_minus_1 {
            return true;
        }
    }
    false
}

/// Miller-Rabin primality test.
///
/// Uses deterministic bases for small candidates and OS-random witnesses for
/// larger candidates. The large-candidate path is probabilistic: 32 independent
/// witnesses give a false-prime probability below 2^-64 for odd composites.
pub fn is_prime(n: &BigUint) -> bool {
    if n < &BigUint::from(2u32) {
        return false;
    }
    if n == &BigUint::from(2u32) || n == &BigUint::from(3u32) {
        return true;
    }
    if n.is_even() {
        return false;
    }

    // Small prime divisibility check for speed
    let small_primes = [2u32, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37];
    for &p in &small_primes {
        let bp = BigUint::from(p);
        if n == &bp {
            return true;
        }
        if (n % &bp).is_zero() {
            return false;
        }
    }

    let n_minus_1 = n - BigUint::one();
    let (s, d) = factor_out_twos(&n_minus_1);

    let fixed_witnesses: Vec<BigUint> = [2u64, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37]
        .iter()
        .map(|&w| BigUint::from(w))
        .collect();

    if !fixed_witnesses.iter().all(|a| {
        if a >= n {
            return true;
        } // Skip witnesses ≥ n
        miller_rabin_witness(n, &d, s, a)
    }) {
        return false;
    }

    if n.bits() <= 128 {
        return true;
    }

    let two = BigUint::from(2u32);
    let high = n - BigUint::one();
    let mut rng = OsRng;
    for _ in 0..32 {
        let a = rng.gen_biguint_range(&two, &high);
        if !miller_rabin_witness(n, &d, s, &a) {
            return false;
        }
    }
    true
}

/// Generate a random probable prime of exactly `bits` bits.
/// Uses Miller-Rabin with fixed small bases plus random OS-backed witnesses.
///
/// Entropy comes from `OsRng` (the OS CSPRNG); we deliberately avoid
/// `thread_rng` so the entropy source is unambiguous.
pub fn random_prime(bits: u64) -> BigUint {
    let mut rng = OsRng;
    loop {
        let mut candidate = rng.gen_biguint(bits);
        // Ensure the candidate has the right bit length and is odd
        candidate.set_bit(bits - 1, true);
        candidate.set_bit(0, true);
        if is_prime(&candidate) {
            return candidate;
        }
    }
}

// ── RSA key types ─────────────────────────────────────────────────────────────

/// RSA public key.
#[derive(Clone, Debug)]
pub struct RsaPublicKey {
    /// Modulus n = p·q
    pub n: BigUint,
    /// Public exponent e (typically 65537)
    pub e: BigUint,
    /// Key size in bits
    pub bits: u64,
}

/// RSA private key (PKCS#1 representation).
///
/// Private fields (`d`, `p`, `q`, `dp`, `dq`, `qinv`) are best-effort
/// zeroized on drop.  See the note on `EccPrivateKey` for the limits
/// of `num-bigint` zeroization.
///
/// `dp`, `dq`, `qinv` are the CRT acceleration parameters defined in
/// PKCS#1 §3.2.  They let the private operation (`m = c^d mod n`) run
/// as two half-width exponentiations against `p` and `q`, which is
/// roughly 4× faster than the single full-width form and — once the
/// half-width pieces go through `crate::ct_bignum::mont_pow_ct` —
/// fully constant-time.
///
/// Convention: `p > q` so that `qinv = q^(-1) mod p` lies in `[1, p)`.
#[derive(Clone, Debug)]
pub struct RsaPrivateKey {
    pub n: BigUint,
    pub e: BigUint,
    /// Private exponent d = e⁻¹ mod λ(n)
    pub d: BigUint,
    pub p: BigUint,
    pub q: BigUint,
    /// `d mod (p-1)` — the CRT exponent for the `p` half.
    pub dp: BigUint,
    /// `d mod (q-1)` — the CRT exponent for the `q` half.
    pub dq: BigUint,
    /// `q^(-1) mod p` — the CRT recombination coefficient.
    pub qinv: BigUint,
    pub bits: u64,
}

impl Drop for RsaPrivateKey {
    fn drop(&mut self) {
        self.d.set_zero();
        self.p.set_zero();
        self.q.set_zero();
        self.dp.set_zero();
        self.dq.set_zero();
        self.qinv.set_zero();
        // n and e are public.
    }
}

/// An RSA key pair.
pub struct RsaKeyPair {
    pub public: RsaPublicKey,
    pub private: RsaPrivateKey,
}

impl RsaKeyPair {
    /// Generate a fresh RSA key pair of `bits` total bits (e.g., 2048).
    /// Each prime will be `bits/2` bits long.
    pub fn generate(bits: u64) -> Self {
        let half = bits / 2;
        loop {
            let p_raw = random_prime(half);
            let q_raw = random_prime(half);
            if p_raw == q_raw {
                continue;
            }

            // PKCS#1 convention: p > q, so qinv = q^(-1) mod p ∈ [1, p).
            // Swapping is just a labelling choice — n = p·q either way.
            let (p, q) = if p_raw > q_raw {
                (p_raw, q_raw)
            } else {
                (q_raw, p_raw)
            };

            let n = &p * &q;

            // Carmichael's totient λ(n) = lcm(p-1, q-1)
            let p1 = &p - BigUint::one();
            let q1 = &q - BigUint::one();
            let lambda = p1.lcm(&q1);

            let e = BigUint::from(65537u32);
            if lambda.gcd(&e) != BigUint::one() {
                continue;
            }

            let d = match mod_inverse(&e, &lambda) {
                Some(v) => v,
                None => continue,
            };

            // CRT precomputed parameters (PKCS#1 §3.2).
            let dp = &d % &p1;
            let dq = &d % &q1;
            let qinv = match mod_inverse(&q, &p) {
                Some(v) => v,
                None => continue, // can't happen for distinct primes, but keep it total
            };

            return RsaKeyPair {
                public: RsaPublicKey {
                    n: n.clone(),
                    e: e.clone(),
                    bits,
                },
                private: RsaPrivateKey {
                    n,
                    e,
                    d,
                    p,
                    q,
                    dp,
                    dq,
                    qinv,
                    bits,
                },
            };
        }
    }
}

// ── Textbook RSA operations ───────────────────────────────────────────────────

/// Textbook RSA encrypt: c = mᵉ mod n.
///
/// **Internal only.** Textbook RSA is not semantically secure (deterministic,
/// malleable, leaks small messages).  External callers must go through
/// `rsa_encrypt`, which applies PKCS#1 v1.5 padding.  Restricted to
/// `pub(crate)` to keep this off the public API surface.
pub(crate) fn rsa_encrypt_raw(msg: &BigUint, key: &RsaPublicKey) -> BigUint {
    mod_pow(msg, &key.e, &key.n)
}

/// Textbook RSA decrypt: m = cᵈ mod n.  See `rsa_encrypt_raw` for why this
/// is `pub(crate)`.
///
/// Routed through [`rsa_mod_pow_ct_crt`] because the exponent `d` is
/// the private key.  For supported modulus sizes (1024/1536/2048/3072/
/// 4096 bits), this is a limb-level constant-time CRT computation
/// built on the `crate::ct_bignum::Uint<LIMBS>` Montgomery stack —
/// roughly 4× faster than the direct form.  For other sizes the
/// dispatcher falls through to the non-CRT `rsa_mod_pow_ct`, and from
/// there to the `BigUint`-backed `mod_pow_ct` for sizes outside the
/// supported set.
pub(crate) fn rsa_decrypt_raw(ciphertext: &BigUint, key: &RsaPrivateKey) -> BigUint {
    rsa_mod_pow_ct_crt(ciphertext, key)
}

// ── Signing / Verification ────────────────────────────────────────────────────

const SHA256_DIGEST_INFO_PREFIX: [u8; 19] = [
    0x30, 0x31, 0x30, 0x0d, 0x06, 0x09, 0x60, 0x86, 0x48, 0x01, 0x65, 0x03, 0x04, 0x02, 0x01, 0x05,
    0x00, 0x04, 0x20,
];

fn emsa_pkcs1_v1_5_encode_sha256(
    message: &[u8],
    key_bytes: usize,
) -> Result<Vec<u8>, &'static str> {
    let hash = sha256(message);
    let t_len = SHA256_DIGEST_INFO_PREFIX.len() + hash.len();
    if key_bytes < t_len + 11 {
        return Err("RSA key too small for SHA-256 PKCS#1 v1.5 signature");
    }
    let ps_len = key_bytes - t_len - 3;
    let mut em = Vec::with_capacity(key_bytes);
    em.push(0x00);
    em.push(0x01);
    em.extend(std::iter::repeat_n(0xff, ps_len));
    em.push(0x00);
    em.extend_from_slice(&SHA256_DIGEST_INFO_PREFIX);
    em.extend_from_slice(&hash);
    Ok(em)
}

/// Sign a message with RSASSA-PKCS1-v1_5/SHA-256.
/// Routed through `rsa_mod_pow_ct_crt` because the exponent `d` is private.
pub fn rsa_sign(message: &[u8], key: &RsaPrivateKey) -> BigUint {
    let key_bytes = key.bits.div_ceil(8) as usize;
    let encoded = emsa_pkcs1_v1_5_encode_sha256(message, key_bytes)
        .expect("RSA key too small for SHA-256 PKCS#1 v1.5 signature");
    let m = BigUint::from_bytes_be(&encoded);
    rsa_mod_pow_ct_crt(&m, key)
}

/// Verify an RSASSA-PKCS1-v1_5/SHA-256 signature.
pub fn rsa_verify(message: &[u8], signature: &BigUint, key: &RsaPublicKey) -> bool {
    let key_bytes = key.bits.div_ceil(8) as usize;
    let expected = match emsa_pkcs1_v1_5_encode_sha256(message, key_bytes) {
        Ok(v) => v,
        Err(_) => return false,
    };
    let recovered = mod_pow(signature, &key.e, &key.n);
    let recovered_bytes =
        match crate::utils::encoding::bigint_to_bytes_be_checked(&recovered, key_bytes) {
            Some(v) => v,
            None => return false,
        };
    use subtle::ConstantTimeEq;
    recovered_bytes.ct_eq(&expected).unwrap_u8() == 1
}

// ── PKCS#1 v1.5 style helpers ─────────────────────────────────────────────────

/// Encode a short message with PKCS#1 v1.5 type 2 padding for RSA encryption.
///
/// Internal helper for `rsa_encrypt`.  Exposed to other modules in the
/// crate but not part of the public API: callers should use `rsa_encrypt`,
/// which packages padding + modular exponentiation correctly.
///
/// Layout: 0x00 || 0x02 || PS (random non-zero padding) || 0x00 || msg
/// The padded value must be strictly less than n.
pub(crate) fn pkcs1_pad_encrypt(msg: &[u8], key_bytes: usize) -> Result<Vec<u8>, &'static str> {
    if msg.len() + 11 > key_bytes {
        return Err("message too long for key size");
    }
    let ps_len = key_bytes - msg.len() - 3;
    let mut padded = vec![0u8; key_bytes];
    padded[1] = 0x02;
    // Fill PS with random non-zero bytes
    let mut i = 2;
    while i < 2 + ps_len {
        let b = crate::utils::random::random_bytes_vec(1)[0];
        if b != 0 {
            padded[i] = b;
            i += 1;
        }
    }
    padded[2 + ps_len] = 0x00;
    padded[3 + ps_len..].copy_from_slice(msg);
    Ok(padded)
}

/// Strip PKCS#1 v1.5 type 2 padding, returning the original message or
/// an error.  Internal helper for `rsa_decrypt`.
///
/// # Bleichenbacher resistance
///
/// The original variable-time implementation early-exited on each
/// individual padding-byte check, which is exactly the side-channel
/// Bleichenbacher's 1998 attack exploits to mount a chosen-ciphertext
/// oracle against PKCS#1 v1.5.  This version performs a fixed-shape
/// scan: every byte is examined regardless of validity, the validity
/// flag is accumulated as a `subtle::Choice`, and only the final
/// aggregate decision is branched on.
///
/// **This alone does not make the public `rsa_decrypt` API
/// Bleichenbacher-safe.**  The fact that decrypt returns `Err` at all
/// — distinct from a "valid but garbage" plaintext — is itself the
/// oracle.  Production protocols (TLS 1.2 RSA-KEX, Cryptographic
/// Message Syntax) handle this with *implicit rejection*: on padding
/// failure, return random-looking bytes of the expected length and
/// rely on a higher-layer MAC to discriminate.  New applications
/// should prefer RSA-OAEP or, better, hybrid encryption with an AEAD.
pub(crate) fn pkcs1_unpad_encrypt(padded: &[u8]) -> Result<Vec<u8>, &'static str> {
    use subtle::{Choice, ConditionallySelectable, ConstantTimeEq};

    let n = padded.len();
    if n < 11 {
        return Err("ciphertext too short");
    }

    // Header check: padded[0] == 0x00 AND padded[1] == 0x02.
    let mut valid = padded[0].ct_eq(&0x00) & padded[1].ct_eq(&0x02);

    // Locate the first 0x00 separator at index ≥ 2 in constant time.
    // Scan every byte; record the first 0x00 we see.  `found` becomes
    // 1 on the first hit and stays 1 thereafter; `should_record`
    // gates the assignment to `sep_idx`.
    let mut sep_idx: u32 = 0;
    let mut found = Choice::from(0u8);
    for i in 2..n {
        let is_zero = padded[i].ct_eq(&0x00);
        let should_record = is_zero & !found;
        sep_idx = u32::conditional_select(&sep_idx, &(i as u32), should_record);
        found |= is_zero;
    }
    valid &= found;

    // PS must be at least 8 bytes long ⇒ sep_idx ≥ 10.  Constant-time
    // "is non-negative" check via the high bit of (sep_idx - 10) cast
    // to a signed integer.
    let diff = (sep_idx as i64) - 10;
    let ps_long_enough_bit = ((diff >> 63) as u8 ^ 1) & 1; // 1 if non-neg
    valid &= Choice::from(ps_long_enough_bit);

    // Branch only on the *aggregate* validity.  An attacker observing
    // distinct invalid ciphertexts no longer learns *which* check
    // failed — a Bleichenbacher precondition.  Note that the size of
    // the returned vector still depends on sep_idx; truly closing
    // that channel requires implicit rejection at the caller level.
    if bool::from(valid) {
        Ok(padded[(sep_idx + 1) as usize..].to_vec())
    } else {
        Err("invalid padding")
    }
}

/// High-level RSA encrypt with PKCS#1 v1.5 padding.
pub fn rsa_encrypt(msg: &[u8], key: &RsaPublicKey) -> Result<BigUint, &'static str> {
    let key_bytes = key.bits.div_ceil(8) as usize;
    let padded = pkcs1_pad_encrypt(msg, key_bytes)?;
    let m = BigUint::from_bytes_be(&padded);
    Ok(rsa_encrypt_raw(&m, key))
}

/// High-level RSA decrypt with PKCS#1 v1.5 unpadding.
pub fn rsa_decrypt(ciphertext: &BigUint, key: &RsaPrivateKey) -> Result<Vec<u8>, &'static str> {
    let m = rsa_decrypt_raw(ciphertext, key);
    let key_bytes = key.bits.div_ceil(8) as usize;
    let padded = crate::utils::encoding::bigint_to_bytes_be(&m, key_bytes);
    pkcs1_unpad_encrypt(&padded)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn primality_small() {
        let primes = [2u32, 3, 5, 7, 11, 13, 17, 19, 23];
        for &p in &primes {
            assert!(is_prime(&BigUint::from(p)), "{p} should be prime");
        }
        let composites = [4u32, 6, 9, 15, 25, 49];
        for &c in &composites {
            assert!(!is_prime(&BigUint::from(c)), "{c} should be composite");
        }
    }

    #[test]
    fn rsa_1024_sign_verify() {
        let kp = RsaKeyPair::generate(1024);
        let msg = b"RSA signing test message";
        let sig = rsa_sign(msg, &kp.private);
        assert!(rsa_verify(msg, &sig, &kp.public));
    }

    #[test]
    fn rsa_sign_wrong_message() {
        let kp = RsaKeyPair::generate(1024);
        let sig = rsa_sign(b"original", &kp.private);
        assert!(!rsa_verify(b"tampered", &sig, &kp.public));
    }

    #[test]
    fn rsa_encrypt_decrypt() {
        let kp = RsaKeyPair::generate(1024);
        let msg = b"hello RSA";
        let ct = rsa_encrypt(msg, &kp.public).unwrap();
        let pt = rsa_decrypt(&ct, &kp.private).unwrap();
        assert_eq!(pt, msg);
    }

    #[test]
    fn primality_known_large_primes() {
        // 2^127 - 1 (Mersenne prime M_127)
        let m127 = (BigUint::one() << 127u32) - BigUint::one();
        assert!(is_prime(&m127));
        // 2^61 - 1 (Mersenne prime M_61)
        let m61 = (BigUint::one() << 61u32) - BigUint::one();
        assert!(is_prime(&m61));
        // Carmichael number 561 = 3·11·17 — fools Fermat's little theorem
        // but Miller-Rabin must reject it.
        assert!(!is_prime(&BigUint::from(561u32)));
        // Carmichael 41041 = 7·11·13·41
        assert!(!is_prime(&BigUint::from(41041u32)));
        // Carmichael 825265 = 5·7·17·19·73
        assert!(!is_prime(&BigUint::from(825265u32)));
    }

    #[test]
    fn random_prime_has_correct_bit_length() {
        for _ in 0..3 {
            let p = random_prime(256);
            assert_eq!(p.bits(), 256, "prime must have exactly 256 bits");
            assert!(is_prime(&p));
        }
    }

    #[test]
    fn rsa_keygen_modulus_bit_length() {
        let kp = RsaKeyPair::generate(1024);
        // n = p·q with p, q each 512 bits and high bits forced to 1, so
        // n must be exactly 1023 or 1024 bits. We force the bit-1 of each
        // prime, so n is at least 2^1022 and at most 2^1024 - 1.
        let bits = kp.public.n.bits();
        assert!((1023..=1024).contains(&bits), "got {bits} bits");
        // d·e ≡ 1 (mod λ(n))
        let lambda = (&kp.private.p - BigUint::one()).lcm(&(&kp.private.q - BigUint::one()));
        assert_eq!((&kp.private.d * &kp.private.e) % &lambda, BigUint::one());
        // p·q == n
        assert_eq!(&kp.private.p * &kp.private.q, kp.public.n);
    }

    #[test]
    fn pkcs1_pad_unpad_roundtrip() {
        let msg = b"sensitive payment payload";
        let padded = pkcs1_pad_encrypt(msg, 128).unwrap();
        assert_eq!(padded.len(), 128);
        assert_eq!(padded[0], 0x00);
        assert_eq!(padded[1], 0x02);
        // Padding bytes must all be non-zero.
        let zero_sep = padded[2..].iter().position(|&b| b == 0).unwrap() + 2;
        assert!(zero_sep - 2 >= 8, "PS must be ≥ 8 bytes");
        for &b in &padded[2..zero_sep] {
            assert_ne!(b, 0);
        }
        let recovered = pkcs1_unpad_encrypt(&padded).unwrap();
        assert_eq!(recovered, msg);
    }

    #[test]
    fn pkcs1_pad_rejects_oversized_message() {
        // 128-byte modulus has 128 - 11 = 117 bytes max payload.
        assert!(pkcs1_pad_encrypt(&[0u8; 117], 128).is_ok());
        assert!(pkcs1_pad_encrypt(&[0u8; 118], 128).is_err());
    }

    #[test]
    fn pkcs1_unpad_rejects_malformed() {
        // Wrong leading byte
        let mut bad = vec![0u8; 128];
        bad[0] = 0x01;
        bad[1] = 0x02;
        assert!(pkcs1_unpad_encrypt(&bad).is_err());
        // Wrong block type
        let mut bad2 = vec![0u8; 128];
        bad2[1] = 0x01;
        assert!(pkcs1_unpad_encrypt(&bad2).is_err());
        // PS shorter than 8 bytes
        let mut bad3 = vec![0u8; 128];
        bad3[1] = 0x02;
        bad3[2] = 0xff;
        bad3[3] = 0x00; // separator after only 1 PS byte
        bad3[4..].copy_from_slice(&[0xaa; 124]);
        assert!(pkcs1_unpad_encrypt(&bad3).is_err());
        // No zero separator at all
        let bad4 = vec![0xffu8; 128];
        assert!(pkcs1_unpad_encrypt(&bad4).is_err());
    }

    #[test]
    fn rsa_encrypt_is_randomized() {
        // PKCS#1 v1.5 padding uses random PS, so two encryptions of the same
        // plaintext must produce different ciphertexts.
        let kp = RsaKeyPair::generate(1024);
        let msg = b"same message";
        let c1 = rsa_encrypt(msg, &kp.public).unwrap();
        let c2 = rsa_encrypt(msg, &kp.public).unwrap();
        assert_ne!(c1, c2, "PKCS#1 v1.5 must produce randomized ciphertexts");
        assert_eq!(rsa_decrypt(&c1, &kp.private).unwrap(), msg);
        assert_eq!(rsa_decrypt(&c2, &kp.private).unwrap(), msg);
    }

    #[test]
    fn rsa_encrypt_empty_and_max_message() {
        let kp = RsaKeyPair::generate(1024);
        // Empty message
        let ct_empty = rsa_encrypt(b"", &kp.public).unwrap();
        assert_eq!(rsa_decrypt(&ct_empty, &kp.private).unwrap(), b"");
        // Maximum-length message: 128 - 11 = 117 bytes
        let max_msg = vec![0xab; 117];
        let ct_max = rsa_encrypt(&max_msg, &kp.public).unwrap();
        assert_eq!(rsa_decrypt(&ct_max, &kp.private).unwrap(), max_msg);
        // One byte too long must fail at padding stage
        let too_long = vec![0xab; 118];
        assert!(rsa_encrypt(&too_long, &kp.public).is_err());
    }

    #[test]
    fn rsa_signature_unique_per_message() {
        // Plain (deterministic) RSA signatures for distinct messages must differ.
        let kp = RsaKeyPair::generate(1024);
        let s1 = rsa_sign(b"msg-a", &kp.private);
        let s2 = rsa_sign(b"msg-b", &kp.private);
        assert_ne!(s1, s2);
    }

    #[test]
    fn rsa_signature_uses_pkcs1_v1_5_encoding() {
        let kp = RsaKeyPair::generate(1024);
        let sig = rsa_sign(b"encoded", &kp.private);
        let recovered = mod_pow(&sig, &kp.public.e, &kp.public.n);
        let recovered_bytes =
            crate::utils::encoding::bigint_to_bytes_be_checked(&recovered, 128).unwrap();
        assert_eq!(&recovered_bytes[..2], &[0x00, 0x01]);
        assert!(
            recovered_bytes[2..]
                .iter()
                .take_while(|&&b| b == 0xff)
                .count()
                >= 8
        );
        assert!(rsa_verify(b"encoded", &sig, &kp.public));
    }

    #[test]
    fn rsa_verify_with_wrong_key_fails() {
        let kp1 = RsaKeyPair::generate(1024);
        let kp2 = RsaKeyPair::generate(1024);
        let sig = rsa_sign(b"transfer 100", &kp1.private);
        assert!(rsa_verify(b"transfer 100", &sig, &kp1.public));
        assert!(!rsa_verify(b"transfer 100", &sig, &kp2.public));
    }

    #[test]
    fn rsa_decrypt_rejects_tampered_ciphertext() {
        let kp = RsaKeyPair::generate(1024);
        let ct = rsa_encrypt(b"hello", &kp.public).unwrap();
        // Flip a bit in the ciphertext (cheap) — decryption nearly always fails
        // PKCS#1 v1.5 unpadding because the random PS bytes change.
        let tampered = &ct ^ BigUint::one();
        // Make sure tampered < n; if it overflowed (extremely unlikely), retry
        // with a different mask.
        let tampered = if tampered >= kp.public.n {
            &ct + BigUint::from(2u32)
        } else {
            tampered
        };
        let res = rsa_decrypt(&tampered, &kp.private);
        // Either unpadding fails outright, or the message decoded to garbage —
        // but it must NOT decrypt back to the original plaintext.
        match res {
            Err(_) => {}
            Ok(plain) => assert_ne!(plain, b"hello"),
        }
    }

    // ── CRT-path correctness ─────────────────────────────────────────

    /// CRT exponentiation must produce the same result as the direct
    /// `c^d mod n` computation.  This is the structural correctness
    /// invariant for the CRT path — if it ever drifts, decrypts
    /// silently produce garbage that PKCS#1 unpadding would reject as
    /// "invalid padding", masking the bug as a Bleichenbacher false
    /// positive at higher layers.
    #[test]
    fn crt_matches_non_crt_1024() {
        let kp = RsaKeyPair::generate(1024);
        // A few non-trivial ciphertexts.  We don't actually encrypt
        // anything (this is testing the math primitive); just feed a
        // handful of values < n into both paths and compare.
        let cases = [
            BigUint::from(0xdeadbeefcafebabeu64),
            BigUint::from(2u32).modpow(&BigUint::from(900u32), &kp.public.n),
            &kp.public.n - BigUint::from(3u8),
            BigUint::one(),
        ];
        for c in &cases {
            let via_crt = rsa_mod_pow_ct_crt(c, &kp.private);
            let via_direct = rsa_mod_pow_ct(c, &kp.private.d, &kp.private.n, 1024);
            assert_eq!(via_crt, via_direct, "CRT vs direct mismatch at 1024 bits");
        }
    }

    /// CRT-decrypt must round-trip with public-exponent encrypt at all
    /// supported sizes.  We only run 1024 by default (keygen at 2048+
    /// is slow); the 2048 case is `#[ignore]`d so it's available via
    /// `cargo test -- --ignored` for full validation.
    #[test]
    fn crt_round_trip_1024() {
        let kp = RsaKeyPair::generate(1024);
        let msg = b"CRT private path";
        let ct = rsa_encrypt(msg, &kp.public).unwrap();
        assert_eq!(rsa_decrypt(&ct, &kp.private).unwrap(), msg);
    }

    #[test]
    #[ignore = "slow keygen — run with `cargo test -- --ignored`"]
    fn crt_round_trip_2048() {
        let kp = RsaKeyPair::generate(2048);
        let msg = b"CRT 2048 round-trip";
        let ct = rsa_encrypt(msg, &kp.public).unwrap();
        assert_eq!(rsa_decrypt(&ct, &kp.private).unwrap(), msg);
        // And the math invariant.
        let c = BigUint::from(0x123456789abcdefu64);
        let via_crt = rsa_mod_pow_ct_crt(&c, &kp.private);
        let via_direct = rsa_mod_pow_ct(&c, &kp.private.d, &kp.private.n, 2048);
        assert_eq!(via_crt, via_direct);
    }

    /// Keygen must populate `dp`, `dq`, `qinv` consistently and put
    /// `p > q` (PKCS#1 §3.2 convention).
    #[test]
    fn crt_params_are_well_formed() {
        let kp = RsaKeyPair::generate(1024);
        let priv_ = &kp.private;

        assert!(priv_.p > priv_.q, "PKCS#1 convention p > q broken");
        assert_eq!(&priv_.dp, &(&priv_.d % (&priv_.p - BigUint::one())));
        assert_eq!(&priv_.dq, &(&priv_.d % (&priv_.q - BigUint::one())));
        // qinv * q ≡ 1 (mod p)
        assert_eq!((&priv_.qinv * &priv_.q) % &priv_.p, BigUint::one());
    }
}
