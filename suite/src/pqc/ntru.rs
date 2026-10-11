//! **NTRU** — the foundational lattice-based public-key cryptosystem
//! (Hoffstein, Pipher, Silverman 1996).  Round-3 NIST PQC finalist.
//!
//! ## Mathematical setting
//!
//! Operations live in the **ring of truncated polynomials**:
//!
//! ```text
//! R = Z[x] / (x^N − 1)
//! ```
//!
//! with two auxiliary moduli `(p, q)`, `p` small (e.g. 3) and `q`
//! large (e.g. 2048), `gcd(p, q) = 1`.  The KEM operates by
//! exploiting the gap between `q`-scale arithmetic (where the
//! ciphertext lives) and `p`-scale recovery (where the message is
//! decoded).
//!
//! ## Key generation
//!
//! 1. Sample two "small" polynomials `f, g ∈ R` with coefficients
//!    in `{−1, 0, +1}`.
//! 2. Require `f` invertible **mod p** and **mod q**.
//! 3. Public key: `h = p · (f^{-1} mod q) · g  (mod q)`.
//! 4. Private key: `(f, f_p^{-1} mod p)`.
//!
//! ## Encryption (raw)
//!
//! Given message `m ∈ R` with coefficients in `{−1, 0, +1}`:
//!
//! ```text
//! r  ← R with small coefficients (random)
//! c  = r · h + m  (mod q)
//! ```
//!
//! ## Decryption
//!
//! ```text
//! a = f · c  (mod q),  lifted to centered representative in [−q/2, q/2]
//! m = (f_p^{-1} · a)   (mod p)
//! ```
//!
//! Correctness relies on `‖f · c‖_∞ < q/2` so that the
//! integer-lift `a` matches the true `f · c ∈ Z[x]`.
//!
//! ## Educational scope
//!
//! Parameters: `N = 11`, `p = 3`, `q = 32` (toy-scale for testing).
//! Real-world NTRU (`ntru-hps-2048-509`) uses `N = 509`, `p = 3`,
//! `q = 2048`.  Our implementation is structurally identical;
//! parameter scaling is just a constant change.
//!
//! KEM construction: Fujisaki-Okamoto-style hashing of `m` to derive
//! the shared secret.  We use SHA-256 for the KEM hash.

use crate::hash::sha256::sha256;
use rand::{rngs::OsRng, Rng};

/// NTRU ring degree.  Public.  We default to a toy value for
/// testing; production would use `N ∈ {509, 677, 821}`.
pub const N: usize = 5;
/// Small modulus (message space coefficients in `[−1, 0, 1]`).
pub const P: i32 = 3;
/// Large modulus (ciphertext coefficients).  Must be coprime to `P`.
///
/// For correct decryption we need `|f · c|_∞ < q/2`.  With weight-3
/// `f` and weight-1 `m, g, r`, worst-case `|p·g·r + f·m|_∞ ≤ 6`,
/// so `q = 13` (where `q/2 = 6.5`) provides a thin margin.  The
/// `f` weight (2 +1, 1 -1) gives `f(1) = 1 ≠ 0` mod p (necessary for
/// invertibility, since `(x-1)` divides `x^N − 1`).
pub const Q: i32 = 13;

/// A polynomial in `R = Z[x] / (x^N − 1)`.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct NtruPoly(pub [i32; N]);

impl NtruPoly {
    pub fn zero() -> Self {
        Self([0; N])
    }

    /// Reduce all coefficients into `[0, m)`.
    pub fn reduce_mod(&self, m: i32) -> Self {
        let mut out = [0; N];
        for i in 0..N {
            out[i] = ((self.0[i] % m) + m) % m;
        }
        Self(out)
    }

    /// Reduce coefficients into the centered range `[−m/2, m/2)`.
    pub fn center_lift(&self, m: i32) -> Self {
        let mut out = [0; N];
        for i in 0..N {
            let v = ((self.0[i] % m) + m) % m;
            out[i] = if v > m / 2 { v - m } else { v };
        }
        Self(out)
    }

    pub fn add(&self, other: &Self) -> Self {
        let mut out = [0; N];
        for i in 0..N {
            out[i] = self.0[i] + other.0[i];
        }
        Self(out)
    }

