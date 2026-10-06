//! **Ed448-Goldilocks signatures** — RFC 8032 §5.2.
//!
//! EdDSA at the 224-bit security level: Hamburg's "Goldilocks"
//! curve, twisted-Edwards form `x² + y² = 1 + d·x²·y²` with
//! `d = -39081 mod p`, over `F_{2⁴⁴⁸ - 2²²⁴ - 1}`.  Cofactor 4;
//! prime-order subgroup of order
//! `L = 2⁴⁴⁶ − 0x8335dc163bb124b65129c96fde933d8d723a70aadc873d6d54a7bb0d`.
//!
//! # Wire formats
//!
//! - **Seed / private key**: 57 bytes.
//! - **Public key**: 57 bytes — y-coordinate little-endian in
//!   bytes 0..56, with the sign of x packed in the high bit of
//!   byte 56 (the low 7 bits of byte 56 hold y's high byte).
//! - **Signature**: 114 bytes = `R ‖ S`, each 57 bytes.
//!
//! Hashing is SHAKE256 (RFC 8032 §5.2 binds Ed448 to it). Domain
//! separation per RFC 8032: every hash that consumes user data is
//! prefixed with `"SigEd448" || 0x00 || |context| || context`.
//! The "vanilla" Ed448 of this module uses an empty pre-hash flag
//! (phflag = 0); context may be empty or up to 255 bytes.
//!
//! # Test vectors
//!
//! Verified against RFC 8032 §7.4 (empty message, empty context)
//! and the "1 octet with context" vector.
//!
//! Security note: this is an educational implementation. Scalar
//! multiplication is variable-time (BigUint), and no attempt is
//! made to harden against side channels.

use crate::hash::sha3::shake256;
use num_bigint::BigUint;
use num_traits::{One, Zero};

// ---------------------------------------------------------------------------
// Field arithmetic over p = 2⁴⁴⁸ − 2²²⁴ − 1.
// ---------------------------------------------------------------------------

/// Ed448 field prime `p = 2⁴⁴⁸ − 2²²⁴ − 1`.
fn p() -> BigUint {
    (BigUint::one() << 448) - (BigUint::one() << 224) - BigUint::one()
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
        (&pp - ((b - a) % &pp)) % &pp
    }
}

fn fe_mul(a: &BigUint, b: &BigUint) -> BigUint {
    fe_reduce(&(a * b))
}

fn fe_sq(a: &BigUint) -> BigUint {
    fe_mul(a, a)
}

fn fe_inv(a: &BigUint) -> BigUint {
    let pp = p();
    let exp = &pp - BigUint::from(2u32);
    a.modpow(&exp, &pp)
}

/// 57-byte little-endian decode (low 56 bytes are the value;
/// byte 56 must be zero apart from the high bit used by point
/// encoding — callers strip that bit before invoking).
fn fe_from_bytes57(bytes: &[u8; 57]) -> BigUint {
    let mut buf = [0u8; 57];
    buf.copy_from_slice(bytes);
    fe_reduce(&BigUint::from_bytes_le(&buf))
}

fn fe_to_bytes57(a: &BigUint) -> [u8; 57] {
    let mut out = [0u8; 57];
    let bytes = a.to_bytes_le();
    let n = bytes.len().min(57);
    out[..n].copy_from_slice(&bytes[..n]);
    out
}

// ---------------------------------------------------------------------------
// Curve constants.
// ---------------------------------------------------------------------------

/// Edwards `d = -39081 mod p`.
fn ed448_d() -> BigUint {
    fe_sub(&BigUint::zero(), &BigUint::from(39081u32))
}

/// Group order of the prime-order subgroup,
/// `L = 2⁴⁴⁶ − 0x8335dc163bb124b65129c96fde933d8d723a70aadc873d6d54a7bb0d`.
fn ed448_l() -> BigUint {
    let two446 = BigUint::one() << 446;
    let sub = BigUint::parse_bytes(
        b"8335dc163bb124b65129c96fde933d8d723a70aadc873d6d54a7bb0d",
        16,
    )
    .unwrap();
    two446 - sub
}

