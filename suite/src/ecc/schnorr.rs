//! BIP-340 Schnorr signatures over secp256k1.
//!
//! Bitcoin Soft Fork BIP-340 (Wuille, Nick, Ruffing 2020),
//! activated November 2021 as part of Taproot.  Replaces ECDSA
//! for new-style outputs with a cleaner, faster, batch-verifiable
//! signing scheme.  Three big wins over ECDSA:
//!
//! 1. **Linearity**: `(d_1 + d_2)·G = D_1 + D_2`, enabling
//!    multi-signature aggregation (MuSig2, FROST).
//! 2. **Provable security** under the discrete-log assumption
//!    (ROM model), unlike ECDSA which has only conjectural
//!    security.
//! 3. **No per-signature inversion** (cheaper signing) and
//!    **batch verification** (cheaper verification at scale).
//!
//! # Wire format
//!
//! - **Public key**: 32 bytes, x-only encoding.  Y-coordinate
//!   forced even (negate `d` during keygen if `Y` would be odd).
//! - **Signature**: 64 bytes = `R.x ‖ s`.  R-point's Y-coordinate
//!   forced even by negating `k` if needed.
//! - **Message**: arbitrary byte string; Bitcoin uses a 32-byte
//!   sighash but BIP-340 specifies the scheme generically over
//!   any-length messages.
//!
//! # Tagged-hash construction
//!
//! BIP-340 uses domain-separated SHA-256:
//! ```text
//! tagged_hash(tag, msg) = SHA-256(SHA-256(tag) ‖ SHA-256(tag) ‖ msg)
//! ```
//! with three tags: `"BIP0340/aux"`, `"BIP0340/nonce"`,
//! `"BIP0340/challenge"`.
//!
//! # Test vectors
//!
//! Verified against the official BIP-340 vectors (from the Bitcoin
//! Core test suite, also in the BIP itself).  Several worked
//! examples in the test module below.

use crate::ecc::ct::scalar_mul_secret;
use crate::ecc::curve::CurveParams;
use crate::ecc::keys::EccKeyPair;
use crate::ecc::point::Point;
use crate::hash::sha256::sha256;
use crate::utils::encoding::bigint_to_bytes_be;
use num_bigint::BigUint;
use num_traits::Zero;

/// Compute `tagged_hash(tag, msg) = SHA256(SHA256(tag) ‖ SHA256(tag) ‖ msg)`.
pub fn tagged_hash(tag: &str, msg: &[u8]) -> [u8; 32] {
    let tag_hash = sha256(tag.as_bytes());
    let mut input = Vec::with_capacity(64 + msg.len());
    input.extend_from_slice(&tag_hash);
    input.extend_from_slice(&tag_hash);
    input.extend_from_slice(msg);
    sha256(&input)
}

/// Encode a `BigUint` as a 32-byte big-endian array, left-padding
/// with zeros if shorter.
fn bytes32(x: &BigUint) -> [u8; 32] {
    let v = bigint_to_bytes_be(x, 32);
    let mut out = [0u8; 32];
    out.copy_from_slice(&v);
    out
}

/// Y-coordinate parity for an affine point.  `Some(true)` if odd,
/// `Some(false)` if even, `None` if identity.
fn y_is_odd(point: &Point) -> Option<bool> {
    match point {
        Point::Affine { y, .. } => Some(y.value.bit(0)),
        Point::Infinity => None,
    }
}

/// Returns `(x, y)` of a finite point as `BigUint` references.
fn xy(point: &Point) -> Option<(&BigUint, &BigUint)> {
    match point {
        Point::Affine { x, y } => Some((&x.value, &y.value)),
        Point::Infinity => None,
    }
}

/// Negate a scalar mod `n`.
fn neg_mod(x: &BigUint, n: &BigUint) -> BigUint {
    if x.is_zero() {
        BigUint::zero()
    } else {
        n - (x % n)
    }
}

// ── Keygen ──────────────────────────────────────────────────────────

/// Derive the BIP-340 x-only public key from a 32-byte private key.
/// Returns `(public_key_x_only, normalized_d)` where `normalized_d`
/// is `d` or `n - d` depending on which one yields an even-Y public
/// point.  The 32-byte x-only encoding is what BIP-340 wire format
/// specifies for public keys.
pub fn xonly_pubkey(d: &BigUint, curve: &CurveParams) -> Option<([u8; 32], BigUint)> {
    if curve.name != "secp256k1" {
        return None;
    }
    if d.is_zero() || d >= &curve.n {
        return None;
    }
    let g = curve.generator();
    let p = scalar_mul_secret(&g, d, curve);
    let (x, _) = xy(&p)?;
    let normalized_d = match y_is_odd(&p)? {
        true => neg_mod(d, &curve.n),
        false => d.clone(),
    };
    Some((bytes32(x), normalized_d))
}

