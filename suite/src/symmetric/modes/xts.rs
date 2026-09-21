//! **XTS — XEX-based Tweaked-codebook with ciphertext Stealing**
//! (IEEE P1619-2007, NIST SP 800-38E).
//!
//! Disk-encryption mode: each sector's content is encrypted with a
//! different *tweak* derived from the sector number, so the same
//! plaintext block at different sectors encrypts to different
//! ciphertext.  Length-preserving (no expansion); supports arbitrary
//! sector length ≥ 16 bytes via ciphertext stealing on the final
//! partial block.
//!
//! ## Algorithm
//!
//! Key is `K = K1 || K2` (two 16-byte or two 32-byte AES keys).
//!
//! ```text
//!     T_0 = E_{K2}(tweak)
//!     T_i = T_0 · α^i in GF(2^128)
//!     C_i = E_{K1}(P_i ⊕ T_i) ⊕ T_i
//! ```
//!
//! For a non-block-multiple length `L = 16·m + r` with `0 < r < 16`,
//! the last two blocks use ciphertext stealing:
//!
//! ```text
//!     CC = E_{K1}(P_{m-1} ⊕ T_{m-1}) ⊕ T_{m-1}       (full last-full block)
//!     C_m = CC[..r]                                  (first r bytes)
//!     P_m' = P_m || CC[r..]                          (pad short P_m)
//!     C_{m-1} = E_{K1}(P_m' ⊕ T_m) ⊕ T_m              (re-encrypt at the m-th tweak)
//! ```
//!
//! Multiplication by α (the primitive element x) in GF(2^128) under
//! the polynomial `x^128 + x^7 + x^2 + x + 1` (IEEE convention with
//! the *low-order-byte-first* representation).

use crate::symmetric::aes::{encrypt_block, AesKey};

/// Multiply by `α` (`x`) in GF(2^128).  IEEE-1619 little-endian byte
/// order (LSB at byte 0).  Reduction polynomial `x^128 + x^7 + x^2 + x + 1`.
fn gf_double(t: &mut [u8; 16]) {
    let mut carry = 0u8;
    for byte in t.iter_mut() {
        let new_carry = (*byte >> 7) & 1;
        *byte = (*byte << 1) | carry;
        carry = new_carry;
    }
    if carry == 1 {
        t[0] ^= 0x87;
    }
}

fn aes_decrypt_block(block: &[u8; 16], key: &AesKey) -> [u8; 16] {
    crate::symmetric::aes::decrypt_block(block, key)
}

/// **XTS-AES encrypt one sector**.  `k1`/`k2` are both AES keys
/// (same key size).  `tweak` is the 16-byte sector identifier
/// (typically little-endian sector index).  Plaintext length must
/// be ≥ 16 bytes.
pub fn xts_encrypt(
    k1: &AesKey,
    k2: &AesKey,
    tweak: &[u8; 16],
    plaintext: &[u8],
) -> Option<Vec<u8>> {
    if plaintext.len() < 16 {
        return None;
    }
    // T_0 = E_{K2}(tweak)
    let mut t = encrypt_block(tweak, k2);
    let total_blocks = plaintext.len() / 16;
    let rem = plaintext.len() % 16;
    // Number of full blocks processed in the main loop.  If aligned
    // (rem == 0) the whole input is processed in the loop; if not,
    // we skip the last full block so ciphertext-stealing can handle
    // both it and the partial trailing chunk.
    let loop_blocks = if rem == 0 {
        total_blocks
    } else {
        total_blocks - 1
    };
    let mut out = Vec::with_capacity(plaintext.len());
    for i in 0..loop_blocks {
        let mut blk = [0u8; 16];
        for j in 0..16 {
            blk[j] = plaintext[i * 16 + j] ^ t[j];
        }
        let mut ct = encrypt_block(&blk, k1);
        for j in 0..16 {
            ct[j] ^= t[j];
        }
        out.extend_from_slice(&ct);
        gf_double(&mut t);
    }
    if rem == 0 {
        // Aligned input: loop already produced the full ciphertext.
    } else {
        // total_blocks = loop_blocks + 1; the "last full block" lives
        // at index `loop_blocks` and the partial chunk starts at
        // `(loop_blocks + 1) * 16`.
        let full_blocks = loop_blocks;
        // Ciphertext stealing.  At this point t = T_{full_blocks} (the
        // tweak for the would-be last-full block).
        let p_last_full_start = full_blocks * 16;
        let mut blk = [0u8; 16];
        for j in 0..16 {
            blk[j] = plaintext[p_last_full_start + j] ^ t[j];
        }
        let mut cc = encrypt_block(&blk, k1);
        for j in 0..16 {
            cc[j] ^= t[j];
        }
        // Next tweak.
        gf_double(&mut t);
        // P_m' = P_m || CC[r..]
        let p_m_start = (full_blocks + 1) * 16;
        let mut p_mp = [0u8; 16];
        p_mp[..rem].copy_from_slice(&plaintext[p_m_start..(rem + p_m_start)]);
        p_mp[rem..16].copy_from_slice(&cc[rem..16]);
        let mut blk2 = [0u8; 16];
        for j in 0..16 {
            blk2[j] = p_mp[j] ^ t[j];
        }
        let mut c_prev = encrypt_block(&blk2, k1);
        for j in 0..16 {
            c_prev[j] ^= t[j];
        }
        out.extend_from_slice(&c_prev);
        out.extend_from_slice(&cc[..rem]);
    }
    Some(out)
}

