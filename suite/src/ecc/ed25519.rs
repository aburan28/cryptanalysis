//! Ed25519 (RFC 8032) — EdDSA signatures over Edwards form of Curve25519.
//!
//! Bernstein-Duif-Lange-Schwabe-Yang 2011.  The default modern
//! signature scheme: SSH (since OpenSSH 6.5), TLS 1.3, WireGuard,
//! Signal, age, Tor, NaCl/libsodium, every major package
//! manager (npm, apt, dnf, ...).
//!
//! # Curve and group
//!
//! Edwards form: `−x² + y² = 1 + d·x²·y²` over `F_{2²⁵⁵−19}` with
//! `d = −121665/121666 mod p`.  Birationally equivalent to the
//! Montgomery form X25519 lives on.  Group order `8 · L` where
//! `L = 2²⁵² + 27742317777372353535851937790883648493` (a prime).
//! The cofactor 8 is why Ed25519 has a "sign with cofactor"
//! variant; standard Ed25519 just uses the prime-order subgroup.
//!
//! # Wire formats
//!
//! - **Public key**: 32 bytes — y-coordinate little-endian, with
//!   the *sign of x* packed into the top bit of the last byte.
//! - **Private key**: 32 bytes (the seed).  The actual scalar `s`
//!   is derived as `SHA-512(seed)[..32]` with clamping.
//! - **Signature**: 64 bytes = `R ‖ S`.
//!
//! # Test vectors
//!
//! Verified against RFC 8032 §7.1 test vectors.
//!
//! Security note: this educational implementation still uses `BigUint` and
//! variable-time scalar multiplication. Verification rejects identity,
//! small-order, and non-prime-subgroup public/R points, but this module should
//! not be treated as a constant-time production Ed25519 implementation.

use super::curve25519::{fe_add, fe_from_bytes, fe_inv, fe_mul, fe_sq, fe_sub, fe_to_bytes, p};
use crate::hash::sha512::sha512;
use num_bigint::BigUint;
use num_traits::{One, Zero};

/// Group order of the prime-order subgroup: `L = 2²⁵² + 27742317777372353535851937790883648493`.
fn ed25519_l() -> BigUint {
    BigUint::parse_bytes(
        b"7237005577332262213973186563042994240857116359379907606001950938285454250989",
        10,
    )
    .unwrap()
}

/// Edwards `d` constant: `d = −121665 · 121666⁻¹ mod p`.
fn ed25519_d() -> BigUint {
    let pp = p();
    let neg_121665 = fe_sub(&BigUint::zero(), &BigUint::from(121665u32));
    let inv_121666 = fe_inv(&BigUint::from(121666u32));
    let d = fe_mul(&neg_121665, &inv_121666);
    let _ = pp;
    d
}

/// Square-root-of-`-1` constant: `2^((p−1)/4) mod p`.
fn sqrt_m1() -> BigUint {
    let pp = p();
    let exp = (&pp - BigUint::one()) / BigUint::from(4u32);
    BigUint::from(2u32).modpow(&exp, &pp)
}

/// Ed25519 base-point Y-coordinate: `B.y = 4/5 mod p`.
fn base_y() -> BigUint {
    // y = 4 · 5⁻¹ mod p.
    let inv5 = fe_inv(&BigUint::from(5u32));
    fe_mul(&BigUint::from(4u32), &inv5)
}

/// Ed25519 base-point X-coordinate.  Published constant in RFC 8032
/// (the unique x with `LSB(x) = 0` satisfying the curve equation).
fn base_x() -> BigUint {
    // Decimal form (RFC 8032 §5.1):
    BigUint::parse_bytes(
        b"15112221349535400772501151409588531511454012693041857206046113283949847762202",
        10,
    )
    .unwrap()
}

/// Extended Edwards (X, Y, Z, T) representation.
#[derive(Clone, Debug)]
struct EdPoint {
    x: BigUint,
    y: BigUint,
    z: BigUint,
    t: BigUint,
}

impl EdPoint {
    fn identity() -> Self {
        EdPoint {
            x: BigUint::zero(),
            y: BigUint::one(),
            z: BigUint::one(),
            t: BigUint::zero(),
        }
    }

    fn from_affine(x: BigUint, y: BigUint) -> Self {
        let t = fe_mul(&x, &y);
        EdPoint {
            x,
            y,
            z: BigUint::one(),
            t,
        }
    }