// ── Sign / Verify ──────────────────────────────────────────────────

/// Sign `msg` under private key `d` with auxiliary randomness
/// `aux_rand` (use 32 zero bytes for deterministic signatures).
/// Returns the 64-byte signature `R.x ‖ s`.
pub fn schnorr_sign(
    msg: &[u8],
    d: &BigUint,
    aux_rand: &[u8; 32],
    curve: &CurveParams,
) -> Option<[u8; 64]> {
    if curve.name != "secp256k1" {
        return None;
    }
    let n = &curve.n;
    if d.is_zero() || d >= n {
        return None;
    }

    // 1. Normalise d so that the public point has even Y.
    let g = curve.generator();
    let p_pub = scalar_mul_secret(&g, d, curve);
    let (px, _) = xy(&p_pub)?;
    let d_norm = match y_is_odd(&p_pub)? {
        true => neg_mod(d, n),
        false => d.clone(),
    };
    let p_x = bytes32(px);

    // 2. t = bytes(d_norm) XOR tagged_hash("BIP0340/aux", aux_rand).
    let aux_hash = tagged_hash("BIP0340/aux", aux_rand);
    let d_bytes = bytes32(&d_norm);
    let mut t = [0u8; 32];
    for i in 0..32 {
        t[i] = d_bytes[i] ^ aux_hash[i];
    }

    // 3. rand = tagged_hash("BIP0340/nonce", t ‖ P.x ‖ msg).
    let mut nonce_input = Vec::with_capacity(64 + msg.len());
    nonce_input.extend_from_slice(&t);
    nonce_input.extend_from_slice(&p_x);
    nonce_input.extend_from_slice(msg);
    let rand = tagged_hash("BIP0340/nonce", &nonce_input);

    // 4. k0 = int(rand) mod n.  Fail if zero (probability 2^-256).
    let k0 = BigUint::from_bytes_be(&rand) % n;
    if k0.is_zero() {
        return None;
    }

    // 5. R = k0 · G.  Negate k0 if R.y is odd.
    let r_pt = scalar_mul_secret(&g, &k0, curve);
    let (rx, _) = xy(&r_pt)?;
    let k = match y_is_odd(&r_pt)? {
        true => neg_mod(&k0, n),
        false => k0,
    };
    let r_x = bytes32(rx);

    // 6. e = int(tagged_hash("BIP0340/challenge", R.x ‖ P.x ‖ msg)) mod n.
    let mut chal_input = Vec::with_capacity(64 + msg.len());
    chal_input.extend_from_slice(&r_x);
    chal_input.extend_from_slice(&p_x);
    chal_input.extend_from_slice(msg);
    let e = BigUint::from_bytes_be(&tagged_hash("BIP0340/challenge", &chal_input)) % n;

    // 7. s = (k + e · d_norm) mod n.
    let s = (&k + (&e * &d_norm)) % n;

    // 8. Concatenate R.x ‖ s.
    let mut sig = [0u8; 64];
    sig[..32].copy_from_slice(&r_x);
    sig[32..].copy_from_slice(&bytes32(&s));
    Some(sig)
}

/// Verify a 64-byte BIP-340 signature against a 32-byte x-only
/// public key.  Returns `true` iff the signature is valid.
pub fn schnorr_verify(
    msg: &[u8],
    pubkey_xonly: &[u8; 32],
    sig: &[u8; 64],
    curve: &CurveParams,
) -> bool {
    if curve.name != "secp256k1" {
        return false;
    }
    let n = &curve.n;
    let p_field = &curve.p;

    // 1. Parse R.x = sig[0..32], s = sig[32..64].
    let r_x = BigUint::from_bytes_be(&sig[..32]);
    let s = BigUint::from_bytes_be(&sig[32..]);
    if r_x >= *p_field || s >= *n {
        return false;
    }

    // 2. Parse public key as x-only point P with even Y.
    let p_x = BigUint::from_bytes_be(pubkey_xonly);
    if p_x >= *p_field {
        return false;
    }
    let p_pub = match lift_x(&p_x, curve) {
        Some(p) => p,
        None => return false,
    };

    // 3. e = int(tagged_hash("BIP0340/challenge", R.x ‖ P.x ‖ msg)) mod n.
    let mut chal_input = Vec::with_capacity(64 + msg.len());
    chal_input.extend_from_slice(&sig[..32]);
    chal_input.extend_from_slice(pubkey_xonly);
    chal_input.extend_from_slice(msg);
    let e = BigUint::from_bytes_be(&tagged_hash("BIP0340/challenge", &chal_input)) % n;

    // 4. R' = s · G − e · P.  Verify R'.y is even and R'.x == r_x.
    let g = curve.generator();
    let s_g = scalar_mul_secret(&g, &s, curve);
    let neg_e = neg_mod(&e, n);
    let neg_e_p = scalar_mul_secret(&p_pub, &neg_e, curve);
    let a_fe = curve.a_fe();
    let r_prime = s_g.add(&neg_e_p, &a_fe);

    match (xy(&r_prime), y_is_odd(&r_prime)) {
        (Some((rx_prime, _)), Some(false)) => rx_prime == &r_x,
        _ => false,
    }
}

