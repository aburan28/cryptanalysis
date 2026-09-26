//! **Salsa20** — Bernstein's ARX stream cipher (2005), the direct
//! ancestor of ChaCha20.  Selected for the eSTREAM portfolio (2008).
//!
//! ## Family
//!
//! - [`salsa20_xor`] — the base cipher: 32-byte key, 8-byte nonce, 64-bit
//!   block counter, 20 rounds.  Compatible with the eSTREAM Salsa20/20
//!   test vectors.
//! - [`hsalsa20`] — the key-derivation kernel used by XSalsa20.  Runs
//!   the Salsa20 core on a 16-byte input and returns 32 bytes of state
//!   words (without adding the initial state back).
//! - [`xsalsa20_xor`] — 24-byte nonce variant.  Splits the nonce into
//!   16 bytes for HSalsa20 → subkey, plus 8 bytes for the inner Salsa20.
//!   This is the construction NaCl uses for `crypto_secretbox`.
//! - [`secretbox`] / [`secretbox_open`] — NaCl-style XSalsa20-Poly1305
//!   AEAD with no associated data (matches `crypto_secretbox` in libsodium).
//!
//! ## State layout
//!
//! Salsa20's 16-word state is arranged as a 4×4 matrix with the σ
//! constants on the *diagonal* (positions 0, 5, 10, 15) — contrast
//! with ChaCha20's *first row*.  The key occupies the rest of the
//! first column and the fourth column (positions 1-4 and 11-14); the
//! nonce sits at 6-7 and the counter at 8-9.
//!
//! ## Quarter round
//!
//! ```text
//!     b ^= ROL(a + d,  7)
//!     c ^= ROL(b + a,  9)
//!     d ^= ROL(c + b, 13)
//!     a ^= ROL(d + c, 18)
//! ```
//!
//! Each "double round" is 4 column-quarter-rounds + 4 row-quarter-
//! rounds.  Salsa20/20 = 10 double rounds.
//!
//! ## Security
//!
//! Salsa20/12 and /20 remain unbroken at full strength.  For new
//! designs prefer ChaCha20 — it has better diffusion per round and is
//! the one IETF (RFC 8439) standardised.  This module is provided for
//! NaCl interoperability and for understanding ChaCha's lineage.

const SIGMA: [u32; 4] = [0x61707865, 0x3320646e, 0x79622d32, 0x6b206574];

#[inline]
fn qr(state: &mut [u32; 16], a: usize, b: usize, c: usize, d: usize) {
    state[b] ^= state[a].wrapping_add(state[d]).rotate_left(7);
    state[c] ^= state[b].wrapping_add(state[a]).rotate_left(9);
    state[d] ^= state[c].wrapping_add(state[b]).rotate_left(13);
    state[a] ^= state[d].wrapping_add(state[c]).rotate_left(18);
}

#[inline]
fn salsa20_core(state: &mut [u32; 16]) {
    for _ in 0..10 {
        // Column rounds.
        qr(state, 0, 4, 8, 12);
        qr(state, 5, 9, 13, 1);
        qr(state, 10, 14, 2, 6);
        qr(state, 15, 3, 7, 11);
        // Row rounds.
        qr(state, 0, 1, 2, 3);
        qr(state, 5, 6, 7, 4);
        qr(state, 10, 11, 8, 9);
        qr(state, 15, 12, 13, 14);
    }
}

fn write_key(state: &mut [u32; 16], key: &[u8; 32]) {
    for i in 0..4 {
        state[1 + i] = u32::from_le_bytes(key[i * 4..i * 4 + 4].try_into().unwrap());
    }
    for i in 0..4 {
        state[11 + i] = u32::from_le_bytes(key[16 + i * 4..16 + i * 4 + 4].try_into().unwrap());
    }
}

/// Produce one 64-byte Salsa20/20 keystream block.
pub fn salsa20_block(key: &[u8; 32], nonce: &[u8; 8], counter: u64) -> [u8; 64] {
    let mut state = [0u32; 16];
    state[0] = SIGMA[0];
    state[5] = SIGMA[1];
    state[10] = SIGMA[2];
    state[15] = SIGMA[3];
    write_key(&mut state, key);
    state[6] = u32::from_le_bytes(nonce[0..4].try_into().unwrap());
    state[7] = u32::from_le_bytes(nonce[4..8].try_into().unwrap());
    state[8] = counter as u32;
    state[9] = (counter >> 32) as u32;

    let initial = state;
    salsa20_core(&mut state);

    let mut out = [0u8; 64];
    for i in 0..16 {
        let w = state[i].wrapping_add(initial[i]);
        out[i * 4..i * 4 + 4].copy_from_slice(&w.to_le_bytes());
    }
    out
}

