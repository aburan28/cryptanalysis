//! **SM2** — Chinese ECC public-key cryptography (GB/T 32918).
//!
//! SM2 is a suite of public-key algorithms defined by the Chinese
//! standardisation body over a specific 256-bit prime-field elliptic
//! curve (see [`CurveParams::sm2`]).  It is the Chinese analogue of the
//! ECDSA / ECIES / ECDH family and is mandatory for Chinese commercial
//! cryptographic products.
//!
//! Three sub-algorithms are standardised:
//!
//! | Document        | Algorithm                            | Status here    |
//! |-----------------|--------------------------------------|----------------|
//! | GB/T 32918.2    | Digital signature                    | ✓ implemented  |
//! | GB/T 32918.3    | Key agreement (Diffie–Hellman style) | not implemented|
//! | GB/T 32918.4    | Public-key encryption                | ✓ implemented  |
//!
//! ## Signature algorithm (GB/T 32918.2)
//!
//! **Signer's identifier ZA**: a 256-bit binding of the signer's
//! identity to the curve.  Computed as
//! `ZA = SM3(ENTL || ID || a || b || Gx || Gy || PAx || PAy)` where
//! `ENTL` is the 16-bit big-endian bit-length of `ID`.  The default
//! ID per the standard is the 16-byte ASCII string `"1234567812345678"`.
//!
//! **Sign**:
//! 1. `e = SM3(ZA || M)` as a 256-bit integer.
//! 2. Choose random `k ∈ [1, n-1]`.
//! 3. `(x₁, _) = k·G`.
//! 4. `r = (e + x₁) mod n`.  Restart if `r = 0` or `r + k = n`.
//! 5. `s = (1 + d)^(-1) · (k − r·d) mod n`.  Restart if `s = 0`.
//! 6. Output `(r, s)`.
//!
//! **Verify**:
//! 1. Reject if `r, s ∉ [1, n-1]`.
//! 2. `e = SM3(ZA || M)`.
//! 3. `t = (r + s) mod n`; reject if `t = 0`.
//! 4. `(x₁, _) = s·G + t·PA`.
//! 5. Accept iff `(e + x₁) mod n == r`.
//!
//! ## Encryption algorithm (GB/T 32918.4)
//!
//! 1. Choose random `k ∈ [1, n-1]`.
//! 2. `C₁ = k·G` (the ephemeral public point, serialised SEC1-uncompressed).
//! 3. `(x₂, y₂) = k·PB`, where `PB` is the recipient's public key.
//! 4. `t = KDF(x₂ || y₂, |M|)`; reject and restart if `t = 0…0`.
//! 5. `C₂ = M ⊕ t` (the encrypted message, same length as `M`).
//! 6. `C₃ = SM3(x₂ || M || y₂)` (integrity tag).
//! 7. Output the concatenation `C₁ || C₃ || C₂` (the "C1C3C2" form
//!    standardised in GB/T 32918.4-2016; the older "C1C2C3" form is
//!    deprecated).
//!
//! The KDF is the iterated SM3 construction from GB/T 32918.4 §5.4.3:
//! `KDF(Z, klen) = SM3(Z || 00000001) || SM3(Z || 00000002) || …`
//! truncated to `klen` bits.

use super::curve::CurveParams;
use super::point::Point;
use crate::hash::sm3::sm3;
use crate::utils::{mod_inverse, random::random_scalar};
use num_bigint::BigUint;
use num_traits::{One, Zero};

/// The standard SM2 user identifier per GB/T 32918.2 (the ASCII bytes
/// of `"1234567812345678"`).  Implementations are free to substitute a
/// different identifier; both signer and verifier must agree on it.
pub const DEFAULT_ID: &[u8] = b"1234567812345678";

/// Encode a non-negative integer as a fixed-width big-endian byte
/// string.  Used to serialise field elements / scalars into the
/// `ZA` and signature byte streams.
fn bytes_be(x: &BigUint, width: usize) -> Vec<u8> {
    crate::utils::encoding::bigint_to_bytes_be_checked(x, width)
        .expect("SM2 field element must fit fixed width")
}

/// Compute `ZA = SM3(ENTL || ID || a || b || Gx || Gy || PAx || PAy)`.
///
/// This is the per-user identity binding that SM2 signatures hash
/// alongside the message.  It is parameterised on the public key `PA`
/// and the user identifier `id` (default [`DEFAULT_ID`]).
pub fn za(id: &[u8], pa: &Point, curve: &CurveParams) -> [u8; 32] {
    try_za(id, pa, curve).expect("ZA: public key must be finite and on the selected curve")
}