/// "Lift x" — find the unique even-Y point on `curve` with
/// x-coordinate `x_val`.  Returns `None` if no such point exists
/// (i.e., `x³ + ax + b` is not a quadratic residue mod p).
fn lift_x(x_val: &BigUint, curve: &CurveParams) -> Option<Point> {
    let p_field = &curve.p;
    // Compute y² = x³ + ax + b mod p.
    let x_cubed = (x_val.modpow(&BigUint::from(3u32), p_field)) % p_field;
    let ax = (&curve.a * x_val) % p_field;
    let rhs = (x_cubed + ax + &curve.b) % p_field;
    // Square root: for secp256k1, p ≡ 3 (mod 4), so y = rhs^((p+1)/4) mod p.
    // Verify p ≡ 3 (mod 4).
    if p_field.bit(0) && p_field.bit(1) {
        // p ≡ 3 (mod 4) ⇔ p mod 4 == 3 ⇔ low two bits are 11.
        let exp = (p_field + 1u32) >> 2;
        let y = rhs.modpow(&exp, p_field);
        if (&y * &y) % p_field != rhs {
            return None;
        }
        // Force even Y.
        let y_even = if y.bit(0) { p_field - &y } else { y };
        let x_fe = curve.fe(x_val.clone());
        let y_fe = curve.fe(y_even);
        Some(Point::Affine { x: x_fe, y: y_fe })
    } else {
        // Tonelli-Shanks for p ≢ 3 (mod 4) — not needed for secp256k1.
        None
    }
}

/// Convenience: derive (32-byte x-only pubkey, normalised privkey)
/// from a `EccKeyPair`-style private scalar.
pub fn schnorr_keypair(d: &BigUint, curve: &CurveParams) -> Option<([u8; 32], BigUint)> {
    xonly_pubkey(d, curve)
}