/// XOR `data` with the Salsa20/20 keystream, starting at block counter 0.
pub fn salsa20_xor(data: &[u8], key: &[u8; 32], nonce: &[u8; 8]) -> Vec<u8> {
    let mut out = data.to_vec();
    let mut counter = 0u64;
    for chunk in out.chunks_mut(64) {
        let block = salsa20_block(key, nonce, counter);
        for (b, k) in chunk.iter_mut().zip(block.iter()) {
            *b ^= k;
        }
        counter = counter.wrapping_add(1);
    }
    out
}

/// **HSalsa20** — Salsa20 keyless-of-counter kernel used to derive
/// XSalsa20's subkey.  Takes a 32-byte key and 16-byte input, runs the
/// Salsa20 core, and returns 8 specific output words **without** the
/// "add initial state" feedforward (which makes it not invertible —
/// the property needed for it to act as a PRF).
pub fn hsalsa20(key: &[u8; 32], input: &[u8; 16]) -> [u8; 32] {
    let mut state = [0u32; 16];
    state[0] = SIGMA[0];
    state[5] = SIGMA[1];
    state[10] = SIGMA[2];
    state[15] = SIGMA[3];
    write_key(&mut state, key);
    for i in 0..4 {
        state[6 + i] = u32::from_le_bytes(input[i * 4..i * 4 + 4].try_into().unwrap());
    }

    salsa20_core(&mut state);

    // Output is the σ-diagonal slots plus the input slots (i.e., the
    // four words that aren't key-derived).
    let pick = [0usize, 5, 10, 15, 6, 7, 8, 9];
    let mut out = [0u8; 32];
    for (i, &p) in pick.iter().enumerate() {
        out[i * 4..i * 4 + 4].copy_from_slice(&state[p].to_le_bytes());
    }
    out
}

/// **XSalsa20** — 24-byte-nonce variant.  First 16 nonce bytes feed
/// HSalsa20 to produce a subkey; the remaining 8 bytes are the nonce
/// for an inner Salsa20.  Used by NaCl's `crypto_secretbox`.
pub fn xsalsa20_xor(data: &[u8], key: &[u8; 32], nonce: &[u8; 24]) -> Vec<u8> {
    let mut hsalsa_in = [0u8; 16];
    hsalsa_in.copy_from_slice(&nonce[0..16]);
    let subkey = hsalsa20(key, &hsalsa_in);
    let mut inner_nonce = [0u8; 8];
    inner_nonce.copy_from_slice(&nonce[16..24]);
    salsa20_xor(data, &subkey, &inner_nonce)
}

// ── NaCl secretbox: XSalsa20-Poly1305 AEAD ───────────────────────────

/// Derive the Poly1305 one-time key by encrypting 32 zero bytes under
/// the (subkey, inner-nonce) — same trick as ChaCha20-Poly1305, but in
/// the Salsa20 family.  The first 32 bytes of the Salsa20 stream
/// (counter = 0) become the Poly1305 key.
fn poly1305_key_for_secretbox(subkey: &[u8; 32], inner_nonce: &[u8; 8]) -> [u8; 32] {
    let block = salsa20_block(subkey, inner_nonce, 0);
    let mut out = [0u8; 32];
    out.copy_from_slice(&block[0..32]);
    out
}