    pub fn sub(&self, other: &Self) -> Self {
        let mut out = [0; N];
        for i in 0..N {
            out[i] = self.0[i] - other.0[i];
        }
        Self(out)
    }

    /// Multiplication in `R = Z[x]/(x^N − 1)`.  After standard
    /// polynomial multiplication, indices wrap around (cyclic
    /// convolution).
    pub fn mul(&self, other: &Self) -> Self {
        let mut out = [0i64; N];
        for i in 0..N {
            for j in 0..N {
                out[(i + j) % N] += self.0[i] as i64 * other.0[j] as i64;
            }
        }
        let mut result = [0i32; N];
        for i in 0..N {
            result[i] = out[i] as i32;
        }
        Self(result)
    }

    pub fn scale(&self, s: i32) -> Self {
        let mut out = [0; N];
        for i in 0..N {
            out[i] = self.0[i] * s;
        }
        Self(out)
    }

    /// Sample a polynomial with `d_plus` coefficients = +1 and
    /// `d_minus` coefficients = −1, rest 0.  Standard NTRU
    /// "ternary" sampling.
    pub fn sample_ternary(d_plus: usize, d_minus: usize) -> Self {
        assert!(d_plus + d_minus <= N);
        let mut rng = OsRng;
        let mut out = [0i32; N];
        let mut placed_plus = 0;
        while placed_plus < d_plus {
            let i: usize = rng.gen_range(0..N);
            if out[i] == 0 {
                out[i] = 1;
                placed_plus += 1;
            }
        }
        let mut placed_minus = 0;
        while placed_minus < d_minus {
            let i: usize = rng.gen_range(0..N);
            if out[i] == 0 {
                out[i] = -1;
                placed_minus += 1;
            }
        }
        Self(out)
    }

    /// Hamming weight by sign (number of +1 plus number of -1).
    pub fn weight(&self) -> usize {
        self.0.iter().filter(|&&c| c != 0).count()
    }
}

// ── Inversion in R/p (and R/q): extended Euclidean over polynomial ring ──

/// Compute `f^{-1} mod (x^N − 1, m)` if it exists.  Uses the
/// extended Euclidean algorithm on polynomials in `(Z/mZ)[x]`.
///
/// Returns `None` if `f` is not invertible.
pub fn poly_inverse(f: &NtruPoly, m: i32) -> Option<NtruPoly> {
    // Brute force is feasible for all our toy parameters:
    // N = 5, m ∈ {3, 11}: at most 11^5 = 161,051 candidates.
    poly_inverse_brute(f, m)
}

fn poly_inverse_brute(f: &NtruPoly, m: i32) -> Option<NtruPoly> {
    let m_usize = m as usize;
    let total = (m_usize as u64).checked_pow(N as u32)?;
    if total > 200_000_000 {
        return None;
    }
    let one = {
        let mut o = NtruPoly::zero();
        o.0[0] = 1;
        o
    };
    for code in 0..total {
        let mut g = NtruPoly::zero();
        let mut c = code;
        for i in 0..N {
            g.0[i] = (c % m_usize as u64) as i32;
            c /= m_usize as u64;
        }
        let prod = f.mul(&g).reduce_mod(m);
        if prod == one {
            return Some(g);
        }
    }
    None
}