/// Sanity wrapper: build a key pair via the standard `EccKeyPair`
/// machinery, then BIP-340-normalise.
#[allow(dead_code)]
fn _link_keypair() {
    let _ = EccKeyPair::generate;
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ecc::curve::CurveParams;
    use num_bigint::BigUint;

    fn hex_decode(s: &str) -> Vec<u8> {
        let s: String = s.chars().filter(|c| !c.is_whitespace()).collect();
        (0..s.len())
            .step_by(2)
            .map(|i| u8::from_str_radix(&s[i..i + 2], 16).unwrap())
            .collect()
    }

    fn hex32(s: &str) -> [u8; 32] {
        let v = hex_decode(s);
        let mut out = [0u8; 32];
        out.copy_from_slice(&v);
        out
    }

    fn hex64(s: &str) -> [u8; 64] {
        let v = hex_decode(s);
        let mut out = [0u8; 64];
        out.copy_from_slice(&v);
        out
    }

    /// Tagged-hash sanity: same inputs → same output, different
    /// tags → different output.
    #[test]
    fn tagged_hash_domain_separation() {
        let h1 = tagged_hash("BIP0340/nonce", b"abc");
        let h2 = tagged_hash("BIP0340/challenge", b"abc");
        let h3 = tagged_hash("BIP0340/nonce", b"abc");
        assert_ne!(h1, h2);
        assert_eq!(h1, h3);
    }

    /// **BIP-340 official test vector index 0** (from
    /// the BIP itself).  Deterministic signature with all-zero
    /// aux_rand on private key 0x000...0003.
    #[test]
    fn bip340_test_vector_0() {
        let curve = CurveParams::secp256k1();
        let d = BigUint::from_bytes_be(&hex_decode(
            "0000000000000000000000000000000000000000000000000000000000000003",
        ));
        let aux = hex32("0000000000000000000000000000000000000000000000000000000000000000");
        let msg = hex_decode("0000000000000000000000000000000000000000000000000000000000000000");
        let expected_pk = hex32("F9308A019258C31049344F85F89D5229B531C845836F99B08601F113BCE036F9");
        let expected_sig = hex64(
            "E907831F80848D1069A5371B402410364BDF1C5F8307B0084C55F1CE2DCA8215\
             25F66A4A85EA8B71E482A74F382D2CE5EBEEE8FDB2172F477DF4900D310536C0",
        );

        let (pk, _) = xonly_pubkey(&d, &curve).unwrap();
        assert_eq!(pk, expected_pk, "public key mismatch");

        let sig = schnorr_sign(&msg, &d, &aux, &curve).unwrap();
        assert_eq!(sig, expected_sig, "signature mismatch");

        assert!(schnorr_verify(&msg, &pk, &sig, &curve), "verify failed");
    }

    /// **BIP-340 official test vector index 1** — non-zero aux_rand,
    /// non-zero msg.
    #[test]
    fn bip340_test_vector_1() {
        let curve = CurveParams::secp256k1();
        let d = BigUint::from_bytes_be(&hex_decode(
            "B7E151628AED2A6ABF7158809CF4F3C762E7160F38B4DA56A784D9045190CFEF",
        ));
        let aux = hex32("0000000000000000000000000000000000000000000000000000000000000001");
        let msg = hex_decode("243F6A8885A308D313198A2E03707344A4093822299F31D0082EFA98EC4E6C89");
        let expected_pk = hex32("DFF1D77F2A671C5F36183726DB2341BE58FEAE1DA2DECED843240F7B502BA659");
        let expected_sig = hex64(
            "6896BD60EEAE296DB48A229FF71DFE071BDE413E6D43F917DC8DCF8C78DE3341\
             8906D11AC976ABCCB20B091292BFF4EA897EFCB639EA871CFA95F6DE339E4B0A",
        );

        let (pk, _) = xonly_pubkey(&d, &curve).unwrap();
        assert_eq!(pk, expected_pk, "public key mismatch");

        let sig = schnorr_sign(&msg, &d, &aux, &curve).unwrap();
        assert_eq!(sig, expected_sig, "signature mismatch");

        assert!(schnorr_verify(&msg, &pk, &sig, &curve), "verify failed");
    }

    /// Round-trip: random private key + arbitrary message,
    /// sign-then-verify.
    #[test]
    fn schnorr_roundtrip() {
        let curve = CurveParams::secp256k1();
        let d = BigUint::from(123_456_789u64);
        let aux = [0xA5u8; 32];
        let msg = b"hello, taproot world!";
        let (pk, _) = xonly_pubkey(&d, &curve).unwrap();
        let sig = schnorr_sign(msg, &d, &aux, &curve).unwrap();
        assert!(schnorr_verify(msg, &pk, &sig, &curve));
    }

    /// Tampered signature must fail verification.
    #[test]
    fn schnorr_rejects_tampered() {
        let curve = CurveParams::secp256k1();
        let d = BigUint::from(42u32);
        let aux = [0u8; 32];
        let msg = b"genuine message";
        let (pk, _) = xonly_pubkey(&d, &curve).unwrap();
        let mut sig = schnorr_sign(msg, &d, &aux, &curve).unwrap();
        // Flip a bit in s.
        sig[63] ^= 0x01;
        assert!(!schnorr_verify(msg, &pk, &sig, &curve));
    }

    /// Different message must not verify under the same signature.
    #[test]
    fn schnorr_rejects_wrong_message() {
        let curve = CurveParams::secp256k1();
        let d = BigUint::from(7u32);
        let aux = [0u8; 32];
        let (pk, _) = xonly_pubkey(&d, &curve).unwrap();
        let sig = schnorr_sign(b"original", &d, &aux, &curve).unwrap();
        assert!(!schnorr_verify(b"different", &pk, &sig, &curve));
    }

    #[test]
    fn bip340_rejects_non_secp256k1_curve() {
        let curve = CurveParams::p256();
        let d = BigUint::from(3u32);
        let aux = [0u8; 32];
        let pk = [0u8; 32];
        let sig = [0u8; 64];

        assert!(xonly_pubkey(&d, &curve).is_none());
        assert!(schnorr_sign(b"msg", &d, &aux, &curve).is_none());
        assert!(!schnorr_verify(b"msg", &pk, &sig, &curve));
    }
}
