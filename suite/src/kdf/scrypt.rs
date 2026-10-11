//! **scrypt** — sequential memory-hard password-based KDF (Percival 2009, RFC 7914).
//!
//! Designed to make brute-force search expensive on custom hardware by
//! forcing each guess to allocate a large random-access buffer:
//! roughly `128 * n * r` bytes of working memory.  An attacker with an
//! ASIC must pay area-time proportional to memory size, not just gate
//! count — the property PBKDF2 lacks.
//!
//! # Algorithm (RFC 7914 §5–6)
//! 1. `B = PBKDF2-HMAC-SHA256(passwd, salt, 1, 128 * r * p)`
//! 2. For each of the `p` blocks of `128 * r` bytes: `B_i = ROMix(B_i, n)`
//! 3. `output = PBKDF2-HMAC-SHA256(passwd, B, 1, dk_len)`
//!
//! ROMix is the memory-hard core: fill an `n`-entry table by iterating
//! BlockMix (which itself is `2r` calls of Salsa20/8), then do `n` more
//! BlockMix steps whose lookup index depends on the current state — the
//! sequential-dependency that defeats trivial parallelisation.
//!
//! # Parameter tuning (RFC 7914 §2)
//! * `n` — CPU/memory cost; **must** be a power of two > 1.  Interactive
//!   logins: `n = 2^14` (16 MiB at r=8).  File-encryption: `n = 2^20`
//!   (1 GiB at r=8).
//! * `r` — block size factor.  `r = 8` is canonical; tunes the ratio of
//!   memory bandwidth to CPU work.
//! * `p` — parallelisation factor.  `p = 1` is fine; raise it to use
//!   more cores per derivation without raising memory.
//!
//! Salsa20/8 (4 double-rounds) is used here — the reduced-round variant
//! is sufficient because scrypt's security rests on the memory-hard
//! outer structure, not on Salsa20's full strength.

use crate::kdf::pbkdf2::pbkdf2_hmac_sha256;

// ── Salsa20/8 core (8 rounds = 4 double rounds) ──────────────────────────────

#[inline]
fn qr(s: &mut [u32; 16], a: usize, b: usize, c: usize, d: usize) {
    s[b] ^= s[a].wrapping_add(s[d]).rotate_left(7);
    s[c] ^= s[b].wrapping_add(s[a]).rotate_left(9);
    s[d] ^= s[c].wrapping_add(s[b]).rotate_left(13);
    s[a] ^= s[d].wrapping_add(s[c]).rotate_left(18);
}

/// Salsa20/8: 64-byte input → 64-byte output, with feedforward of the input.
fn salsa20_8_core(input: &[u8; 64]) -> [u8; 64] {
    let mut x = [0u32; 16];
    for i in 0..16 {
        x[i] = u32::from_le_bytes(input[i * 4..i * 4 + 4].try_into().unwrap());
    }
    let initial = x;
    for _ in 0..4 {
        qr(&mut x, 0, 4, 8, 12);
        qr(&mut x, 5, 9, 13, 1);
        qr(&mut x, 10, 14, 2, 6);
        qr(&mut x, 15, 3, 7, 11);
        qr(&mut x, 0, 1, 2, 3);
        qr(&mut x, 5, 6, 7, 4);
        qr(&mut x, 10, 11, 8, 9);
        qr(&mut x, 15, 12, 13, 14);
    }
    let mut out = [0u8; 64];
    for i in 0..16 {
        let w = x[i].wrapping_add(initial[i]);
        out[i * 4..i * 4 + 4].copy_from_slice(&w.to_le_bytes());
    }
    out
}

// ── BlockMix and ROMix ───────────────────────────────────────────────────────

/// BlockMix on `b` (length `128 * r`): chain Salsa20/8 across `2r`
/// 64-byte chunks, then permute the output so even-indexed Y blocks
/// come first.
fn block_mix(b: &mut [u8], r: u32) {
    let two_r = (2 * r) as usize;
    let mut x = [0u8; 64];
    x.copy_from_slice(&b[(two_r - 1) * 64..two_r * 64]);

    let mut y = vec![0u8; b.len()];
    for i in 0..two_r {
        for j in 0..64 {
            x[j] ^= b[i * 64 + j];
        }
        x = salsa20_8_core(&x);
        y[i * 64..i * 64 + 64].copy_from_slice(&x);
    }

    // Output order: Y[0], Y[2], ..., Y[2r-2], Y[1], Y[3], ..., Y[2r-1]
    for i in 0..(r as usize) {
        b[i * 64..i * 64 + 64].copy_from_slice(&y[(2 * i) * 64..(2 * i) * 64 + 64]);
        b[(r as usize + i) * 64..(r as usize + i) * 64 + 64]
            .copy_from_slice(&y[(2 * i + 1) * 64..(2 * i + 1) * 64 + 64]);
    }
}

/// Integerify: interpret the last 64 bytes of `b` as a little-endian
/// integer mod `n`.  Since `n` is a power of two we just need the low
/// `log2(n)` bits of the first u64 of that final chunk.
#[inline]
fn integerify(b: &[u8], r: u32, n_mask: u64) -> usize {
    let off = (2 * r as usize - 1) * 64;
    let lo = u64::from_le_bytes(b[off..off + 8].try_into().unwrap());
    (lo & n_mask) as usize
}

