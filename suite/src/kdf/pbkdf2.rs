//! PBKDF2 — Password-Based Key Derivation Function 2 (RFC 8018 / PKCS#5 v2.1).
//!
//! # Algorithm
//! DK = T₁ || T₂ || … || Tᵢ   (concatenated to the desired length)
//!
//! Tᵢ = F(Password, Salt, c, i)
//! F(P, S, c, i) = U₁ ⊕ U₂ ⊕ … ⊕ Uᵢ
//!
//! U₁ = HMAC(P, S || INT(i))
//! Uⱼ = HMAC(P, Uⱼ₋₁)     for j = 2 … c
//!
//! Using HMAC-SHA256 as the underlying PRF (hLen = 32 bytes).
//! For password hashing, use c ≥ 600,000 iterations (NIST SP 800-132).

use crate::kdf::hkdf::hmac_sha256;

const H_LEN: usize = 32; // HMAC-SHA256 output length

/// Derive `dk_len` bytes from `password` and `salt` using `iterations` rounds.
///
/// # Parameters
/// * `password`   — the secret (e.g., a user's password as UTF-8 bytes)
/// * `salt`       — a random per-credential salt (≥ 16 bytes recommended)
/// * `iterations` — work factor; ≥ 600_000 recommended for password storage
/// * `dk_len`     — desired output length in bytes
pub fn pbkdf2_hmac_sha256(password: &[u8], salt: &[u8], iterations: u32, dk_len: usize) -> Vec<u8> {
    pbkdf2_hmac_sha256_checked(password, salt, iterations, dk_len)
        .expect("invalid PBKDF2 parameters")
}

/// Checked PBKDF2-HMAC-SHA256.
pub fn pbkdf2_hmac_sha256_checked(
    password: &[u8],
    salt: &[u8],
    iterations: u32,
    dk_len: usize,
) -> Result<Vec<u8>, &'static str> {
    if iterations == 0 {
        return Err("PBKDF2 iterations must be nonzero");
    }
    let block_count = dk_len
        .checked_add(H_LEN - 1)
        .ok_or("PBKDF2 output too long")?
        / H_LEN;
    if block_count > u32::MAX as usize {
        return Err("PBKDF2 output too long");
    }
    let mut dk = Vec::with_capacity(block_count * H_LEN);

    for i in 1u32..=block_count as u32 {
        // U₁ = HMAC(password, salt || INT32_BE(i))
        let mut salt_i = salt.to_vec();
        salt_i.extend_from_slice(&i.to_be_bytes());
        let mut u = hmac_sha256(password, &salt_i);
        let mut t = u;

        // U₂ … Uc
        for _ in 1..iterations {
            u = hmac_sha256(password, &u);
            for (a, b) in t.iter_mut().zip(u.iter()) {
                *a ^= b;
            }
        }
        dk.extend_from_slice(&t);
    }

    dk.truncate(dk_len);
    Ok(dk)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn h(s: &str) -> Vec<u8> {
        hex::decode(s).unwrap()
    }

    // ── PBKDF2-HMAC-SHA256 KATs (RFC 7914 §11) ───────────────────────────────

    #[test]
    fn pbkdf2_rfc7914_tc1() {
        // RFC 7914 §11 — PBKDF2-HMAC-SHA-256(passwd, salt, 1, 64)
        let dk = pbkdf2_hmac_sha256(b"passwd", b"salt", 1, 64);
        assert_eq!(
            dk,
            h(
                "55ac046e56e3089fec1691c22544b605f94185216dde0465e68b9d57c20dacbc\
               49ca9cccf179b645991664b39d77ef317c71b845b1e30bd509112041d3a19783"
            ),
        );
    }

    #[test]
    fn pbkdf2_simple_c1_32() {
        // Cross-checked with Python cryptography
        let dk = pbkdf2_hmac_sha256(b"password", b"salt", 1, 32);
        assert_eq!(
            dk,
            h("120fb6cffcf8b32c43e7225256c4f837a86548c92ccc35480805987cb70be17b"),
        );
    }

    #[test]
    fn pbkdf2_c4096_32() {
        let dk = pbkdf2_hmac_sha256(b"password", b"salt", 4096, 32);
        assert_eq!(
            dk,
            h("c5e478d59288c841aa530db6845c4c8d962893a001ce4e11a4963873aa98134a"),
        );
    }

    #[test]
    fn pbkdf2_deterministic() {
        let dk1 = pbkdf2_hmac_sha256(b"secret", b"pepper", 100, 32);
        let dk2 = pbkdf2_hmac_sha256(b"secret", b"pepper", 100, 32);
        assert_eq!(dk1, dk2);
    }

    #[test]
    fn pbkdf2_different_passwords() {
        let dk1 = pbkdf2_hmac_sha256(b"password1", b"salt", 100, 32);
        let dk2 = pbkdf2_hmac_sha256(b"password2", b"salt", 100, 32);
        assert_ne!(dk1, dk2);
    }

    #[test]
    fn pbkdf2_different_salts() {
        let dk1 = pbkdf2_hmac_sha256(b"password", b"salt-a", 100, 32);
        let dk2 = pbkdf2_hmac_sha256(b"password", b"salt-b", 100, 32);
        assert_ne!(dk1, dk2);
    }

    #[test]
    fn pbkdf2_multi_block() {
        // dkLen > hLen exercises the block concatenation logic.
        let dk = pbkdf2_hmac_sha256(b"passwd", b"salt", 1, 64);
        assert_eq!(dk.len(), 64);
        // Truncating the multi-block output must equal a single-block call of the same length.
        let dk32 = pbkdf2_hmac_sha256(b"passwd", b"salt", 1, 32);
        assert_eq!(&dk[..32], &dk32[..]);
    }

    #[test]
    fn pbkdf2_rejects_zero_iterations_and_block_overflow() {
        assert!(pbkdf2_hmac_sha256_checked(b"p", b"s", 0, 32).is_err());
        let too_long = (u32::MAX as usize + 1) * H_LEN;
        assert!(pbkdf2_hmac_sha256_checked(b"p", b"s", 1, too_long).is_err());
    }
}