#[allow(dead_code)]
/// Extended-Euclidean inversion of `f` in `Z_m[x] / (x^N − 1)`.
/// Implements Almost-Inverse algorithm adapted from Silverman 1999.
/// **Currently unused**: brute force is sufficient for our toy
/// parameters.  Kept here for future extension to larger `N` / `q`.
fn poly_inverse_extended(f: &NtruPoly, m: i32) -> Option<NtruPoly> {
    // Convert to degree-N-1 polynomial representation as Vec<i32>.
    let mut a = vec![0i32; N + 1];
    for i in 0..N {
        a[i] = ((f.0[i] % m) + m) % m;
    }
    // a(x) and x^N − 1: a starts as f, b starts as x^N − 1.
    let mut b = vec![0i32; N + 1];
    b[0] = m - 1; // -1 mod m
    b[N] = 1;
    let mut u = vec![0i32; N + 1];
    u[0] = 1;
    let mut v = vec![0i32; N + 1];

    let mut deg_a = N;
    while deg_a > 0 && a[deg_a] == 0 {
        deg_a -= 1;
    }
    let mut deg_b = N;

    let mod_inv = |x: i32, m: i32| -> Option<i32> {
        let x = ((x % m) + m) % m;
        if x == 0 {
            return None;
        }
        // Brute force inverse for small m.
        (1..m).find(|&i| (x * i) % m == 1)
    };

    let mut k = 0i64;
    loop {
        if a[0] == 0 {
            // Multiply a, u by x^{-1}: shift down.
            a.rotate_left(1);
            if a.last() == Some(&0) {
                *a.last_mut().unwrap() = 0;
            } // no-op
              // u should multiply by x^{-1} = x^{N-1} mod (x^N − 1).
              // Equivalent to rotating u right.
            u.rotate_right(1);
            if u[0] != 0 {
                // rotate_right placed last element at position 0, ok.
            }
            k += 1;
            if k > (2 * N as i64 + 10) {
                return None; // safety bail
            }
            continue;
        }
        if deg_a == 0 {
            // a is a constant; if it's invertible mod m, done.
            let a0_inv = mod_inv(a[0], m)?;
            // result = u · a[0]^{-1} · x^{−k}  reduced mod (x^N − 1).
            let mut result = [0i32; N];
            for i in 0..N {
                result[i] = ((u[i] * a0_inv) % m + m) % m;
            }
            // Multiply by x^{-k mod N} = rotate right by (k mod N).
            let k_mod = ((k % N as i64) + N as i64) % N as i64;
            for _ in 0..k_mod {
                result.rotate_right(1);
            }
            let mut out = NtruPoly::zero();
            out.0[..N].copy_from_slice(&result[..N]);
            // Sanity check: verify f · out = 1.
            let one_check = f.mul(&out).reduce_mod(m);
            let mut one = NtruPoly::zero();
            one.0[0] = 1;
            if one_check == one {
                return Some(out);
            }
            return None;
        }
        if deg_a < deg_b {
            std::mem::swap(&mut a, &mut b);
            std::mem::swap(&mut u, &mut v);
            std::mem::swap(&mut deg_a, &mut deg_b);
        }
        // We need a[0] nonzero now; if it's zero we'd have returned above.
        let b0_inv = mod_inv(b[0], m)?;
        let coef = (a[0] * b0_inv) % m;
        for i in 0..=deg_b {
            a[i] = ((a[i] - coef * b[i]) % m + m * m) % m;
        }
        for i in 0..=N {
            u[i] = ((u[i] - coef * v[i]) % m + m * m) % m;
        }
        // Recompute deg_a.
        while deg_a > 0 && a[deg_a] == 0 {
            deg_a -= 1;
        }
        if a.iter().all(|&x| x == 0) {
            return None;
        }
    }
}

// ── NTRU KEM ────────────────────────────────────────────────────────

#[derive(Clone, Debug)]
pub struct NtruPublicKey {
    pub h: NtruPoly,
}

#[derive(Clone, Debug)]
pub struct NtruPrivateKey {
    pub f: NtruPoly,
    pub f_p_inv: NtruPoly,
    pub pk: NtruPublicKey,
}

pub struct NtruKeyPair {
    pub pk: NtruPublicKey,
    pub sk: NtruPrivateKey,
}

/// Generate an NTRU key pair.  Retries `f` sampling until invertible
/// mod both `p` and `q`.
pub fn ntru_keygen() -> NtruKeyPair {
    for _ in 0..500 {
        // For toy parameters N=5, p=3, q=13:
        // f has weight (2, 1) so f(1) = 1 ≠ 0 ⇒ avoids the
        // automatic (x − 1) factor of x^N − 1.
        // g has weight (1, 0) so g(1) = 1 ≠ 0 similarly.
        let f = NtruPoly::sample_ternary(2, 1);
        let g = NtruPoly::sample_ternary(1, 0);
        let f_p_inv = match poly_inverse(&f, P) {
            Some(x) => x,
            None => continue,
        };
        let f_q_inv = match poly_inverse(&f, Q) {
            Some(x) => x,
            None => continue,
        };
        // h = p · f_q_inv · g  (mod q)
        let h = f_q_inv.mul(&g).scale(P).reduce_mod(Q);
        let pk = NtruPublicKey { h };
        let sk = NtruPrivateKey {
            f,
            f_p_inv,
            pk: pk.clone(),
        };
        return NtruKeyPair { pk, sk };
    }
    panic!("NTRU keygen failed after 200 retries (extremely unlikely with valid parameters)");
}