    fn to_affine(&self) -> (BigUint, BigUint) {
        let zi = fe_inv(&self.z);
        (fe_mul(&self.x, &zi), fe_mul(&self.y, &zi))
    }

    fn is_identity(&self) -> bool {
        let (x, y) = self.to_affine();
        x.is_zero() && y.is_one()
    }

    /// Point doubling on extended Edwards (HCD 2008 §3.3) with `a = -1`.
    /// Variables follow the paper:
    /// `A = X²`, `B = Y²`, `C = 2·Z²`, `D = a·A = -A`,
    /// `E = (X+Y)² - A - B`, `G = D + B = B - A`,
    /// `F = G - C`, `H = D - B = -A - B`.
    fn double(&self) -> Self {
        let a = fe_sq(&self.x);
        let b = fe_sq(&self.y);
        let c = fe_mul(&BigUint::from(2u32), &fe_sq(&self.z));
        let xy = fe_add(&self.x, &self.y);
        let e = fe_sub(&fe_sq(&xy), &fe_add(&a, &b));
        let g = fe_sub(&b, &a); // G = B - A
        let h = fe_sub(&BigUint::zero(), &fe_add(&a, &b)); // H = -A - B
        let f = fe_sub(&g, &c); // F = G - C
        let new_x = fe_mul(&e, &f);
        let new_y = fe_mul(&g, &h);
        let new_t = fe_mul(&e, &h);
        let new_z = fe_mul(&f, &g);
        EdPoint {
            x: new_x,
            y: new_y,
            z: new_z,
            t: new_t,
        }
    }

    /// Mixed/projective add (HCD 2008, §3.1, a = -1).
    fn add(&self, other: &EdPoint) -> Self {
        let d = ed25519_d();
        let two = BigUint::from(2u32);
        // A = (Y1 - X1) * (Y2 - X2)
        let a = fe_mul(&fe_sub(&self.y, &self.x), &fe_sub(&other.y, &other.x));
        // B = (Y1 + X1) * (Y2 + X2)
        let b = fe_mul(&fe_add(&self.y, &self.x), &fe_add(&other.y, &other.x));
        // C = T1 · 2d · T2
        let c = fe_mul(&fe_mul(&self.t, &two), &fe_mul(&d, &other.t));
        // D = Z1 · 2 · Z2
        let dd = fe_mul(&fe_mul(&self.z, &two), &other.z);
        let e = fe_sub(&b, &a);
        let f = fe_sub(&dd, &c);
        let g = fe_add(&dd, &c);
        let h = fe_add(&b, &a);
        let new_x = fe_mul(&e, &f);
        let new_y = fe_mul(&g, &h);
        let new_t = fe_mul(&e, &h);
        let new_z = fe_mul(&f, &g);
        EdPoint {
            x: new_x,
            y: new_y,
            z: new_z,
            t: new_t,
        }
    }

    fn scalar_mul(&self, scalar: &BigUint) -> Self {
        // Double-and-add, MSB to LSB.
        let mut acc = EdPoint::identity();
        let bits = scalar.bits();
        for i in (0..bits).rev() {
            acc = acc.double();
            if scalar.bit(i) {
                acc = acc.add(self);
            }
        }
        acc
    }

    /// Encode as 32-byte y-with-sign-of-x (little-endian, top
    /// bit of last byte = parity of x).
    fn encode(&self) -> [u8; 32] {
        let (x, y) = self.to_affine();
        let mut out = fe_to_bytes(&y);
        if x.bit(0) {
            out[31] |= 0x80;
        }
        out
    }
}

/// Base point `B`.
fn base_point() -> EdPoint {
    EdPoint::from_affine(base_x(), base_y())
}