/// **NaCl `crypto_secretbox`** — XSalsa20-Poly1305 AEAD, no associated
/// data.  Returns `tag || ciphertext` (16-byte tag prepended, matching
/// libsodium / NaCl wire format).
///
/// The 24-byte nonce should be unique per (key, message); since it's
/// 192 bits, it can be sampled uniformly at random with negligible
/// collision probability.
pub fn secretbox(plaintext: &[u8], key: &[u8; 32], nonce: &[u8; 24]) -> Vec<u8> {
    let mut hin = [0u8; 16];
    hin.copy_from_slice(&nonce[0..16]);
    let subkey = hsalsa20(key, &hin);
    let mut inner_nonce = [0u8; 8];
    inner_nonce.copy_from_slice(&nonce[16..24]);

    let poly_key = poly1305_key_for_secretbox(&subkey, &inner_nonce);
    // Salsa20 stream starting at counter 1 — counter 0 is the poly key.
    let mut ciphertext = plaintext.to_vec();
    let mut counter = 1u64;
    for chunk in ciphertext.chunks_mut(64) {
        let block = salsa20_block(&subkey, &inner_nonce, counter);
        for (b, k) in chunk.iter_mut().zip(block.iter()) {
            *b ^= k;
        }
        counter = counter.wrapping_add(1);
    }
    let tag = crate::symmetric::chacha20::poly1305(&poly_key, &ciphertext);

    let mut out = Vec::with_capacity(16 + ciphertext.len());
    out.extend_from_slice(&tag);
    out.extend_from_slice(&ciphertext);
    out
}