/// Ed448 base-point coordinates (RFC 8032 §5.2.5).
fn base_x() -> BigUint {
    BigUint::parse_bytes(
        b"4F1970C66BED0DED221D15A622BF36DA9E146570470F1767EA6DE324\
          A3D3A46412AE1AF72AB66511433B80E18B00938E2626A82BC70CC05E",
        16,
    )
    .unwrap()
}

fn base_y() -> BigUint {
    BigUint::parse_bytes(
        b"693F46716EB6BC248876203756C9C7624BEA73736CA3984087789C1E\
          05A0C2D73AD3FF1CE67C39C4FDBD132C4ED7C8AD9808795BF230FA14",
        16,
    )
    .unwrap()
}

// ---------------------------------------------------------------------------
// Edwards point in projective (X : Y : Z) coordinates.
//
// Ed448 uses the untwisted Edwards form (a = 1), for which the
// projective addition formulas of Hisil-Wong-Carter-Dawson (HWCD
// 2008, "Twisted Edwards Curves Revisited", §3.2 with a = 1) are
// strongly unified and the cheaper `T`-less projective form is
// fine since we don't need the speed of extended coordinates.
// ---------------------------------------------------------------------------

#[derive(Clone, Debug)]
struct EdPoint {
    x: BigUint,
    y: BigUint,
    z: BigUint,
}

impl EdPoint {
    fn identity() -> Self {
        EdPoint {
            x: BigUint::zero(),
            y: BigUint::one(),
            z: BigUint::one(),
        }
    }

    fn from_affine(x: BigUint, y: BigUint) -> Self {
        EdPoint {
            x,
            y,
            z: BigUint::one(),
        }
    }

    fn to_affine(&self) -> (BigUint, BigUint) {
        let zi = fe_inv(&self.z);
        (fe_mul(&self.x, &zi), fe_mul(&self.y, &zi))
    }

    /// Projective doubling on untwisted Edwards (`a = 1`).
    /// HWCD §3.3 with a=1:
    ///   B = (X+Y)²,  C = X²,  D = Y²,  E = C + D,  H = Z²,
    ///   J = E − 2H,  X' = (B − E) · J,  Y' = E · (C − D),  Z' = E · J.
    fn double(&self) -> Self {
        let b = fe_sq(&fe_add(&self.x, &self.y));
        let c = fe_sq(&self.x);
        let d = fe_sq(&self.y);
        let e = fe_add(&c, &d);
        let h = fe_sq(&self.z);
        let j = fe_sub(&e, &fe_add(&h, &h));
        let new_x = fe_mul(&fe_sub(&b, &e), &j);
        let new_y = fe_mul(&e, &fe_sub(&c, &d));
        let new_z = fe_mul(&e, &j);
        EdPoint {
            x: new_x,
            y: new_y,
            z: new_z,
        }
    }

    /// Projective addition on untwisted Edwards (`a = 1`).
    /// "Edwards curves" — Bernstein/Lange 2007, §6, projective:
    ///   A = Z1·Z2,  B = A²,  C = X1·X2,  D = Y1·Y2,
    ///   E = d·C·D,  F = B − E,  G = B + E,
    ///   X3 = A · F · ((X1+Y1)(X2+Y2) − C − D)
    ///   Y3 = A · G · (D − C)
    ///   Z3 = F · G
    fn add(&self, other: &EdPoint) -> Self {
        let d = ed448_d();
        let a = fe_mul(&self.z, &other.z);
        let b = fe_sq(&a);
        let c = fe_mul(&self.x, &other.x);
        let dd = fe_mul(&self.y, &other.y);
        let e = fe_mul(&d, &fe_mul(&c, &dd));
        let f = fe_sub(&b, &e);
        let g = fe_add(&b, &e);
        let xx = fe_mul(&fe_add(&self.x, &self.y), &fe_add(&other.x, &other.y));
        let h = fe_sub(&fe_sub(&xx, &c), &dd);
        let new_x = fe_mul(&a, &fe_mul(&f, &h));
        let new_y = fe_mul(&a, &fe_mul(&g, &fe_sub(&dd, &c)));
        let new_z = fe_mul(&f, &g);
        EdPoint {
            x: new_x,
            y: new_y,
            z: new_z,
        }
    }