fn try_za(id: &[u8], pa: &Point, curve: &CurveParams) -> Option<[u8; 32]> {
    if !curve.is_valid_public_point(pa) {
        return None;
    }
    let mut buf = Vec::with_capacity(2 + id.len() + 32 * 6);
    let entl = (id.len() as u16) * 8; // bit-length of ID, 16-bit BE
    buf.push((entl >> 8) as u8);
    buf.push((entl & 0xff) as u8);
    buf.extend_from_slice(id);
    buf.extend_from_slice(&bytes_be(&curve.a, 32));
    buf.extend_from_slice(&bytes_be(&curve.b, 32));
    buf.extend_from_slice(&bytes_be(&curve.gx, 32));
    buf.extend_from_slice(&bytes_be(&curve.gy, 32));
    match pa {
        Point::Affine { x, y } => {
            buf.extend_from_slice(&bytes_be(&x.value, 32));
            buf.extend_from_slice(&bytes_be(&y.value, 32));
        }
        Point::Infinity => return None,
    }
    Some(sm3(&buf))
}

/// An SM2 signature `(r, s)`.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Sm2Signature {
    pub r: BigUint,
    pub s: BigUint,
}

/// Compute the digest `e = SM3(ZA || M)` reduced mod n.
fn message_digest(za: &[u8; 32], msg: &[u8], n: &BigUint) -> BigUint {
    let mut buf = Vec::with_capacity(32 + msg.len());
    buf.extend_from_slice(za);
    buf.extend_from_slice(msg);
    let h = sm3(&buf);
    BigUint::from_bytes_be(&h) % n
}

/// **Sign** `msg` with private key `d` under user identifier `id`.
///
/// Caller must ensure `pa = d·G` matches `d` (the same point is used
/// in ZA computation and is exposed in the public key).
pub fn sign(msg: &[u8], d: &BigUint, pa: &Point, id: &[u8], curve: &CurveParams) -> Sm2Signature {
    let z = za(id, pa, curve);
    let e = message_digest(&z, msg, &curve.n);
    let a = curve.a_fe();

    loop {
        let k = random_scalar(&curve.n);
        if k.is_zero() {
            continue;
        }
        let kg = curve.generator().scalar_mul_ct(&k, &a, curve.order_bits());
        let x1 = match &kg {
            Point::Affine { x, .. } => x.value.clone(),
            Point::Infinity => continue,
        };
        let r = (&e + &x1) % &curve.n;
        if r.is_zero() || (&r + &k) == curve.n {
            continue;
        }
        // s = (1 + d)^(-1) · (k − r·d) mod n.  The subtraction is
        // performed in the integers (lifted to BigInt to handle the
        // possibly-negative intermediate) and then reduced mod n.
        let one_plus_d = (BigUint::one() + d) % &curve.n;
        let inv = match mod_inverse(&one_plus_d, &curve.n) {
            Some(v) => v,
            None => continue,
        };
        let rd = (&r * d) % &curve.n;
        // k − r·d  ≡  k + (n − rd)  (mod n).
        let k_minus_rd = (&k + &curve.n - &rd) % &curve.n;
        let s = (&inv * &k_minus_rd) % &curve.n;
        if s.is_zero() {
            continue;
        }
        return Sm2Signature { r, s };
    }
}

/// **Verify** that `sig` is a valid SM2 signature over `msg` with
/// signer public key `pa` and identifier `id`.
pub fn verify(msg: &[u8], sig: &Sm2Signature, pa: &Point, id: &[u8], curve: &CurveParams) -> bool {
    if sig.r.is_zero() || sig.r >= curve.n || sig.s.is_zero() || sig.s >= curve.n {
        return false;
    }
    let z = match try_za(id, pa, curve) {
        Some(z) => z,
        None => return false,
    };
    let e = message_digest(&z, msg, &curve.n);
    let a = curve.a_fe();

    let t = (&sig.r + &sig.s) % &curve.n;
    if t.is_zero() {
        return false;
    }
    let sg = curve.generator().scalar_mul(&sig.s, &a);
    let tp = pa.scalar_mul(&t, &a);
    let sum = sg.add(&tp, &a);
    let x1 = match sum {
        Point::Affine { x, .. } => x.value,
        Point::Infinity => return false,
    };
    ((&e + &x1) % &curve.n) == sig.r
}

