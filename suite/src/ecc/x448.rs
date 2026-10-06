//! X448 — Diffie-Hellman key agreement on Curve448 (RFC 7748).
//!
//! Hamburg 2015's "Goldilocks" curve in Montgomery form:
//! `y² = x³ + A x² + x` with `A = 156326` over
//! `F_{2⁴⁴⁸ − 2²²⁴ − 1}`.  Aimed at the 224-bit security
//! level — the higher-security companion to X25519.  Used in
//! TLS 1.3 (RFC 8446), libsodium, OpenSSH (since 8.3), and the
//! CFRG Hybrid Public Key Encryption (HPKE, RFC 9180) suites.
//!
//! As with X25519, the Montgomery ladder operates on x-coordinates
//! only and is constant-time-by-construction at the algorithmic
//! level (BigUint limb-arithmetic is *not* constant-time; see the
//! `curve25519` module note).
//!
//! # Wire format
//!
//! - **Public key**: 56 bytes, little-endian x-coordinate
//! - **Private key (scalar)**: 56 bytes, "clamped":
//!   - `byte[0] &= 252` (clear bottom 2 bits)
//!   - `byte[55] |= 128` (set top bit, i.e. bit 447)
//! - **Shared secret**: 56 bytes, little-endian x-coordinate
//!
//! # Test vectors
//!
//! Verified against RFC 7748 §5.2 vectors.

use num_bigint::BigUint;
use num_traits::One;

/// Curve448 field prime: `p = 2⁴⁴⁸ − 2²²⁴ − 1`.
fn p() -> BigUint {
    (BigUint::one() << 448) - (BigUint::one() << 224) - BigUint::one()
}

/// `A24 = (A - 2) / 4 = (156326 - 2) / 4 = 39081` (RFC 7748 §5).
fn a24() -> BigUint {
    BigUint::from(39081u32)
}

fn fe_reduce(x: &BigUint) -> BigUint {
    let pp = p();
    if x < &pp {
        x.clone()
    } else {
        x % &pp
    }
}

fn fe_add(a: &BigUint, b: &BigUint) -> BigUint {
    fe_reduce(&(a + b))
}

fn fe_sub(a: &BigUint, b: &BigUint) -> BigUint {
    let pp = p();
    if a >= b {
        (a - b) % &pp
    } else {
        &pp - ((b - a) % &pp)
    }
}

fn fe_mul(a: &BigUint, b: &BigUint) -> BigUint {
    fe_reduce(&(a * b))
}

fn fe_inv(a: &BigUint) -> BigUint {
    let pp = p();
    let exp = &pp - BigUint::from(2u32);
    a.modpow(&exp, &pp)
}

fn fe_from_bytes(bytes: &[u8; 56]) -> BigUint {
    fe_reduce(&BigUint::from_bytes_le(bytes))
}

fn fe_to_bytes(a: &BigUint) -> [u8; 56] {
    let mut out = [0u8; 56];
    let bytes = a.to_bytes_le();
    let n = bytes.len().min(56);
    out[..n].copy_from_slice(&bytes[..n]);
    out
}

/// "Clamp" a 56-byte X448 private scalar per RFC 7748 §5:
/// clear the bottom 2 bits of byte 0 and set the top bit of byte 55.
pub fn clamp(scalar: &mut [u8; 56]) {
    scalar[0] &= 252;
    scalar[55] |= 128;
}

/// X448 scalar multiplication: `[k] · u`.  Both inputs are
/// 56-byte little-endian; output is 56 bytes.
pub fn x448(scalar: &[u8; 56], u_coord: &[u8; 56]) -> [u8; 56] {
    let mut k = *scalar;
    clamp(&mut k);
    let scalar_bn = BigUint::from_bytes_le(&k);
    // X448 has no top-bit mask on the u-coordinate (unlike X25519);
    // values are simply reduced mod p.
    let u = fe_from_bytes(u_coord);
    let result = ladder(&scalar_bn, &u);
    fe_to_bytes(&result)
}

/// Generate an X448 keypair from a 56-byte seed: returns
/// `(clamped_secret, public_key)` where the public key is
/// `[seed] · 5` (base u-coordinate is 5 per RFC 7748).
pub fn x448_keygen(seed: &[u8; 56]) -> ([u8; 56], [u8; 56]) {
    let mut sk = *seed;
    clamp(&mut sk);
    let mut base = [0u8; 56];
    base[0] = 5;
    let pk = x448(&sk, &base);
    (sk, pk)
}