/// ROMix: the memory-hard core.  Builds an `n`-entry table from
/// repeated BlockMix, then does `n` more BlockMix steps whose lookups
/// depend on the current state.
fn ro_mix(b: &mut [u8], n: u32, r: u32) {
    let block_len = b.len(); // 128 * r
    let n_us = n as usize;
    let n_mask = (n as u64) - 1;

    let mut v = vec![0u8; n_us * block_len];
    for i in 0..n_us {
        v[i * block_len..(i + 1) * block_len].copy_from_slice(b);
        block_mix(b, r);
    }
    for _ in 0..n_us {
        let j = integerify(b, r, n_mask);
        for k in 0..block_len {
            b[k] ^= v[j * block_len + k];
        }
        block_mix(b, r);
    }
}

// ── Public API ───────────────────────────────────────────────────────────────

/// Derive `dk_len` bytes from `passwd` and `salt` using scrypt with
/// cost parameters `n`, `r`, `p`.
///
/// * `n` — CPU/memory cost; must be a power of two and `> 1`.
/// * `r` — block size factor.
/// * `p` — parallelisation factor.
///
/// Memory footprint is roughly `128 * n * r * p` bytes (the per-block
/// `V` table dominates).
pub fn scrypt(
    passwd: &[u8],
    salt: &[u8],
    n: u32,
    r: u32,
    p: u32,
    dk_len: usize,
) -> Result<Vec<u8>, &'static str> {
    if r == 0 || p == 0 {
        return Err("scrypt: r and p must be nonzero");
    }
    if n < 2 || (n & (n - 1)) != 0 {
        return Err("scrypt: n must be a power of two > 1");
    }
    // n < 2^(128 * r / 8) = 2^(16 * r).  For r >= 2 this is vacuous on u32.
    if r == 1 && n >= 1 << 16 {
        return Err("scrypt: n too large for given r");
    }
    // r * p < 2^30
    if (r as u64)
        .checked_mul(p as u64)
        .ok_or("scrypt: r*p overflow")?
        >= 1 << 30
    {
        return Err("scrypt: r * p must be < 2^30");
    }
    // dk_len <= (2^32 - 1) * 32
    if dk_len > ((1u64 << 32) - 1) as usize * 32 {
        return Err("scrypt: dk_len too large");
    }

    let block_len = 128usize
        .checked_mul(r as usize)
        .ok_or("scrypt: r too large")?;
    let total = block_len
        .checked_mul(p as usize)
        .ok_or("scrypt: p*r too large")?;

    let mut b = pbkdf2_hmac_sha256(passwd, salt, 1, total);
    for i in 0..(p as usize) {
        let slice = &mut b[i * block_len..(i + 1) * block_len];
        ro_mix(slice, n, r);
    }
    Ok(pbkdf2_hmac_sha256(passwd, &b, 1, dk_len))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn h(s: &str) -> Vec<u8> {
        hex::decode(s.split_whitespace().collect::<String>()).unwrap()
    }

    // ── RFC 7914 §11 test vectors ────────────────────────────────────────────

    #[test]
    fn scrypt_rfc7914_tv1() {
        // passwd="", salt="", n=16, r=1, p=1, dk_len=64
        let dk = scrypt(b"", b"", 16, 1, 1, 64).unwrap();
        assert_eq!(
            dk,
            h("77 d6 57 62 38 65 7b 20 3b 19 ca 42 c1 8a 04 97
               f1 6b 48 44 e3 07 4a e8 df df fa 3f ed e2 14 42
               fc d0 06 9d ed 09 48 f8 32 6a 75 3a 0f c8 1f 17
               e8 d3 e0 fb 2e 0d 36 28 cf 35 e2 0c 38 d1 89 06"),
        );
    }

    #[test]
    fn scrypt_rfc7914_tv2() {
        // passwd="password", salt="NaCl", n=1024, r=8, p=16, dk_len=64
        let dk = scrypt(b"password", b"NaCl", 1024, 8, 16, 64).unwrap();
        assert_eq!(
            dk,
            h("fd ba be 1c 9d 34 72 00 78 56 e7 19 0d 01 e9 fe
               7c 6a d7 cb c8 23 78 30 e7 73 76 63 4b 37 31 62
               2e af 30 d9 2e 22 a3 88 6f f1 09 27 9d 98 30 da
               c7 27 af b9 4a 83 ee 6d 83 60 cb df a2 cc 06 40"),
        );
    }

    #[test]
    fn scrypt_rejects_non_power_of_two_n() {
        assert!(scrypt(b"p", b"s", 3, 1, 1, 32).is_err());
        assert!(scrypt(b"p", b"s", 1, 1, 1, 32).is_err());
        assert!(scrypt(b"p", b"s", 0, 1, 1, 32).is_err());
    }

    #[test]
    fn scrypt_rejects_zero_r_or_p() {
        assert!(scrypt(b"p", b"s", 16, 0, 1, 32).is_err());
        assert!(scrypt(b"p", b"s", 16, 1, 0, 32).is_err());
    }

    #[test]
    fn scrypt_rejects_rp_too_large() {
        // r * p must be < 2^30
        assert!(scrypt(b"p", b"s", 16, 1 << 15, 1 << 15, 32).is_err());
    }

    #[test]
    fn scrypt_deterministic() {
        let a = scrypt(b"secret", b"pepper", 16, 1, 1, 32).unwrap();
        let b = scrypt(b"secret", b"pepper", 16, 1, 1, 32).unwrap();
        assert_eq!(a, b);
    }

    #[test]
    fn scrypt_different_passwords() {
        let a = scrypt(b"password1", b"salt", 16, 1, 1, 32).unwrap();
        let b = scrypt(b"password2", b"salt", 16, 1, 1, 32).unwrap();
        assert_ne!(a, b);
    }
}
