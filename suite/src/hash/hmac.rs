//! HMAC — Keyed-Hash Message Authentication Code (RFC 2104, FIPS 198-1).
//!
//! Generic over any Merkle-Damgård (or sponge) hash with a fixed block size
//! and output size.  HMAC works by:
//!
//! ```text
//!   HMAC(K, m) = H( (K' ⊕ opad) || H( (K' ⊕ ipad) || m ) )
//! ```
//!
//! where `K'` is `K` zero-padded to `block_size` (hashed first if `|K| >
//! block_size`).  `ipad = 0x36…36`, `opad = 0x5c…5c`.  The two-layer
//! structure is what immunises HMAC against the length-extension attacks
//! that plague raw `H(K || m)`.
//!
//! # Security notes
//! - HMAC-SHA-1 is **still secure as a MAC** despite SHA-1 being broken
//!   for collision resistance.  RFC 6151 / NIST SP 800-131A both permit
//!   HMAC-SHA-1 indefinitely; deprecate only for new designs.
//! - Tag comparison MUST be constant-time.  See [`hmac_verify_ct`].
//! - HMAC-MD5 is intentionally not exposed — too easy to misuse, and the
//!   surrounding ecosystem (`md5.rs`) is already a "study target".

use super::blake2b::blake2b_keyed;
use super::sha1::sha1;
use super::sha256::sha256;
use super::sha512::{sha384, sha512};

// ── Generic core ─────────────────────────────────────────────────────────────

/// Compute HMAC over any hash function presented as a closure plus
/// (block_size, output_size) constants.  Returns a `Vec<u8>` of length
/// `output_size`.
///
/// Most callers want one of the [`hmac_sha1`], [`hmac_sha256`],
/// [`hmac_sha384`], [`hmac_sha512`] wrappers below; this entry point is
/// for non-standard inner hashes (e.g. Streebog, SM3) that need HMAC too.
pub fn hmac_with<F>(block_size: usize, hash: F, key: &[u8], data: &[u8]) -> Vec<u8>
where
    F: Fn(&[u8]) -> Vec<u8>,
{
    // Step 1: normalise the key to exactly `block_size` bytes.
    let mut k = vec![0u8; block_size];
    if key.len() > block_size {
        let hk = hash(key);
        k[..hk.len()].copy_from_slice(&hk);
    } else {
        k[..key.len()].copy_from_slice(key);
    }

    // Step 2: inner hash H((K ⊕ ipad) || data).
    let mut inner_input = Vec::with_capacity(block_size + data.len());
    inner_input.extend(k.iter().map(|b| b ^ 0x36));
    inner_input.extend_from_slice(data);
    let inner = hash(&inner_input);

    // Step 3: outer hash H((K ⊕ opad) || inner).
    let mut outer_input = Vec::with_capacity(block_size + inner.len());
    outer_input.extend(k.iter().map(|b| b ^ 0x5c));
    outer_input.extend_from_slice(&inner);
    hash(&outer_input)
}

/// Constant-time verification: `true` iff `HMAC(key, data) == tag`.
///
/// Generic over the inner hash via the same `(block_size, hash)` interface
/// as [`hmac_with`].  Always prefer this over `hmac_with(...) == tag` when
/// the tag is supplied by an untrusted party.
pub fn hmac_verify_ct<F>(block_size: usize, hash: F, key: &[u8], data: &[u8], tag: &[u8]) -> bool
where
    F: Fn(&[u8]) -> Vec<u8>,
{
    use subtle::ConstantTimeEq;
    let computed = hmac_with(block_size, hash, key, data);
    if computed.len() != tag.len() {
        return false;
    }
    computed.ct_eq(tag).unwrap_u8() == 1
}

// ── Convenience wrappers for the standard inner hashes ───────────────────────

/// HMAC-SHA-1.  Block 64, output 20.
pub fn hmac_sha1(key: &[u8], data: &[u8]) -> [u8; 20] {
    let v = hmac_with(64, |b| sha1(b).to_vec(), key, data);
    v.try_into().unwrap()
}

/// HMAC-SHA-256.  Block 64, output 32.
pub fn hmac_sha256(key: &[u8], data: &[u8]) -> [u8; 32] {
    let v = hmac_with(64, |b| sha256(b).to_vec(), key, data);
    v.try_into().unwrap()
}

/// HMAC-SHA-384.  Block 128, output 48.
pub fn hmac_sha384(key: &[u8], data: &[u8]) -> [u8; 48] {
    let v = hmac_with(128, |b| sha384(b).to_vec(), key, data);
    v.try_into().unwrap()
}

/// HMAC-SHA-512.  Block 128, output 64.
pub fn hmac_sha512(key: &[u8], data: &[u8]) -> [u8; 64] {
    let v = hmac_with(128, |b| sha512(b).to_vec(), key, data);
    v.try_into().unwrap()
}