    fn scalar_mul(&self, scalar: &BigUint) -> Self {
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

    /// Encode as 57 bytes: y little-endian in bytes 0..56,
    /// sign of x in the top bit of byte 56.
    fn encode(&self) -> [u8; 57] {
        let (x, y) = self.to_affine();
        let mut out = fe_to_bytes57(&y);
        // y < p < 2⁴⁴⁸, so byte 56 of fe_to_bytes57(y) is 0.
        if x.bit(0) {
            out[56] |= 0x80;
        }
        out
    }
}

fn base_point() -> EdPoint {
    EdPoint::from_affine(base_x(), base_y())
}

/// Decode a 57-byte Ed448 point.
///
/// Curve equation (untwisted, a = 1): `x² + y² = 1 + d·x²·y²`,
/// so `x² = (y² − 1) / (d·y² − 1) mod p`.
fn decode_point(input: &[u8; 57]) -> Option<EdPoint> {
    let pp = p();
    let mut buf = *input;
    let sign = (buf[56] >> 7) & 1;
    buf[56] &= 0x7F;
    let y = fe_from_bytes57(&buf);
    if y >= pp {
        return None;
    }
    let yy = fe_sq(&y);
    let d = ed448_d();
    let num = fe_sub(&yy, &BigUint::one());
    let den = fe_sub(&fe_mul(&d, &yy), &BigUint::one());
    if den.is_zero() {
        return None;
    }
    let x_sq = fe_mul(&num, &fe_inv(&den));

    // sqrt mod p for p ≡ 3 (mod 4): candidate = x_sq^((p+1)/4).
    let exp = (&pp + BigUint::one()) / BigUint::from(4u32);
    let cand = x_sq.modpow(&exp, &pp);
    if fe_sq(&cand) != x_sq {
        return None;
    }

    // If sign bit set but x == 0, reject (RFC 8032 §5.2.3).
    if cand.is_zero() && sign == 1 {
        return None;
    }

    let x = if cand.bit(0) != (sign == 1) {
        fe_sub(&BigUint::zero(), &cand)
    } else {
        cand
    };

    Some(EdPoint::from_affine(x, y))
}

// ---------------------------------------------------------------------------
// Hashing helpers.
// ---------------------------------------------------------------------------

/// RFC 8032 §5.2 dom4 prefix: `"SigEd448" || phflag || |context| || context`.
/// We only implement the pure variant (phflag = 0x00).
fn dom4(context: &[u8]) -> Vec<u8> {
    assert!(context.len() <= 255, "Ed448 context >255 bytes");
    let mut out = Vec::with_capacity(8 + 2 + context.len());
    out.extend_from_slice(b"SigEd448");
    out.push(0x00); // phflag = 0 (pure Ed448)
    out.push(context.len() as u8);
    out.extend_from_slice(context);
    out
}

/// SHAKE256 → 114 bytes, the Ed448 hash output width.
fn shake_114(input: &[u8]) -> [u8; 114] {
    let v = shake256(input, 114);
    let mut out = [0u8; 114];
    out.copy_from_slice(&v);
    out
}

/// Clamp the 57-byte SHAKE256 prefix into a valid Ed448 scalar
/// per RFC 8032 §5.2.5:
///   s[0] &= 0xfc; s[55] |= 0x80; s[56] = 0x00.
fn clamp(s: &mut [u8; 57]) {
    s[0] &= 0xfc;
    s[55] |= 0x80;
    s[56] = 0x00;
}

/// Expand a 57-byte seed: returns `(clamped_scalar_bytes, prefix)`.
fn expand_seed(seed: &[u8; 57]) -> ([u8; 57], [u8; 57]) {
    let h = shake_114(seed);
    let mut s = [0u8; 57];
    let mut prefix = [0u8; 57];
    s.copy_from_slice(&h[..57]);
    prefix.copy_from_slice(&h[57..]);
    clamp(&mut s);
    (s, prefix)
}

/// Convert a `BigUint` to a 57-byte little-endian signature scalar.
fn bytes57_le(x: &BigUint) -> [u8; 57] {
    let mut out = [0u8; 57];
    let bytes = x.to_bytes_le();
    let n = bytes.len().min(57);
    out[..n].copy_from_slice(&bytes[..n]);
    out
}

// ---------------------------------------------------------------------------
// Public API.
// ---------------------------------------------------------------------------

/// Generate an Ed448 keypair from a 57-byte seed.  Returns
/// `(secret_key, public_key)` where the secret key is the seed
/// itself (per RFC 8032: the seed is the canonical private key)
/// and the public key is the 57-byte encoded `[s] · G`.
pub fn ed448_keygen(seed: &[u8; 57]) -> ([u8; 57], [u8; 57]) {
    let (s, _) = expand_seed(seed);
    let s_bn = BigUint::from_bytes_le(&s);
    let a = base_point().scalar_mul(&s_bn);
    (*seed, a.encode())
}

/// Sign `msg` with Ed448 (pure, phflag = 0).  `context` may be
/// empty or up to 255 bytes.
pub fn ed448_sign(sk: &[u8; 57], pk: &[u8; 57], context: &[u8], msg: &[u8]) -> [u8; 114] {
    let (s, prefix) = expand_seed(sk);
    let s_bn = BigUint::from_bytes_le(&s);
    let l = ed448_l();
    let dom = dom4(context);

    // r = SHAKE256(dom4 || prefix || msg) mod L  (114-byte digest).
    let mut r_input = Vec::with_capacity(dom.len() + 57 + msg.len());
    r_input.extend_from_slice(&dom);
    r_input.extend_from_slice(&prefix);
    r_input.extend_from_slice(msg);
    let r_hash = shake_114(&r_input);
    let r_bn = BigUint::from_bytes_le(&r_hash) % &l;

    // R = r · G.
    let r_pt = base_point().scalar_mul(&r_bn);
    let r_enc = r_pt.encode();

    // k = SHAKE256(dom4 || R || A || msg) mod L.
    let mut k_input = Vec::with_capacity(dom.len() + 57 + 57 + msg.len());
    k_input.extend_from_slice(&dom);
    k_input.extend_from_slice(&r_enc);
    k_input.extend_from_slice(pk);
    k_input.extend_from_slice(msg);
    let k_hash = shake_114(&k_input);
    let k_bn = BigUint::from_bytes_le(&k_hash) % &l;

    // S = (r + k · s) mod L.
    let s_sig = (r_bn + k_bn * s_bn) % &l;
    let s_bytes = bytes57_le(&s_sig);

    let mut sig = [0u8; 114];
    sig[..57].copy_from_slice(&r_enc);
    sig[57..].copy_from_slice(&s_bytes);
    sig
}

/// Verify an Ed448 signature.  Returns `true` iff valid.
pub fn ed448_verify(pk: &[u8; 57], context: &[u8], msg: &[u8], sig: &[u8; 114]) -> bool {
    let l = ed448_l();
    let r_bytes: [u8; 57] = sig[..57].try_into().unwrap();
    let s_bytes: [u8; 57] = sig[57..].try_into().unwrap();

    let s_bn = BigUint::from_bytes_le(&s_bytes);
    if s_bn >= l {
        return false;
    }

    let a_pt = match decode_point(pk) {
        Some(p) => p,
        None => return false,
    };
    let r_pt = match decode_point(&r_bytes) {
        Some(p) => p,
        None => return false,
    };

    let dom = dom4(context);
    let mut k_input = Vec::with_capacity(dom.len() + 57 + 57 + msg.len());
    k_input.extend_from_slice(&dom);
    k_input.extend_from_slice(&r_bytes);
    k_input.extend_from_slice(pk);
    k_input.extend_from_slice(msg);
    let k_hash = shake_114(&k_input);
    let k_bn = BigUint::from_bytes_le(&k_hash) % &l;

    // [S]·G ?= R + [k]·A.
    let lhs = base_point().scalar_mul(&s_bn);
    let rhs = r_pt.add(&a_pt.scalar_mul(&k_bn));

    // Compare in affine: cheaper and matches encoding semantics.
    let (lx, ly) = lhs.to_affine();
    let (rx, ry) = rhs.to_affine();
    lx == rx && ly == ry
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

    fn hex57(s: &str) -> [u8; 57] {
        let v = hex_decode(s);
        let mut out = [0u8; 57];
        out.copy_from_slice(&v);
        out
    }

    fn hex114(s: &str) -> [u8; 114] {
        let v = hex_decode(s);
        let mut out = [0u8; 114];
        out.copy_from_slice(&v);
        out
    }

    /// **RFC 8032 §7.4** — empty message, empty context.
    #[test]
    fn rfc8032_ed448_empty() {
        let sk = hex57(
            "6c82a562cb808d10d632be89c8513ebf6c929f34ddfa8c9f63c9960ef6e348a3\
             528c8a3fcc2f044e39a3fc5b94492f8f032e7549a20098f95b",
        );
        let expected_pk = hex57(
            "5fd7449b59b461fd2ce787ec616ad46a1da1342485a70e1f8a0ea75d80e96778\
             edf124769b46c7061bd6783df1e50f6cd1fa1abeafe8256180",
        );
        let (_, pk) = ed448_keygen(&sk);
        assert_eq!(pk, expected_pk, "Ed448 public key mismatch");

        let expected_sig = hex114(
            "533a37f6bbe457251f023c0d88f976ae2dfb504a843e34d2074fd823d41a591f\
             2b233f034f628281f2fd7a22ddd47d7828c59bd0a21bfd3980ff0d2028d4b18a\
             9df63e006c5d1c2d345b925d8dc00b4104852db99ac5c7cdda8530a113a0f4db\
             b61149f05a7363268c71d95808ff2e652600",
        );
        let sig = ed448_sign(&sk, &pk, b"", b"");
        assert_eq!(sig, expected_sig, "Ed448 signature mismatch");
        assert!(ed448_verify(&pk, b"", b"", &sig), "verify failed");
    }

    /// **RFC 8032 §7.4** — 1-octet message with 1-octet context.
    #[test]
    fn rfc8032_ed448_one_octet_with_context() {
        let sk = hex57(
            "c4eab05d357007c632f3dbb48489924d552b08fe0c353a0d4a1f00acda2c463a\
             fbea67c5e8d2877c5e3bc397a659949ef8021e954e0a12274e",
        );
        let expected_pk = hex57(
            "43ba28f430cdff456ae531545f7ecd0ac834a55d9358c0372bfa0c6c6798c086\
             6aea01eb00742802b8438ea4cb82169c235160627b4c3a9480",
        );
        let (_, pk) = ed448_keygen(&sk);
        assert_eq!(pk, expected_pk);

        let msg = hex_decode("03");
        let ctx = hex_decode("666f6f"); // "foo"
        let expected_sig = hex114(
            "d4f8f6131770dd46f40867d6fd5d5055de43541f8c5e35abbcd001b32a89f7d2\
             151f7647f11d8ca2ae279fb842d607217fce6e042f6815ea000c85741de5c8da\
             1144a6a1aba7f96de42505d7a7298524fda538fccbbb754f578c1cad10d54d0d\
             5428407e85dcbc98a49155c13764e66c3c00",
        );
        let sig = ed448_sign(&sk, &pk, &ctx, &msg);
        assert_eq!(sig, expected_sig, "Ed448 ctx signature mismatch");
        assert!(ed448_verify(&pk, &ctx, &msg, &sig));
    }

    #[test]
    fn ed448_roundtrip() {
        let seed = [0x5Au8; 57];
        let (sk, pk) = ed448_keygen(&seed);
        let msg = b"hello, ed448 world";
        let sig = ed448_sign(&sk, &pk, b"", msg);
        assert!(ed448_verify(&pk, b"", msg, &sig));
    }

    #[test]
    fn ed448_rejects_tampered_sig() {
        let seed = [0x42u8; 57];
        let (sk, pk) = ed448_keygen(&seed);
        let mut sig = ed448_sign(&sk, &pk, b"", b"original");
        sig[0] ^= 0x01;
        assert!(!ed448_verify(&pk, b"", b"original", &sig));
    }

    #[test]
    fn ed448_rejects_wrong_message() {
        let seed = [0x07u8; 57];
        let (sk, pk) = ed448_keygen(&seed);
        let sig = ed448_sign(&sk, &pk, b"", b"original");
        assert!(!ed448_verify(&pk, b"", b"different", &sig));
    }

    #[test]
    fn ed448_rejects_wrong_context() {
        let seed = [0x11u8; 57];
        let (sk, pk) = ed448_keygen(&seed);
        let sig = ed448_sign(&sk, &pk, b"ctx-A", b"msg");
        assert!(ed448_verify(&pk, b"ctx-A", b"msg", &sig));
        assert!(!ed448_verify(&pk, b"ctx-B", b"msg", &sig));
    }
}