// ── Public-key encryption (GB/T 32918.4) ────────────────────────────

/// SM2-specific KDF (GB/T 32918.4 §5.4.3): iterated SM3.
fn sm2_kdf(z: &[u8], out_len: usize) -> Vec<u8> {
    let mut out = Vec::with_capacity(out_len);
    let mut ct: u32 = 1;
    while out.len() < out_len {
        let mut buf = Vec::with_capacity(z.len() + 4);
        buf.extend_from_slice(z);
        buf.extend_from_slice(&ct.to_be_bytes());
        out.extend_from_slice(&sm3(&buf));
        ct = ct.wrapping_add(1);
    }
    out.truncate(out_len);
    out
}

/// **Encrypt** `msg` for recipient public key `pb`.  Output is the
/// `C1 || C3 || C2` form (GB/T 32918.4-2016).
///
/// `C1` is the 65-byte SEC1-uncompressed ephemeral point `04 || X || Y`,
/// `C3` is a 32-byte SM3 integrity tag, and `C2` is the same length as
/// the plaintext `msg`.
pub fn encrypt(msg: &[u8], pb: &Point, curve: &CurveParams) -> Vec<u8> {
    encrypt_checked(msg, pb, curve).expect("SM2 recipient public key must be valid")
}

/// Checked SM2 encryption that rejects invalid recipient public keys.
pub fn encrypt_checked(
    msg: &[u8],
    pb: &Point,
    curve: &CurveParams,
) -> Result<Vec<u8>, &'static str> {
    if !curve.is_valid_public_point(pb) {
        return Err("recipient public key is not a valid point on this curve");
    }
    let a = curve.a_fe();
    loop {
        let k = random_scalar(&curve.n);
        if k.is_zero() {
            continue;
        }
        let c1 = curve.generator().scalar_mul_ct(&k, &a, curve.order_bits());
        let (c1x, c1y) = match &c1 {
            Point::Affine { x, y } => (x.value.clone(), y.value.clone()),
            Point::Infinity => continue,
        };
        let shared = pb.scalar_mul_ct(&k, &a, curve.order_bits());
        let (x2, y2) = match &shared {
            Point::Affine { x, y } => (x.value.clone(), y.value.clone()),
            Point::Infinity => continue,
        };
        // KDF input: x2 || y2
        let mut kdf_input = Vec::with_capacity(64);
        kdf_input.extend_from_slice(&bytes_be(&x2, 32));
        kdf_input.extend_from_slice(&bytes_be(&y2, 32));
        let t = sm2_kdf(&kdf_input, msg.len());
        if t.iter().all(|&b| b == 0) {
            // All-zero stream is disallowed by the standard.
            continue;
        }
        let c2: Vec<u8> = msg.iter().zip(t.iter()).map(|(m, k)| m ^ k).collect();
        // C3 = SM3(x2 || M || y2)
        let mut c3_input = Vec::with_capacity(32 + msg.len() + 32);
        c3_input.extend_from_slice(&bytes_be(&x2, 32));
        c3_input.extend_from_slice(msg);
        c3_input.extend_from_slice(&bytes_be(&y2, 32));
        let c3 = sm3(&c3_input);
        // Assemble C1 || C3 || C2.  C1 is SEC1-uncompressed: 04 || X || Y.
        let mut out = Vec::with_capacity(1 + 64 + 32 + msg.len());
        out.push(0x04);
        out.extend_from_slice(&bytes_be(&c1x, 32));
        out.extend_from_slice(&bytes_be(&c1y, 32));
        out.extend_from_slice(&c3);
        out.extend_from_slice(&c2);
        return Ok(out);
    }
}

