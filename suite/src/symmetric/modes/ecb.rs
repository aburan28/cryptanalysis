//! **ECB — Electronic Codebook**.
//!
//! `C_i = E(P_i)` independently per block.  No chaining, no IV.
//!
//! > ⚠️ **ECB is broken**.  Identical plaintext blocks produce identical
//! > ciphertext blocks — the canonical "ECB penguin" example.  We
//! > implement it because (a) it's a teaching reference, (b) CBC/CFB/OFB
//! > all internally invoke ECB on individual blocks, and (c) some
//! > legacy protocols still specify it.  **Never use ECB for messages
//! > longer than one block**.
//!
//! Generic over [`BlockCipher<N>`]; we PKCS#7-pad on `encrypt` and
//! validate the padding on `decrypt`.

use super::cipher::BlockCipher;

/// PKCS#7 pad `data` to a multiple of `N` bytes.
pub fn pkcs7_pad<const N: usize>(data: &[u8]) -> Vec<u8> {
    let pad = N - (data.len() % N);
    let mut out = Vec::with_capacity(data.len() + pad);
    out.extend_from_slice(data);
    for _ in 0..pad {
        out.push(pad as u8);
    }
    out
}

/// Strip PKCS#7 padding; returns `None` if invalid.
pub fn pkcs7_unpad<const N: usize>(data: &[u8]) -> Option<Vec<u8>> {
    if data.is_empty() || !data.len().is_multiple_of(N) {
        return None;
    }
    let pad = *data.last()? as usize;
    if pad == 0 || pad > N {
        return None;
    }
    if data.len() < pad {
        return None;
    }
    let pad_start = data.len() - pad;
    if data[pad_start..].iter().any(|&b| b as usize != pad) {
        return None;
    }
    Some(data[..pad_start].to_vec())
}

/// **ECB encrypt** with PKCS#7 padding.
pub fn ecb_encrypt<C: BlockCipher<N>, const N: usize>(cipher: &C, plaintext: &[u8]) -> Vec<u8> {
    let padded = pkcs7_pad::<N>(plaintext);
    let mut out = Vec::with_capacity(padded.len());
    for chunk in padded.chunks(N) {
        let mut block = [0u8; N];
        block.copy_from_slice(chunk);
        cipher.encrypt_block(&mut block);
        out.extend_from_slice(&block);
    }
    out
}

/// **ECB decrypt** with PKCS#7 padding validation.  Returns `None` on
/// length or padding error.
pub fn ecb_decrypt<C: BlockCipher<N>, const N: usize>(
    cipher: &C,
    ciphertext: &[u8],
) -> Option<Vec<u8>> {
    if ciphertext.is_empty() || !ciphertext.len().is_multiple_of(N) {
        return None;
    }
    let mut out = Vec::with_capacity(ciphertext.len());
    for chunk in ciphertext.chunks(N) {
        let mut block = [0u8; N];
        block.copy_from_slice(chunk);
        cipher.decrypt_block(&mut block);
        out.extend_from_slice(&block);
    }
    pkcs7_unpad::<N>(&out)
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::symmetric::aes::AesKey;

    /// Round-trip on a message that needs padding.
    #[test]
    fn ecb_aes_round_trip() {
        let key = AesKey::new(&[0u8; 16]).unwrap();
        let pt = b"hello, world!";
        let ct = ecb_encrypt::<_, 16>(&key, pt);
        assert_eq!(ct.len(), 16); // padded to one full block
        let recovered = ecb_decrypt::<_, 16>(&key, &ct).unwrap();
        assert_eq!(recovered, pt);
    }

    /// **The ECB penguin**: identical plaintext blocks produce
    /// identical ciphertext blocks — this is exactly what makes ECB
    /// insecure.  Demonstrate the leak.
    #[test]
    fn ecb_leaks_block_repetition() {
        let key = AesKey::new(&[7u8; 16]).unwrap();
        let pt: Vec<u8> = (0..64).map(|i| (i % 16) as u8).collect(); // 4 identical blocks
                                                                     // Manually replicate one block so we have 4 identical 16-byte chunks.
        let mut pt2 = vec![0u8; 64];
        for i in 0..64 {
            pt2[i] = (i % 16) as u8;
        }
        // Encrypt without padding by carefully feeding a multiple of 16.
        let padded = pkcs7_pad::<16>(&pt2);
        let mut out = Vec::new();
        for chunk in padded.chunks(16) {
            let mut blk = [0u8; 16];
            blk.copy_from_slice(chunk);
            BlockCipher::<16>::encrypt_block(&key, &mut blk);
            out.extend_from_slice(&blk);
        }
        // First 4 input blocks are identical → first 4 output blocks identical.
        assert_eq!(&out[0..16], &out[16..32]);
        assert_eq!(&out[16..32], &out[32..48]);
        // (The 5th block is the padding block, may differ.)
        let _ = pt;
    }

    /// Truncated ciphertext fails to decrypt.
    #[test]
    fn ecb_rejects_short_ciphertext() {
        let key = AesKey::new(&[0u8; 16]).unwrap();
        assert!(ecb_decrypt::<_, 16>(&key, &[1u8; 15]).is_none());
        assert!(ecb_decrypt::<_, 16>(&key, &[]).is_none());
    }

    /// PKCS#7 padding round-trips.
    #[test]
    fn pkcs7_round_trips() {
        for len in 0..=32 {
            let data = vec![0xABu8; len];
            let padded = pkcs7_pad::<16>(&data);
            assert_eq!(padded.len() % 16, 0);
            let unpadded = pkcs7_unpad::<16>(&padded).unwrap();
            assert_eq!(unpadded, data);
        }
    }

    /// PKCS#7 rejects invalid padding.
    #[test]
    fn pkcs7_rejects_bad_padding() {
        // Padding byte too large.
        let mut bad = vec![0u8; 16];
        bad[15] = 0x11; // 17 > 16
        assert!(pkcs7_unpad::<16>(&bad).is_none());
        // Padding byte 0.
        let mut zero = vec![0u8; 16];
        zero[15] = 0;
        assert!(pkcs7_unpad::<16>(&zero).is_none());
        // Mismatched pad bytes.
        let mut bad2 = vec![0u8; 16];
        bad2[14] = 0x02;
        bad2[15] = 0x03; // last says 3, but byte[13] != 3
        assert!(pkcs7_unpad::<16>(&bad2).is_none());
    }
}