/// **NaCl `crypto_secretbox_open`** — verify + decrypt.  Returns
/// `Some(plaintext)` on tag match, `None` otherwise.
pub fn secretbox_open(boxed: &[u8], key: &[u8; 32], nonce: &[u8; 24]) -> Option<Vec<u8>> {
    if boxed.len() < 16 {
        return None;
    }
    let (tag_bytes, ciphertext) = boxed.split_at(16);

    let mut hin = [0u8; 16];
    hin.copy_from_slice(&nonce[0..16]);
    let subkey = hsalsa20(key, &hin);
    let mut inner_nonce = [0u8; 8];
    inner_nonce.copy_from_slice(&nonce[16..24]);

    let poly_key = poly1305_key_for_secretbox(&subkey, &inner_nonce);
    let expected = crate::symmetric::chacha20::poly1305(&poly_key, ciphertext);

    use subtle::ConstantTimeEq;
    if expected.ct_eq(tag_bytes).unwrap_u8() != 1 {
        return None;
    }

    let mut plaintext = ciphertext.to_vec();
    let mut counter = 1u64;
    for chunk in plaintext.chunks_mut(64) {
        let block = salsa20_block(&subkey, &inner_nonce, counter);
        for (b, k) in chunk.iter_mut().zip(block.iter()) {
            *b ^= k;
        }
        counter = counter.wrapping_add(1);
    }
    Some(plaintext)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// **eSTREAM Salsa20/20 256-bit-key, Set 1, vector #0**
    /// Key: `80` in byte 0, rest zero.  IV/nonce: all zero.  First 64
    /// bytes of stream are the official reference value.
    #[test]
    fn salsa20_estream_set1_vector0() {
        let mut key = [0u8; 32];
        key[0] = 0x80;
        let nonce = [0u8; 8];
        let stream = salsa20_block(&key, &nonce, 0);
        let expected = [
            0xE3, 0xBE, 0x8F, 0xDD, 0x8B, 0xEC, 0xA2, 0xE3, 0xEA, 0x8E, 0xF9, 0x47, 0x5B, 0x29,
            0xA6, 0xE7, 0x00, 0x39, 0x51, 0xE1, 0x09, 0x7A, 0x5C, 0x38, 0xD2, 0x3B, 0x7A, 0x5F,
            0xAD, 0x9F, 0x68, 0x44, 0xB2, 0x2C, 0x97, 0x55, 0x9E, 0x27, 0x23, 0xC7, 0xCB, 0xBD,
            0x3F, 0xE4, 0xFC, 0x8D, 0x9A, 0x07, 0x44, 0x65, 0x2A, 0x83, 0xE7, 0x2A, 0x9C, 0x46,
            0x18, 0x76, 0xAF, 0x4D, 0x7E, 0xF1, 0xA1, 0x17,
        ];
        assert_eq!(stream, expected);
    }

    /// XOR round-trip: encrypting then re-encrypting yields the input.
    #[test]
    fn salsa20_xor_round_trip() {
        let key = [0x42u8; 32];
        let nonce = [0x11u8; 8];
        let msg = b"the quick brown fox jumps over the lazy dog".to_vec();
        let ct = salsa20_xor(&msg, &key, &nonce);
        assert_ne!(ct, msg);
        let pt = salsa20_xor(&ct, &key, &nonce);
        assert_eq!(pt, msg);
    }

    /// **XSalsa20 NaCl test vector** (Bernstein, "Extending the Salsa20
    /// nonce", 2011, §8).
    #[test]
    fn xsalsa20_nacl_vector() {
        let key: [u8; 32] = [
            0x1b, 0x27, 0x55, 0x64, 0x73, 0xe9, 0x85, 0xd4, 0x62, 0xcd, 0x51, 0x19, 0x7a, 0x9a,
            0x46, 0xc7, 0x60, 0x09, 0x54, 0x9e, 0xac, 0x64, 0x74, 0xf2, 0x06, 0xc4, 0xee, 0x08,
            0x44, 0xf6, 0x83, 0x89,
        ];
        let nonce: [u8; 24] = [
            0x69, 0x69, 0x6e, 0xe9, 0x55, 0xb6, 0x2b, 0x73, 0xcd, 0x62, 0xbd, 0xa8, 0x75, 0xfc,
            0x73, 0xd6, 0x82, 0x19, 0xe0, 0x03, 0x6b, 0x7a, 0x0b, 0x37,
        ];
        // Encrypt 32 zero bytes; this is the canonical NaCl stream test.
        let ct = xsalsa20_xor(&[0u8; 32], &key, &nonce);
        let expected: [u8; 32] = [
            0xee, 0xa6, 0xa7, 0x25, 0x1c, 0x1e, 0x72, 0x91, 0x6d, 0x11, 0xc2, 0xcb, 0x21, 0x4d,
            0x3c, 0x25, 0x25, 0x39, 0x12, 0x1d, 0x8e, 0x23, 0x4e, 0x65, 0x2d, 0x65, 0x1f, 0xa4,
            0xc8, 0xcf, 0xf8, 0x80,
        ];
        assert_eq!(ct.as_slice(), &expected);
    }

    /// **NaCl `crypto_secretbox` round-trip + tamper**.
    #[test]
    fn secretbox_round_trip_and_tamper() {
        let key = [0x42u8; 32];
        let nonce = [0x11u8; 24];
        let pt = b"NaCl secretbox compatibility test".to_vec();

        let boxed = secretbox(&pt, &key, &nonce);
        assert_eq!(boxed.len(), 16 + pt.len());
        let opened = secretbox_open(&boxed, &key, &nonce).expect("open");
        assert_eq!(opened, pt);

        // Tampered ciphertext.
        let mut tampered = boxed.clone();
        tampered[20] ^= 1;
        assert!(secretbox_open(&tampered, &key, &nonce).is_none());
        // Tampered tag.
        let mut tampered = boxed.clone();
        tampered[0] ^= 1;
        assert!(secretbox_open(&tampered, &key, &nonce).is_none());
        // Wrong key.
        assert!(secretbox_open(&boxed, &[0x33u8; 32], &nonce).is_none());
    }

    /// HSalsa20 NaCl test vector — verifies the subkey derivation in
    /// isolation.  Same key as `xsalsa20_nacl_vector`, with input =
    /// first 16 bytes of that nonce.
    #[test]
    fn hsalsa20_nacl_subkey() {
        let key: [u8; 32] = [
            0x1b, 0x27, 0x55, 0x64, 0x73, 0xe9, 0x85, 0xd4, 0x62, 0xcd, 0x51, 0x19, 0x7a, 0x9a,
            0x46, 0xc7, 0x60, 0x09, 0x54, 0x9e, 0xac, 0x64, 0x74, 0xf2, 0x06, 0xc4, 0xee, 0x08,
            0x44, 0xf6, 0x83, 0x89,
        ];
        let input: [u8; 16] = [
            0x69, 0x69, 0x6e, 0xe9, 0x55, 0xb6, 0x2b, 0x73, 0xcd, 0x62, 0xbd, 0xa8, 0x75, 0xfc,
            0x73, 0xd6,
        ];
        let subkey = hsalsa20(&key, &input);
        let expected: [u8; 32] = [
            0xdc, 0x90, 0x8d, 0xda, 0x0b, 0x93, 0x44, 0xa9, 0x53, 0x62, 0x9b, 0x73, 0x38, 0x20,
            0x77, 0x88, 0x80, 0xf3, 0xce, 0xb4, 0x21, 0xbb, 0x61, 0xb9, 0x1c, 0xbd, 0x4c, 0x3e,
            0x66, 0x25, 0x6c, 0xe4,
        ];
        assert_eq!(subkey, expected);
    }
}