/// "HMAC"-BLAKE2b — but in practice this is **keyed BLAKE2b**, not the
/// generic HMAC construction.  BLAKE2 has its own built-in key handling
/// (RFC 7693 §2.5) that is faster, simpler, and just as secure: there is
/// no length-extension on BLAKE2 to defend against.  Exposed here for
/// API parity with the SHA-family HMAC wrappers.
///
/// Returns 64 bytes (BLAKE2b-512 output).
pub fn hmac_blake2b(key: &[u8], data: &[u8]) -> Vec<u8> {
    blake2b_keyed(key, data, 64)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn h(s: &str) -> Vec<u8> {
        hex::decode(s.chars().filter(|c| !c.is_whitespace()).collect::<String>()).unwrap()
    }

    // ── HMAC-SHA-1 (RFC 2202 §3) ─────────────────────────────────────────────

    #[test]
    fn hmac_sha1_rfc2202_tc1() {
        // key=0x0b * 20, msg="Hi There"
        let mac = hmac_sha1(&[0x0b; 20], b"Hi There");
        assert_eq!(
            &mac,
            h("b617318655057264e28bc0b6fb378c8ef146be00").as_slice(),
        );
    }

    #[test]
    fn hmac_sha1_rfc2202_tc2() {
        // key="Jefe", msg="what do ya want for nothing?"
        let mac = hmac_sha1(b"Jefe", b"what do ya want for nothing?");
        assert_eq!(
            &mac,
            h("effcdf6ae5eb2fa2d27416d5f184df9c259a7c79").as_slice(),
        );
    }

    #[test]
    fn hmac_sha1_rfc2202_tc4() {
        // key=0x01..0x19, msg=0xcd * 50
        let key: Vec<u8> = (1u8..=25).collect();
        let mac = hmac_sha1(&key, &[0xcd; 50]);
        assert_eq!(
            &mac,
            h("4c9007f4026250c6bc8414f9bf50c86c2d7235da").as_slice(),
        );
    }

    #[test]
    fn hmac_sha1_long_key() {
        // RFC 2202 TC6: key=0xaa * 80 — longer than block_size, gets hashed
        let mac = hmac_sha1(
            &[0xaa; 80],
            b"Test Using Larger Than Block-Size Key - Hash Key First",
        );
        assert_eq!(
            &mac,
            h("aa4ae5e15272d00e95705637ce8a3b55ed402112").as_slice(),
        );
    }

    // ── HMAC-SHA-256 (RFC 4231 §4) ───────────────────────────────────────────

    #[test]
    fn hmac_sha256_rfc4231_tc1() {
        let mac = hmac_sha256(&[0x0b; 20], b"Hi There");
        assert_eq!(
            &mac,
            h("b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7").as_slice(),
        );
    }

    #[test]
    fn hmac_sha256_rfc4231_tc2() {
        let mac = hmac_sha256(b"Jefe", b"what do ya want for nothing?");
        assert_eq!(
            &mac,
            h("5bdcc146bf60754e6a042426089575c75a003f089d2739839dec58b964ec3843").as_slice(),
        );
    }

    #[test]
    fn hmac_sha256_rfc4231_tc6_long_key() {
        // 131-byte key (> 64-byte block) gets hashed first.
        let mac = hmac_sha256(
            &[0xaa; 131],
            b"Test Using Larger Than Block-Size Key - Hash Key First",
        );
        assert_eq!(
            &mac,
            h("60e431591ee0b67f0d8a26aacbf5b77f8e0bc6213728c5140546040f0ee37f54").as_slice(),
        );
    }

    // ── HMAC-SHA-384 (RFC 4231 §4) ───────────────────────────────────────────

    #[test]
    fn hmac_sha384_rfc4231_tc1() {
        let mac = hmac_sha384(&[0x0b; 20], b"Hi There");
        assert_eq!(
            &mac,
            h(
                "afd03944d84895626b0825f4ab46907f15f9dadbe4101ec682aa034c7cebc59c\
               faea9ea9076ede7f4af152e8b2fa9cb6"
            )
            .as_slice(),
        );
    }

    #[test]
    fn hmac_sha384_rfc4231_tc2() {
        let mac = hmac_sha384(b"Jefe", b"what do ya want for nothing?");
        assert_eq!(
            &mac,
            h(
                "af45d2e376484031617f78d2b58a6b1b9c7ef464f5a01b47e42ec3736322445e\
               8e2240ca5e69e2c78b3239ecfab21649"
            )
            .as_slice(),
        );
    }

    // ── HMAC-SHA-512 (RFC 4231 §4) ───────────────────────────────────────────

    #[test]
    fn hmac_sha512_rfc4231_tc1() {
        let mac = hmac_sha512(&[0x0b; 20], b"Hi There");
        assert_eq!(
            &mac,
            h(
                "87aa7cdea5ef619d4ff0b4241a1d6cb02379f4e2ce4ec2787ad0b30545e17cde\
               daa833b7d6b8a702038b274eaea3f4e4be9d914eeb61f1702e696c203a126854"
            )
            .as_slice(),
        );
    }

    #[test]
    fn hmac_sha512_rfc4231_tc2() {
        let mac = hmac_sha512(b"Jefe", b"what do ya want for nothing?");
        assert_eq!(
            &mac,
            h(
                "164b7a7bfcf819e2e395fbe73b56e0a387bd64222e831fd610270cd7ea250554\
               9758bf75c05a994a6d034f65f8f0e6fdcaeab1a34d4a6b4b636e070a38bce737"
            )
            .as_slice(),
        );
    }

    // ── Verification helper ─────────────────────────────────────────────────

    #[test]
    fn hmac_verify_ct_accepts_correct_tag() {
        let key = b"secret";
        let data = b"message";
        let tag = hmac_sha256(key, data);
        assert!(hmac_verify_ct(64, |b| sha256(b).to_vec(), key, data, &tag));
    }

    #[test]
    fn hmac_verify_ct_rejects_wrong_tag() {
        let key = b"secret";
        let data = b"message";
        let mut tag = hmac_sha256(key, data);
        tag[0] ^= 1;
        assert!(!hmac_verify_ct(64, |b| sha256(b).to_vec(), key, data, &tag));
    }

    #[test]
    fn hmac_verify_ct_rejects_truncated_tag() {
        let key = b"secret";
        let data = b"message";
        let tag = hmac_sha256(key, data);
        assert!(!hmac_verify_ct(
            64,
            |b| sha256(b).to_vec(),
            key,
            data,
            &tag[..16]
        ));
    }
}