/// **Decrypt** an SM2 ciphertext under private key `d`.
///
/// Returns `None` if the integrity tag `C3` does not match (e.g. the
/// ciphertext was tampered with) or the input is malformed.
pub fn decrypt(ct: &[u8], d: &BigUint, curve: &CurveParams) -> Option<Vec<u8>> {
    // Layout: 04 || X(32) || Y(32) || C3(32) || C2(msg_len).
    if ct.len() < 1 + 64 + 32 {
        return None;
    }
    if ct[0] != 0x04 {
        // We only accept the uncompressed encoding for now.
        return None;
    }
    let c1x = BigUint::from_bytes_be(&ct[1..33]);
    let c1y = BigUint::from_bytes_be(&ct[33..65]);
    let c3_expected = &ct[65..97];
    let c2 = &ct[97..];

    let c1 = Point::Affine {
        x: curve.fe(c1x.clone()),
        y: curve.fe(c1y.clone()),
    };
    if !curve.is_on_curve(&c1) {
        return None;
    }
    let a = curve.a_fe();
    let shared = c1.scalar_mul_ct(d, &a, curve.order_bits());
    let (x2, y2) = match &shared {
        Point::Affine { x, y } => (x.value.clone(), y.value.clone()),
        Point::Infinity => return None,
    };
    let mut kdf_input = Vec::with_capacity(64);
    kdf_input.extend_from_slice(&bytes_be(&x2, 32));
    kdf_input.extend_from_slice(&bytes_be(&y2, 32));
    let t = sm2_kdf(&kdf_input, c2.len());
    if t.iter().all(|&b| b == 0) {
        return None;
    }
    let msg: Vec<u8> = c2.iter().zip(t.iter()).map(|(c, k)| c ^ k).collect();
    let mut c3_input = Vec::with_capacity(32 + msg.len() + 32);
    c3_input.extend_from_slice(&bytes_be(&x2, 32));
    c3_input.extend_from_slice(&msg);
    c3_input.extend_from_slice(&bytes_be(&y2, 32));
    let c3 = sm3(&c3_input);
    // Constant-time compare on a 32-byte tag (small fixed length).
    let mut diff = 0u8;
    for i in 0..32 {
        diff |= c3[i] ^ c3_expected[i];
    }
    if diff != 0 {
        return None;
    }
    Some(msg)
}

// ── Key generation helper ───────────────────────────────────────────