/// Montgomery ladder.  RFC 7748 §5 pseudocode, with `bits = 448`
/// (iterate from bit 447 down to 0).
fn ladder(scalar: &BigUint, u: &BigUint) -> BigUint {
    let x1 = u.clone();
    let mut x2 = BigUint::from(1u32);
    let mut z2 = BigUint::from(0u32);
    let mut x3 = u.clone();
    let mut z3 = BigUint::from(1u32);
    let mut swap = 0u32;

    let a24_v = a24();

    for t in (0..448).rev() {
        let k_t = if scalar.bit(t) { 1u32 } else { 0u32 };
        let s = swap ^ k_t;
        if s == 1 {
            std::mem::swap(&mut x2, &mut x3);
            std::mem::swap(&mut z2, &mut z3);
        }
        swap = k_t;

        let a = fe_add(&x2, &z2);
        let aa = fe_mul(&a, &a);
        let b = fe_sub(&x2, &z2);
        let bb = fe_mul(&b, &b);
        let e = fe_sub(&aa, &bb);
        let c = fe_add(&x3, &z3);
        let d = fe_sub(&x3, &z3);
        let da = fe_mul(&d, &a);
        let cb = fe_mul(&c, &b);

        let da_plus_cb = fe_add(&da, &cb);
        x3 = fe_mul(&da_plus_cb, &da_plus_cb);
        let da_minus_cb = fe_sub(&da, &cb);
        let dm_sq = fe_mul(&da_minus_cb, &da_minus_cb);
        z3 = fe_mul(&x1, &dm_sq);

        x2 = fe_mul(&aa, &bb);
        let a24e = fe_mul(&a24_v, &e);
        let aa_plus_a24e = fe_add(&aa, &a24e);
        z2 = fe_mul(&e, &aa_plus_a24e);
    }
    if swap == 1 {
        std::mem::swap(&mut x2, &mut x3);
        std::mem::swap(&mut z2, &mut z3);
    }
    let z2_inv = fe_inv(&z2);
    fe_mul(&x2, &z2_inv)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn hex_decode(s: &str) -> Vec<u8> {
        let s: String = s.chars().filter(|c| !c.is_whitespace()).collect();
        (0..s.len())
            .step_by(2)
            .map(|i| u8::from_str_radix(&s[i..i + 2], 16).unwrap())
            .collect()
    }

    fn hex56(s: &str) -> [u8; 56] {
        let v = hex_decode(s);
        let mut out = [0u8; 56];
        out.copy_from_slice(&v);
        out
    }

    fn hex(bytes: &[u8]) -> String {
        bytes.iter().map(|b| format!("{:02x}", b)).collect()
    }

    /// **RFC 7748 §5.2 X448 vector**.
    #[test]
    fn rfc7748_x448_vector() {
        let scalar = hex56(
            "3d262fddf9ec8e88495266fea19a34d28882acef045104d0d1aae121\
             700a779c984c24f8cdd78fbff44943eba368f54b29259a4f1c600ad3",
        );
        let u = hex56(
            "06fce640fa3487bfda5f6cf2d5263f8aad88334cbd07437f020f08f9\
             814dc031ddbdc38c19c6da2583fa5429db94ada18aa7a7fb4ef8a086",
        );
        let expected = "ce3e4ff95a60dc6697da1db1d85e6afbdf79b50a2412d7546d5f239f\
                        e14fbaadeb445fc66a01b0779d98223961111e21766282f73dd96b6f";
        let result = x448(&scalar, &u);
        assert_eq!(hex(&result), expected, "RFC 7748 X448 vector mismatch");
    }

    /// X448 ECDH round-trip.
    #[test]
    fn x448_ecdh_roundtrip() {
        let a_seed = [0x01u8; 56];
        let b_seed = [0x02u8; 56];
        let (a_sk, a_pk) = x448_keygen(&a_seed);
        let (b_sk, b_pk) = x448_keygen(&b_seed);
        let s_ab = x448(&a_sk, &b_pk);
        let s_ba = x448(&b_sk, &a_pk);
        assert_eq!(s_ab, s_ba, "X448 ECDH shared-secret asymmetry");
    }

    /// Clamping zeros the right bits.
    #[test]
    fn clamp_zeros_correct_bits() {
        let mut s = [0xFFu8; 56];
        clamp(&mut s);
        assert_eq!(s[0] & 0x03, 0, "low 2 bits not cleared");
        assert_eq!(s[55] & 0x80, 0x80, "top bit not set");
    }
}