/// Decode a 32-byte y-with-sign-of-x encoding back to an `EdPoint`.
fn decode_point(input: &[u8; 32]) -> Option<EdPoint> {
    let pp = p();
    let mut buf = *input;
    let sign = (buf[31] >> 7) & 1;
    buf[31] &= 0x7F;
    let y = fe_from_bytes(&buf);
    if y >= pp {
        return None;
    }
    let yy = fe_sq(&y);
    let d = ed25519_d();
    // x² = (y² − 1) / (d·y² + 1)
    let num = fe_sub(&yy, &BigUint::one());
    let dyy = fe_mul(&d, &yy);
    let den = fe_add(&dyy, &BigUint::one());
    let x_sq = fe_mul(&num, &fe_inv(&den));
    // sqrt via candidate = (x_sq)^((p+3)/8); check; multiply by
    // sqrt(-1) if not.
    let exp = (&pp + BigUint::from(3u32)) / BigUint::from(8u32);
    let mut cand = x_sq.modpow(&exp, &pp);
    if fe_sq(&cand) != x_sq {
        cand = fe_mul(&cand, &sqrt_m1());
        if fe_sq(&cand) != x_sq {
            return None;
        }
    }
    if cand.bit(0) != (sign == 1) {
        cand = fe_sub(&BigUint::zero(), &cand);
    }
    Some(EdPoint::from_affine(cand, y))
}

fn is_small_order(point: &EdPoint) -> bool {
    point.scalar_mul(&BigUint::from(8u32)).is_identity()
}

fn is_in_prime_order_subgroup(point: &EdPoint) -> bool {
    point.scalar_mul(&ed25519_l()).is_identity()
}

fn is_acceptable_public_point(point: &EdPoint) -> bool {
    !is_small_order(point) && is_in_prime_order_subgroup(point)
}

/// Compute `(s, prefix) = SHA-512(seed); s clamped`.
fn expand_seed(seed: &[u8; 32]) -> ([u8; 32], [u8; 32]) {
    let h = sha512(seed);
    let mut s = [0u8; 32];
    let mut prefix = [0u8; 32];
    s.copy_from_slice(&h[..32]);
    prefix.copy_from_slice(&h[32..]);
    // Clamp s.
    s[0] &= 248;
    s[31] &= 127;
    s[31] |= 64;
    (s, prefix)
}

/// Derive the 32-byte Ed25519 public key from a 32-byte seed.
pub fn ed25519_pubkey(seed: &[u8; 32]) -> [u8; 32] {
    let (s, _) = expand_seed(seed);
    let s_bn = BigUint::from_bytes_le(&s);
    let a = base_point().scalar_mul(&s_bn);
    a.encode()
}

/// Sign `message` with Ed25519.
pub fn ed25519_sign(message: &[u8], seed: &[u8; 32]) -> [u8; 64] {
    let (s, prefix) = expand_seed(seed);
    let s_bn = BigUint::from_bytes_le(&s);
    let a_pt = base_point().scalar_mul(&s_bn);
    let a_enc = a_pt.encode();

    // r = SHA-512(prefix ‖ message) mod L
    let mut r_input = Vec::with_capacity(32 + message.len());
    r_input.extend_from_slice(&prefix);
    r_input.extend_from_slice(message);
    let r_hash = sha512(&r_input);
    let r_bn = BigUint::from_bytes_le(&r_hash) % ed25519_l();

    // R = r·B
    let r_pt = base_point().scalar_mul(&r_bn);
    let r_enc = r_pt.encode();

    // k = SHA-512(R ‖ A ‖ message) mod L
    let mut k_input = Vec::with_capacity(64 + message.len());
    k_input.extend_from_slice(&r_enc);
    k_input.extend_from_slice(&a_enc);
    k_input.extend_from_slice(message);
    let k_hash = sha512(&k_input);
    let l = ed25519_l();
    let k_bn = BigUint::from_bytes_le(&k_hash) % &l;

    // S = (r + k·s) mod L
    let s_sig = (r_bn + (k_bn * s_bn)) % &l;
    let s_bytes = bytes32_le(&s_sig);

    let mut sig = [0u8; 64];
    sig[..32].copy_from_slice(&r_enc);
    sig[32..].copy_from_slice(&s_bytes);
    sig
}