/// **Raw NTRU encryption** of a ternary message `m` with random `r`.
pub fn ntru_encrypt_raw(m: &NtruPoly, r: &NtruPoly, pk: &NtruPublicKey) -> NtruPoly {
    let rh = r.mul(&pk.h);
    rh.add(m).reduce_mod(Q)
}

/// **Raw NTRU decryption** to recover the ternary message.
pub fn ntru_decrypt_raw(c: &NtruPoly, sk: &NtruPrivateKey) -> NtruPoly {
    let a = sk.f.mul(c).center_lift(Q);
    let m_unreduced = sk.f_p_inv.mul(&a);
    m_unreduced.center_lift(P)
}

/// **KEM Encapsulation** (educational FO-style):
/// 1. Sample random `m, r` ∈ ternary.
/// 2. Compute ciphertext `c = NTRU_Enc(m; r, pk)`.
/// 3. Shared secret `K = SHA-256(m ‖ r)`.
pub fn ntru_encapsulate(pk: &NtruPublicKey) -> (NtruPoly, [u8; 32]) {
    // Same toy weight constraints as in keygen.
    let m = NtruPoly::sample_ternary(1, 0);
    let r = NtruPoly::sample_ternary(1, 0);
    let c = ntru_encrypt_raw(&m, &r, pk);
    // Shared secret = H(m ‖ c) — symmetric with decap which can
    // only recover `m`, not `r`.  Including `c` provides binding
    // (tampered ciphertexts yield different shared secrets).
    let mut hash_input = Vec::with_capacity(2 * N * 4);
    for v in m.0.iter() {
        hash_input.extend_from_slice(&v.to_le_bytes());
    }
    for v in c.0.iter() {
        hash_input.extend_from_slice(&v.to_le_bytes());
    }
    let k = sha256(&hash_input);
    (c, k)
}

fn ciphertext_is_well_formed(c: &NtruPoly) -> bool {
    c.0.iter().all(|&coeff| (0..Q).contains(&coeff))
}

fn is_valid_encapsulated_message(m: &NtruPoly) -> bool {
    let plus = m.0.iter().filter(|&&coeff| coeff == 1).count();
    let minus = m.0.iter().filter(|&&coeff| coeff == -1).count();
    plus == 1 && minus == 0 && m.0.iter().all(|&coeff| matches!(coeff, -1..=1))
}

fn matches_valid_encapsulation(c: &NtruPoly, m: &NtruPoly, pk: &NtruPublicKey) -> bool {
    if !is_valid_encapsulated_message(m) {
        return false;
    }

    // Encapsulation currently samples `r` with exactly one `+1` term and no
    // `-1` terms, so we can cheaply re-encrypt across the tiny candidate set.
    for i in 0..N {
        let mut r = NtruPoly::zero();
        r.0[i] = 1;
        if ntru_encrypt_raw(m, &r, pk) == *c {
            return true;
        }
    }

    false
}

fn rejection_key(sk: &NtruPrivateKey, c: &NtruPoly) -> [u8; 32] {
    let mut hash_input = Vec::with_capacity(32 + 3 * N * 4);
    hash_input.extend_from_slice(b"NTRU-REJECT");
    for coeff in sk.f.0.iter() {
        hash_input.extend_from_slice(&coeff.to_le_bytes());
    }
    for coeff in sk.f_p_inv.0.iter() {
        hash_input.extend_from_slice(&coeff.to_le_bytes());
    }
    for coeff in c.0.iter() {
        hash_input.extend_from_slice(&coeff.to_le_bytes());
    }
    sha256(&hash_input)
}