/// Derive the SM2 public point `P = d·G` for the given private scalar.
pub fn public_key_from_private(d: &BigUint, curve: &CurveParams) -> Point {
    let a = curve.a_fe();
    curve.generator().scalar_mul_ct(d, &a, curve.order_bits())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sm2_curve() -> CurveParams {
        CurveParams::sm2()
    }

    /// **Test 1 — public-key derivation**: known test vector from
    /// draft-shen-sm2-ecdsa-02 §A.2.
    /// dA = 3945208F7B2144B13F36E38AC6D39F95889393692860B51A42FB81EF4DF7C5B8
    /// xA = 09F9DF311E5421A150DD7D161E4BC5C672179FAD1833FC076BB08FF356F35020
    /// yA = CCEA490CE26775A52DC6EA718CC1AA600AED05FBF35E084A6632F6072DA9AD13
    #[test]
    fn sm2_public_key_test_vector() {
        let curve = sm2_curve();
        let d = BigUint::parse_bytes(
            b"3945208F7B2144B13F36E38AC6D39F95889393692860B51A42FB81EF4DF7C5B8",
            16,
        )
        .unwrap();
        let pa = public_key_from_private(&d, &curve);
        let (xa, ya) = match pa {
            Point::Affine { x, y } => (x.value, y.value),
            _ => panic!("PA should not be infinity"),
        };
        let want_x = BigUint::parse_bytes(
            b"09F9DF311E5421A150DD7D161E4BC5C672179FAD1833FC076BB08FF356F35020",
            16,
        )
        .unwrap();
        let want_y = BigUint::parse_bytes(
            b"CCEA490CE26775A52DC6EA718CC1AA600AED05FBF35E084A6632F6072DA9AD13",
            16,
        )
        .unwrap();
        assert_eq!(xa, want_x);
        assert_eq!(ya, want_y);
    }

    /// **Test 2 — generator on curve**: structural check.
    #[test]
    fn sm2_generator_is_on_curve() {
        let curve = sm2_curve();
        assert!(curve.is_on_curve(&curve.generator()));
    }

    /// **Test 3 — sign / verify roundtrip**.
    #[test]
    fn sm2_sign_verify_roundtrip() {
        let curve = sm2_curve();
        let d = BigUint::parse_bytes(
            b"3945208F7B2144B13F36E38AC6D39F95889393692860B51A42FB81EF4DF7C5B8",
            16,
        )
        .unwrap();
        let pa = public_key_from_private(&d, &curve);
        let msg = b"hello SM2!";
        let sig = sign(msg, &d, &pa, DEFAULT_ID, &curve);
        assert!(verify(msg, &sig, &pa, DEFAULT_ID, &curve));
    }

    /// **Test 4 — wrong message rejection**.
    #[test]
    fn sm2_wrong_message_fails() {
        let curve = sm2_curve();
        let d = BigUint::parse_bytes(
            b"3945208F7B2144B13F36E38AC6D39F95889393692860B51A42FB81EF4DF7C5B8",
            16,
        )
        .unwrap();
        let pa = public_key_from_private(&d, &curve);
        let sig = sign(b"original", &d, &pa, DEFAULT_ID, &curve);
        assert!(!verify(b"tampered", &sig, &pa, DEFAULT_ID, &curve));
    }

    /// **Test 5 — wrong key rejection**.
    #[test]
    fn sm2_wrong_key_fails() {
        let curve = sm2_curve();
        let d1 = BigUint::parse_bytes(
            b"3945208F7B2144B13F36E38AC6D39F95889393692860B51A42FB81EF4DF7C5B8",
            16,
        )
        .unwrap();
        let d2 = BigUint::parse_bytes(
            b"1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF",
            16,
        )
        .unwrap();
        let pa1 = public_key_from_private(&d1, &curve);
        let pa2 = public_key_from_private(&d2, &curve);
        let sig = sign(b"msg", &d1, &pa1, DEFAULT_ID, &curve);
        assert!(!verify(b"msg", &sig, &pa2, DEFAULT_ID, &curve));
    }

    /// **Test 6 — encrypt / decrypt roundtrip**.
    #[test]
    fn sm2_encrypt_decrypt_roundtrip() {
        let curve = sm2_curve();
        let d = BigUint::parse_bytes(
            b"3945208F7B2144B13F36E38AC6D39F95889393692860B51A42FB81EF4DF7C5B8",
            16,
        )
        .unwrap();
        let pb = public_key_from_private(&d, &curve);
        let msg = b"encrypted hello, SM2 world!";
        let ct = encrypt(msg, &pb, &curve);
        let pt = decrypt(&ct, &d, &curve).expect("decrypt should succeed");
        assert_eq!(pt, msg);
    }

    /// **Test 7 — tampered ciphertext rejection**.
    #[test]
    fn sm2_tampered_ciphertext_rejected() {
        let curve = sm2_curve();
        let d = BigUint::parse_bytes(
            b"3945208F7B2144B13F36E38AC6D39F95889393692860B51A42FB81EF4DF7C5B8",
            16,
        )
        .unwrap();
        let pb = public_key_from_private(&d, &curve);
        let mut ct = encrypt(b"msg", &pb, &curve);
        // Flip a bit in the last (C2) block.
        let last = ct.len() - 1;
        ct[last] ^= 0x01;
        // SM2 detects tampering via the C3 integrity tag.
        assert!(decrypt(&ct, &d, &curve).is_none());
    }

    #[test]
    fn sm2_rejects_invalid_public_inputs() {
        let curve = sm2_curve();
        let d = BigUint::parse_bytes(
            b"3945208F7B2144B13F36E38AC6D39F95889393692860B51A42FB81EF4DF7C5B8",
            16,
        )
        .unwrap();
        let pa = public_key_from_private(&d, &curve);
        let sig = sign(b"msg", &d, &pa, DEFAULT_ID, &curve);

        assert!(!verify(b"msg", &sig, &Point::Infinity, DEFAULT_ID, &curve));
        assert!(encrypt_checked(b"msg", &Point::Infinity, &curve).is_err());
    }

    /// **Test 8 — ZA is deterministic and matches a Python reference**.
    ///
    /// Cross-checked against an independent SM3-from-scratch
    /// implementation in Python: with `ID = "1234567812345678"` and PA
    /// from the test vector above,
    /// `ZA = b2e14c5c79c6df5b85f4fe7ed8db7a262b9da7e07ccb0ea9f4747b8ccda8a4f3`.
    #[test]
    fn sm2_za_known_vector() {
        let curve = sm2_curve();
        let d = BigUint::parse_bytes(
            b"3945208F7B2144B13F36E38AC6D39F95889393692860B51A42FB81EF4DF7C5B8",
            16,
        )
        .unwrap();
        let pa = public_key_from_private(&d, &curve);
        let z = za(DEFAULT_ID, &pa, &curve);
        let want = hex_to_bytes("b2e14c5c79c6df5b85f4fe7ed8db7a262b9da7e07ccb0ea9f4747b8ccda8a4f3");
        assert_eq!(&z[..], &want[..]);
    }

    fn hex_to_bytes(s: &str) -> Vec<u8> {
        (0..s.len())
            .step_by(2)
            .map(|i| u8::from_str_radix(&s[i..i + 2], 16).unwrap())
            .collect()
    }
}