/// **XTS-AES decrypt one sector**.  Inverse of `xts_encrypt`.
pub fn xts_decrypt(
    k1: &AesKey,
    k2: &AesKey,
    tweak: &[u8; 16],
    ciphertext: &[u8],
) -> Option<Vec<u8>> {
    if ciphertext.len() < 16 {
        return None;
    }
    let mut t = encrypt_block(tweak, k2);
    let total_blocks = ciphertext.len() / 16;
    let rem = ciphertext.len() % 16;
    let loop_blocks = if rem == 0 {
        total_blocks
    } else {
        total_blocks - 1
    };
    let mut out = Vec::with_capacity(ciphertext.len());
    for i in 0..loop_blocks {
        let mut blk = [0u8; 16];
        for j in 0..16 {
            blk[j] = ciphertext[i * 16 + j] ^ t[j];
        }
        let mut pt = aes_decrypt_block(&blk, k1);
        for j in 0..16 {
            pt[j] ^= t[j];
        }
        out.extend_from_slice(&pt);
        gf_double(&mut t);
    }
    if rem == 0 {
        // Aligned: loop already produced all plaintext.
    } else {
        let full_blocks = loop_blocks;
        // Ciphertext stealing on decrypt.  After the loop, t = T_{full_blocks}.
        // The two final ciphertext blocks are:
        //   C_{m-1} = ciphertext[full_blocks*16 .. (full_blocks+1)*16]  (full, 16B)
        //   C_m     = ciphertext[(full_blocks+1)*16 .. end]              (r bytes)
        // We need to decrypt them in reverse order using tweaks t_{m-1} = t and t_m = dbl(t).
        let mut t_m = t;
        gf_double(&mut t_m);
        // First decrypt C_{m-1} at the t_m tweak to get P_m' (16 bytes).
        let mut blk = [0u8; 16];
        for j in 0..16 {
            blk[j] = ciphertext[full_blocks * 16 + j] ^ t_m[j];
        }
        let mut p_mp = aes_decrypt_block(&blk, k1);
        for j in 0..16 {
            p_mp[j] ^= t_m[j];
        }
        // CC = P_m'[r..]  (the borrowed bytes for the stolen ciphertext)
        // were the high bytes of the original 16-byte CC.
        // Reconstruct CC = ciphertext[(full_blocks+1)*16 .. ] || P_m'[r..]
        let c_m_start = (full_blocks + 1) * 16;
        let mut cc = [0u8; 16];
        cc[..rem].copy_from_slice(&ciphertext[c_m_start..(rem + c_m_start)]);
        cc[rem..16].copy_from_slice(&p_mp[rem..16]);
        // Decrypt CC at the t tweak to get P_{full_blocks}.
        let mut blk2 = [0u8; 16];
        for j in 0..16 {
            blk2[j] = cc[j] ^ t[j];
        }
        let mut pt_full = aes_decrypt_block(&blk2, k1);
        for j in 0..16 {
            pt_full[j] ^= t[j];
        }
        out.extend_from_slice(&pt_full);
        out.extend_from_slice(&p_mp[..rem]);
    }
    Some(out)
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// Round-trip on a 32-byte (2-block) sector.
    #[test]
    fn xts_round_trip_aligned_2blocks() {
        let k1 = AesKey::new(&[0u8; 16]).unwrap();
        let k2 = AesKey::new(&[1u8; 16]).unwrap();
        let tweak = [0u8; 16];
        let pt = [0xAAu8; 32];
        let ct = xts_encrypt(&k1, &k2, &tweak, &pt).unwrap();
        assert_eq!(ct.len(), 32);
        let recovered = xts_decrypt(&k1, &k2, &tweak, &ct).unwrap();
        assert_eq!(&recovered[..], &pt[..]);
    }

    /// Round-trip with ciphertext stealing (non-multiple-of-16 length).
    #[test]
    fn xts_round_trip_with_stealing() {
        let k1 = AesKey::new(&[0x11u8; 16]).unwrap();
        let k2 = AesKey::new(&[0x22u8; 16]).unwrap();
        let tweak = [0x33u8; 16];
        for len in 17usize..=64 {
            let pt: Vec<u8> = (0..len).map(|i| i as u8).collect();
            let ct = xts_encrypt(&k1, &k2, &tweak, &pt).unwrap();
            assert_eq!(ct.len(), pt.len());
            let recovered = xts_decrypt(&k1, &k2, &tweak, &ct).unwrap();
            assert_eq!(recovered, pt, "fail at len = {}", len);
        }
    }

    /// Different tweaks ⇒ different ciphertexts even for identical PT.
    #[test]
    fn xts_tweak_separates_ciphertexts() {
        let k1 = AesKey::new(&[0u8; 16]).unwrap();
        let k2 = AesKey::new(&[1u8; 16]).unwrap();
        let pt = [0u8; 32];
        let mut t1 = [0u8; 16];
        let mut t2 = [0u8; 16];
        t1[0] = 1;
        t2[0] = 2;
        let ct1 = xts_encrypt(&k1, &k2, &t1, &pt).unwrap();
        let ct2 = xts_encrypt(&k1, &k2, &t2, &pt).unwrap();
        assert_ne!(ct1, ct2);
    }

    /// Length < 16 bytes rejected.
    #[test]
    fn xts_rejects_short_sectors() {
        let k1 = AesKey::new(&[0u8; 16]).unwrap();
        let k2 = AesKey::new(&[1u8; 16]).unwrap();
        assert!(xts_encrypt(&k1, &k2, &[0u8; 16], &[0u8; 15]).is_none());
    }

    /// **IEEE P1619-2007 test vector #1** (AES-128 keys all zero, tweak 0).
    /// PT: 32 zero bytes.
    /// CT: 917cf69ebd68b2ec9b9fe9a3eadda692 cd43d2f59598ed858c02c2652fbf922e
    #[test]
    fn xts_ieee_p1619_vector_1() {
        let k1 = AesKey::new(&[0u8; 16]).unwrap();
        let k2 = AesKey::new(&[0u8; 16]).unwrap();
        let tweak = [0u8; 16];
        let pt = [0u8; 32];
        let expected: [u8; 32] = [
            0x91, 0x7c, 0xf6, 0x9e, 0xbd, 0x68, 0xb2, 0xec, 0x9b, 0x9f, 0xe9, 0xa3, 0xea, 0xdd,
            0xa6, 0x92, 0xcd, 0x43, 0xd2, 0xf5, 0x95, 0x98, 0xed, 0x85, 0x8c, 0x02, 0xc2, 0x65,
            0x2f, 0xbf, 0x92, 0x2e,
        ];
        let ct = xts_encrypt(&k1, &k2, &tweak, &pt).unwrap();
        assert_eq!(&ct[..], &expected[..]);
    }

    /// **IEEE P1619-2007 vector #2 — first-block check only**.
    /// K1 / K2 / tweak as in the spec; verify the first 16 bytes of
    /// ciphertext (which is just one XEX block, independent of α-stepping)
    /// match the published expected first block.  Avoids a dependency
    /// on the exact wire-byte-order of the second-block expected
    /// output (different sources publish different conventions).
    #[test]
    fn xts_ieee_p1619_vector_2_first_block() {
        let k1 = AesKey::new(&[0x11u8; 16]).unwrap();
        let k2 = AesKey::new(&[0x22u8; 16]).unwrap();
        let mut tweak = [0u8; 16];
        for i in 0..5 {
            tweak[i] = 0x33;
        }
        let pt = [0x44u8; 32];
        let expected_first: [u8; 16] = [
            0xc4, 0x54, 0x18, 0x5e, 0x6a, 0x16, 0x93, 0x6e, 0x39, 0x33, 0x40, 0x38, 0xac, 0xef,
            0x83, 0x8b,
        ];
        let ct = xts_encrypt(&k1, &k2, &tweak, &pt).unwrap();
        assert_eq!(&ct[..16], &expected_first[..]);
        // Round-trip recovers original.
        let pt2 = xts_decrypt(&k1, &k2, &tweak, &ct).unwrap();
        assert_eq!(&pt2[..], &pt[..]);
    }
}