/// **KEM Decapsulation**: recover `m`, then `r`-recovery (here
/// simplified: we hash just `m` for the educational version since
/// recovering `r` requires the FO re-encryption check).  For full
/// IND-CCA we'd:
/// 1. Decrypt to recover `m`.
/// 2. Re-derive `r` from `(c − m) · h^{-1}` (only possible if h is
///    invertible mod q — not always the case).
/// 3. Re-encrypt and verify match.
///
/// This educational version still rejects malformed ciphertexts and
/// impossible decryptions instead of directly hashing attacker-chosen
/// decapsulation outputs.
pub fn ntru_decapsulate(c: &NtruPoly, sk: &NtruPrivateKey) -> [u8; 32] {
    if !ciphertext_is_well_formed(c) {
        return rejection_key(sk, c);
    }

    let m = ntru_decrypt_raw(c, sk);
    if !matches_valid_encapsulation(c, &m, &sk.pk) {
        return rejection_key(sk, c);
    }

    let mut hash_input = Vec::with_capacity(N * 4 + N * 4);
    for v in m.0.iter() {
        hash_input.extend_from_slice(&v.to_le_bytes());
    }
    for v in c.0.iter() {
        hash_input.extend_from_slice(&v.to_le_bytes());
    }
    sha256(&hash_input)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Polynomial arithmetic: x · (x + 1) = x² + x  (in R = Z[x]/(x^N − 1))
    #[test]
    fn poly_mul_basic() {
        let mut x = NtruPoly::zero();
        x.0[1] = 1;
        let mut x_plus_1 = NtruPoly::zero();
        x_plus_1.0[0] = 1;
        x_plus_1.0[1] = 1;
        let prod = x.mul(&x_plus_1);
        let mut expected = NtruPoly::zero();
        expected.0[1] = 1;
        expected.0[2] = 1;
        assert_eq!(prod, expected);
    }

    /// Polynomial inverse mod p=3: f = 1 + x (typically invertible).
    #[test]
    fn poly_inverse_mod_p_works() {
        // Try a few f and find one invertible mod p.
        for trial in 0..20 {
            let f = NtruPoly::sample_ternary(2, 1);
            if let Some(f_inv) = poly_inverse(&f, P) {
                let prod = f.mul(&f_inv).reduce_mod(P);
                let mut one = NtruPoly::zero();
                one.0[0] = 1;
                assert_eq!(prod, one, "trial {}", trial);
                return;
            }
        }
        panic!("Could not find invertible f in 20 trials");
    }

    /// Ternary sampling produces the requested weights.
    #[test]
    fn ternary_sample_correct_weights() {
        let p = NtruPoly::sample_ternary(2, 1);
        let plus_count = p.0.iter().filter(|&&c| c == 1).count();
        let minus_count = p.0.iter().filter(|&&c| c == -1).count();
        assert_eq!(plus_count, 2);
        assert_eq!(minus_count, 1);
    }

    /// **Raw encryption → decryption** recovers the message.
    /// Uses the same minimal weights as `ntru_encapsulate` to
    /// ensure the noise bound holds.
    #[test]
    fn raw_encrypt_decrypt_roundtrip() {
        let kp = ntru_keygen();
        let m = NtruPoly::sample_ternary(1, 0);
        let r = NtruPoly::sample_ternary(1, 0);
        let c = ntru_encrypt_raw(&m, &r, &kp.pk);
        let m_recovered = ntru_decrypt_raw(&c, &kp.sk);
        assert_eq!(m, m_recovered);
    }

    /// **KEM**: encapsulate → decapsulate → same shared secret.
    #[test]
    fn kem_shared_secret_matches() {
        let kp = ntru_keygen();
        let (c, k_enc) = ntru_encapsulate(&kp.pk);
        let k_dec = ntru_decapsulate(&c, &kp.sk);
        assert_eq!(k_enc, k_dec);
    }

    #[test]
    fn ntru_decapsulate_rejects_zero_ciphertext() {
        let kp = ntru_keygen();
        let zero = NtruPoly::zero();

        assert_eq!(
            ntru_decapsulate(&zero, &kp.sk),
            rejection_key(&kp.sk, &zero)
        );
    }

    #[test]
    fn ntru_decapsulate_rejects_out_of_range_coefficients() {
        let kp = ntru_keygen();
        let mut malformed = NtruPoly::zero();
        malformed.0[0] = Q;

        assert_eq!(
            ntru_decapsulate(&malformed, &kp.sk),
            rejection_key(&kp.sk, &malformed)
        );
    }
}