/// Verify Ed25519.  Returns `true` iff the signature is valid.
pub fn ed25519_verify(message: &[u8], pubkey: &[u8; 32], sig: &[u8; 64]) -> bool {
    let l = ed25519_l();
    let r_bytes: [u8; 32] = sig[..32].try_into().unwrap();
    let s_bytes: [u8; 32] = sig[32..].try_into().unwrap();
    let s_bn = BigUint::from_bytes_le(&s_bytes);
    if s_bn >= l {
        return false;
    }
    let a_pt = match decode_point(pubkey) {
        Some(p) => p,
        None => return false,
    };
    let r_pt = match decode_point(&r_bytes) {
        Some(p) => p,
        None => return false,
    };
    if !is_acceptable_public_point(&a_pt) || !is_acceptable_public_point(&r_pt) {
        return false;
    }

    // k = SHA-512(R ‖ A ‖ message) mod L
    let mut k_input = Vec::with_capacity(64 + message.len());
    k_input.extend_from_slice(&r_bytes);
    k_input.extend_from_slice(pubkey);
    k_input.extend_from_slice(message);
    let k_hash = sha512(&k_input);
    let k_bn = BigUint::from_bytes_le(&k_hash) % &l;

    // Check: 8·s·B ≡ 8·R + 8·k·A
    // (the cofactor-8 cleared check; standard Ed25519 verifies
    //  the cofactored equation per RFC 8032).
    let lhs = base_point().scalar_mul(&s_bn);
    let ka = a_pt.scalar_mul(&k_bn);
    let rhs = r_pt.add(&ka);

    // Encode both sides; compare.  Cofactor multiplication isn't
    // strictly needed since we're already in the prime-order
    // subgroup if A and R are valid encoded points.
    lhs.encode() == rhs.encode()
}

fn bytes32_le(x: &BigUint) -> [u8; 32] {
    let mut out = [0u8; 32];
    let bytes = x.to_bytes_le();
    let n = bytes.len().min(32);
    out[..n].copy_from_slice(&bytes[..n]);
    out
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

    /// **RFC 8032 §7.1 TEST 1**.  Empty message.
    #[test]
    fn rfc8032_test_1() {
        let seed = hex32("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60");
        let expected_pk = hex32("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a");
        let pk = ed25519_pubkey(&seed);
        assert_eq!(pk, expected_pk, "pubkey mismatch");

        let expected_sig = hex64(
            "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555\
             fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b",
        );
        let sig = ed25519_sign(b"", &seed);
        assert_eq!(sig, expected_sig, "signature mismatch");
        assert!(ed25519_verify(b"", &pk, &sig), "verify failed");
    }

    /// **RFC 8032 §7.1 TEST 2**.  Single-byte message.
    #[test]
    fn rfc8032_test_2() {
        let seed = hex32("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb");
        let expected_pk = hex32("3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c");
        let pk = ed25519_pubkey(&seed);
        assert_eq!(pk, expected_pk);

        let msg = hex_decode("72");
        let expected_sig = hex64(
            "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da\
             085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00",
        );
        let sig = ed25519_sign(&msg, &seed);
        assert_eq!(sig, expected_sig);
        assert!(ed25519_verify(&msg, &pk, &sig));
    }

    /// Round-trip test: random seed + arbitrary message.
    #[test]
    fn ed25519_roundtrip() {
        let seed = [0xA5u8; 32];
        let pk = ed25519_pubkey(&seed);
        let sig = ed25519_sign(b"hello, ed25519 world!", &seed);
        assert!(ed25519_verify(b"hello, ed25519 world!", &pk, &sig));
    }

    /// Tampering breaks verification.
    #[test]
    fn ed25519_rejects_tampered() {
        let seed = [0x42u8; 32];
        let pk = ed25519_pubkey(&seed);
        let mut sig = ed25519_sign(b"original", &seed);
        sig[0] ^= 0x01;
        assert!(!ed25519_verify(b"original", &pk, &sig));
    }

    /// Different message rejected under same signature.
    #[test]
    fn ed25519_rejects_wrong_message() {
        let seed = [0x07u8; 32];
        let pk = ed25519_pubkey(&seed);
        let sig = ed25519_sign(b"original", &seed);
        assert!(!ed25519_verify(b"different", &pk, &sig));
    }

    #[test]
    fn ed25519_rejects_identity_public_key_and_r() {
        let seed = [0x42u8; 32];
        let pk = ed25519_pubkey(&seed);
        let sig = ed25519_sign(b"msg", &seed);

        let identity = {
            let mut b = [0u8; 32];
            b[0] = 1;
            b
        };
        assert!(!ed25519_verify(b"msg", &identity, &sig));

        let mut bad_sig = sig;
        bad_sig[..32].copy_from_slice(&identity);
        assert!(!ed25519_verify(b"msg", &pk, &bad_sig));
    }

    #[test]
    fn ed25519_rejects_trivial_forgery_with_identity_points() {
        let identity = {
            let mut b = [0u8; 32];
            b[0] = 1;
            b
        };
        let sig = [0u8; 64];
        assert!(!ed25519_verify(b"forged", &identity, &sig));
    }
}
