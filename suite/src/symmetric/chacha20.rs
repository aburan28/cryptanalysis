//! ChaCha20-Poly1305 AEAD — RFC 8439, implemented from scratch.
//!
//! # ChaCha20 stream cipher
//! State: 16 32-bit little-endian words.
//!   words  0- 3: "expa nd 3 2-by te k" (ASCII constants)
//!   words  4-11: 256-bit key
//!   word  12: 32-bit block counter
//!   words 13-15: 96-bit nonce
//!
//! Each block applies 20 rounds of "quarter rounds" (ARX operations),
//! then adds the original state to produce 64 bytes of keystream.
//!
//! # Poly1305 MAC
//! One-time authenticator over GF(2¹³⁰ - 5).
//! Key: (r, s) derived from the first 32 bytes of ChaCha20 output (counter=0).
//! r is clamped by zeroing specific bits; s is used as-is.
//! The tag is: ((clamp(r)·m₁ + clamp(r)·m₂ + … + s) mod 2¹³⁰-5) mod 2¹²⁸
//!
//! Security note: Poly1305 here is implemented with `BigUint`, so it is
//! variable-time. Tag verification uses constant-time comparison, but this
//! module remains educational rather than production-grade.

use num_bigint::BigUint;
use num_traits::{One, Zero};

// ── ChaCha20 ─────────────────────────────────────────────────────────────────

const SIGMA: [u32; 4] = [0x61707865, 0x3320646e, 0x79622d32, 0x6b206574];

/// Apply one ChaCha20 quarter round to four words.
macro_rules! qr {
    ($a:expr, $b:expr, $c:expr, $d:expr) => {
        $a = $a.wrapping_add($b);
        $d ^= $a;
        $d = $d.rotate_left(16);
        $c = $c.wrapping_add($d);
        $b ^= $c;
        $b = $b.rotate_left(12);
        $a = $a.wrapping_add($b);
        $d ^= $a;
        $d = $d.rotate_left(8);
        $c = $c.wrapping_add($d);
        $b ^= $c;
        $b = $b.rotate_left(7);
    };
}

/// Generate one 64-byte ChaCha20 block at the given counter value.
pub fn chacha20_block(key: &[u8; 32], nonce: &[u8; 12], counter: u32) -> [u8; 64] {
    let mut state = [0u32; 16];
    state[..4].copy_from_slice(&SIGMA);

    for i in 0..8 {
        state[4 + i] = u32::from_le_bytes(key[i * 4..i * 4 + 4].try_into().unwrap());
    }
    state[12] = counter;
    for i in 0..3 {
        state[13 + i] = u32::from_le_bytes(nonce[i * 4..i * 4 + 4].try_into().unwrap());
    }

    let mut working = state;

    // 20 rounds = 10 column rounds + 10 diagonal rounds
    for _ in 0..10 {
        // Column rounds
        qr!(working[0], working[4], working[8], working[12]);
        qr!(working[1], working[5], working[9], working[13]);
        qr!(working[2], working[6], working[10], working[14]);
        qr!(working[3], working[7], working[11], working[15]);
        // Diagonal rounds
        qr!(working[0], working[5], working[10], working[15]);
        qr!(working[1], working[6], working[11], working[12]);
        qr!(working[2], working[7], working[8], working[13]);
        qr!(working[3], working[4], working[9], working[14]);
    }

    let mut out = [0u8; 64];
    for (i, w) in working.iter().enumerate() {
        let w_final = w.wrapping_add(state[i]);
        out[i * 4..i * 4 + 4].copy_from_slice(&w_final.to_le_bytes());
    }
    out
}

/// Encrypt or decrypt `data` using ChaCha20 (XOR with keystream, counter starts at 1).
pub fn chacha20_xor(data: &[u8], key: &[u8; 32], nonce: &[u8; 12]) -> Vec<u8> {
    chacha20_xor_checked(data, key, nonce).expect("ChaCha20 counter would wrap")
}

/// Checked ChaCha20 XOR that rejects inputs requiring counter wraparound.
pub fn chacha20_xor_checked(
    data: &[u8],
    key: &[u8; 32],
    nonce: &[u8; 12],
) -> Result<Vec<u8>, &'static str> {
    ensure_chacha20_capacity(data.len(), 1)?;
    let mut out = data.to_vec();
    let mut counter = 1u32;

    for chunk in out.chunks_mut(64) {
        let block = chacha20_block(key, nonce, counter);
        for (b, k) in chunk.iter_mut().zip(block.iter()) {
            *b ^= k;
        }
        counter = counter.wrapping_add(1);
    }
    Ok(out)
}

pub fn chacha20_len_fits(len: usize, start_counter: u32) -> bool {
    ensure_chacha20_capacity(len, start_counter).is_ok()
}

fn ensure_chacha20_capacity(len: usize, start_counter: u32) -> Result<(), &'static str> {
    let blocks = len
        .checked_add(63)
        .ok_or("ChaCha20 input length overflow")?
        / 64;
    let available = (u32::MAX as u64) - (start_counter as u64) + 1;
    if (blocks as u64) > available {
        Err("ChaCha20 counter would wrap")
    } else {
        Ok(())
    }
}

// ── ChaCha8 / ChaCha12 / HChaCha20 / XChaCha20 ───────────────────────────────

/// Run the ChaCha core for `double_rounds × 2` rounds.  ChaCha20 uses
/// 10 (i.e. 20 rounds); ChaCha12 uses 6; ChaCha8 uses 4.
fn chacha_block_with(
    key: &[u8; 32],
    nonce: &[u8; 12],
    counter: u32,
    double_rounds: usize,
) -> [u8; 64] {
    let mut state = [0u32; 16];
    state[..4].copy_from_slice(&SIGMA);
    for i in 0..8 {
        state[4 + i] = u32::from_le_bytes(key[i * 4..i * 4 + 4].try_into().unwrap());
    }
    state[12] = counter;
    for i in 0..3 {
        state[13 + i] = u32::from_le_bytes(nonce[i * 4..i * 4 + 4].try_into().unwrap());
    }
    let mut working = state;
    for _ in 0..double_rounds {
        qr!(working[0], working[4], working[8], working[12]);
        qr!(working[1], working[5], working[9], working[13]);
        qr!(working[2], working[6], working[10], working[14]);
        qr!(working[3], working[7], working[11], working[15]);
        qr!(working[0], working[5], working[10], working[15]);
        qr!(working[1], working[6], working[11], working[12]);
        qr!(working[2], working[7], working[8], working[13]);
        qr!(working[3], working[4], working[9], working[14]);
    }
    let mut out = [0u8; 64];
    for (i, w) in working.iter().enumerate() {
        let w_final = w.wrapping_add(state[i]);
        out[i * 4..i * 4 + 4].copy_from_slice(&w_final.to_le_bytes());
    }
    out
}

fn chacha_xor_with(data: &[u8], key: &[u8; 32], nonce: &[u8; 12], double_rounds: usize) -> Vec<u8> {
    let mut out = data.to_vec();
    let mut counter = 1u32;
    for chunk in out.chunks_mut(64) {
        let block = chacha_block_with(key, nonce, counter, double_rounds);
        for (b, k) in chunk.iter_mut().zip(block.iter()) {
            *b ^= k;
        }
        counter = counter.wrapping_add(1);
    }
    out
}

/// ChaCha8 keystream block (4 double rounds = 8 single rounds).
pub fn chacha8_block(key: &[u8; 32], nonce: &[u8; 12], counter: u32) -> [u8; 64] {
    chacha_block_with(key, nonce, counter, 4)
}
/// ChaCha8 stream cipher — XOR `data` with keystream (counter starts at 1).
pub fn chacha8_xor(data: &[u8], key: &[u8; 32], nonce: &[u8; 12]) -> Vec<u8> {
    chacha_xor_with(data, key, nonce, 4)
}

/// ChaCha12 keystream block (6 double rounds = 12 single rounds).
pub fn chacha12_block(key: &[u8; 32], nonce: &[u8; 12], counter: u32) -> [u8; 64] {
    chacha_block_with(key, nonce, counter, 6)
}
/// ChaCha12 stream cipher — XOR `data` with keystream (counter starts at 1).
pub fn chacha12_xor(data: &[u8], key: &[u8; 32], nonce: &[u8; 12]) -> Vec<u8> {
    chacha_xor_with(data, key, nonce, 6)
}

/// **HChaCha20** — key-derivation kernel for XChaCha20.  Runs the
/// ChaCha20 core (20 rounds) with the given 32-byte key and 16-byte
/// input slotted into the counter+nonce positions, then returns 8
/// state words (positions 0-3, 12-15) *without* the feed-forward.
pub fn hchacha20(key: &[u8; 32], input: &[u8; 16]) -> [u8; 32] {
    let mut state = [0u32; 16];
    state[..4].copy_from_slice(&SIGMA);
    for i in 0..8 {
        state[4 + i] = u32::from_le_bytes(key[i * 4..i * 4 + 4].try_into().unwrap());
    }
    for i in 0..4 {
        state[12 + i] = u32::from_le_bytes(input[i * 4..i * 4 + 4].try_into().unwrap());
    }
    for _ in 0..10 {
        qr!(state[0], state[4], state[8], state[12]);
        qr!(state[1], state[5], state[9], state[13]);
        qr!(state[2], state[6], state[10], state[14]);
        qr!(state[3], state[7], state[11], state[15]);
        qr!(state[0], state[5], state[10], state[15]);
        qr!(state[1], state[6], state[11], state[12]);
        qr!(state[2], state[7], state[8], state[13]);
        qr!(state[3], state[4], state[9], state[14]);
    }
    let pick = [0usize, 1, 2, 3, 12, 13, 14, 15];
    let mut out = [0u8; 32];
    for (i, &p) in pick.iter().enumerate() {
        out[i * 4..i * 4 + 4].copy_from_slice(&state[p].to_le_bytes());
    }
    out
}

/// **XChaCha20** — 24-byte-nonce variant (draft-irtf-cfrg-xchacha).
/// Derives a subkey via HChaCha20(key, nonce[0..16]); the inner
/// ChaCha20 uses that subkey with a 12-byte nonce composed of 4 zero
/// bytes followed by `nonce[16..24]`.
pub fn xchacha20_xor(data: &[u8], key: &[u8; 32], nonce: &[u8; 24]) -> Vec<u8> {
    let mut hin = [0u8; 16];
    hin.copy_from_slice(&nonce[0..16]);
    let subkey = hchacha20(key, &hin);
    let mut inner_nonce = [0u8; 12];
    inner_nonce[4..12].copy_from_slice(&nonce[16..24]);
    chacha20_xor(data, &subkey, &inner_nonce)
}

// ── Poly1305 ─────────────────────────────────────────────────────────────────

fn p1305() -> BigUint {
    // 2^130 - 5
    (BigUint::one() << 130u32) - BigUint::from(5u32)
}

/// Clamp `r` per RFC 8439: zero out specific bits to reduce the key space.
fn clamp_r(r: &mut [u8; 16]) {
    r[3] &= 0x0f;
    r[7] &= 0x0f;
    r[11] &= 0x0f;
    r[15] &= 0x0f;
    r[4] &= 0xfc;
    r[8] &= 0xfc;
    r[12] &= 0xfc;
}

/// Compute a Poly1305 MAC over `msg` with a 32-byte one-time key (r || s).
pub fn poly1305(key: &[u8; 32], msg: &[u8]) -> [u8; 16] {
    let mut r_bytes: [u8; 16] = key[..16].try_into().unwrap();
    clamp_r(&mut r_bytes);

    let r = BigUint::from_bytes_le(&r_bytes);
    let s = BigUint::from_bytes_le(&key[16..]);
    let p = p1305();

    let mut acc = BigUint::zero();

    for block in msg.chunks(16) {
        let mut block_bytes = block.to_vec();
        block_bytes.push(0x01); // Append one bit above the block
        let n = BigUint::from_bytes_le(&block_bytes);
        acc = ((acc + n) * &r) % &p;
    }

    acc += s;
    // Take mod 2^128 (truncate to 16 bytes little-endian)
    let bytes = acc.to_bytes_le();
    let mut tag = [0u8; 16];
    let copy_len = bytes.len().min(16);
    tag[..copy_len].copy_from_slice(&bytes[..copy_len]);
    tag
}

// ── ChaCha20-Poly1305 AEAD ────────────────────────────────────────────────────

/// Derive the Poly1305 one-time key from the ChaCha20 key + nonce (counter=0).
fn poly1305_key_gen(key: &[u8; 32], nonce: &[u8; 12]) -> [u8; 32] {
    let block = chacha20_block(key, nonce, 0);
    block[..32].try_into().unwrap()
}

/// Build the Poly1305 input: PAD(AAD) || PAD(CT) || len(AAD) || len(CT).
fn poly1305_pad(aad: &[u8], ciphertext: &[u8]) -> Vec<u8> {
    let mut msg = Vec::new();
    msg.extend_from_slice(aad);
    pad16(&mut msg);
    msg.extend_from_slice(ciphertext);
    pad16(&mut msg);
    msg.extend_from_slice(&(aad.len() as u64).to_le_bytes());
    msg.extend_from_slice(&(ciphertext.len() as u64).to_le_bytes());
    msg
}

fn pad16(v: &mut Vec<u8>) {
    let rem = v.len() % 16;
    if rem != 0 {
        v.resize(v.len() + (16 - rem), 0);
    }
}

/// ChaCha20-Poly1305 encrypt. Returns `ciphertext || 16-byte tag`.
pub fn chacha20_poly1305_encrypt(
    plaintext: &[u8],
    key: &[u8; 32],
    nonce: &[u8; 12],
    aad: &[u8],
) -> Vec<u8> {
    chacha20_poly1305_encrypt_checked(plaintext, key, nonce, aad)
        .expect("ChaCha20-Poly1305 counter would wrap")
}

/// Checked ChaCha20-Poly1305 encryption.
pub fn chacha20_poly1305_encrypt_checked(
    plaintext: &[u8],
    key: &[u8; 32],
    nonce: &[u8; 12],
    aad: &[u8],
) -> Result<Vec<u8>, &'static str> {
    let ciphertext = chacha20_xor_checked(plaintext, key, nonce)?;
    let otk = poly1305_key_gen(key, nonce);
    let mac_data = poly1305_pad(aad, &ciphertext);
    let tag = poly1305(&otk, &mac_data);

    let mut out = ciphertext;
    out.extend_from_slice(&tag);
    Ok(out)
}

/// ChaCha20-Poly1305 decrypt. Returns the plaintext, or `None` on tag failure.
pub fn chacha20_poly1305_decrypt(
    ciphertext_and_tag: &[u8],
    key: &[u8; 32],
    nonce: &[u8; 12],
    aad: &[u8],
) -> Option<Vec<u8>> {
    if ciphertext_and_tag.len() < 16 {
        return None;
    }
    let (ciphertext, tag_bytes) = ciphertext_and_tag.split_at(ciphertext_and_tag.len() - 16);

    let otk = poly1305_key_gen(key, nonce);
    let mac_data = poly1305_pad(aad, ciphertext);
    let expected_tag = poly1305(&otk, &mac_data);

    // Constant-time MAC comparison; see `aes::aes_gcm_decrypt` for rationale.
    use subtle::ConstantTimeEq;
    if expected_tag.ct_eq(tag_bytes).unwrap_u8() != 1 {
        return None;
    }

    chacha20_xor_checked(ciphertext, key, nonce).ok()
}

// ── XChaCha20-Poly1305 (draft-irtf-cfrg-xchacha) ─────────────────────────────

/// **XChaCha20-Poly1305 encrypt** — extended-nonce AEAD (24-byte nonce).
///
/// Internally: derive a subkey via `HChaCha20(key, nonce[0..16])`, then
/// run ChaCha20-Poly1305 with the subkey and a 12-byte inner nonce of
/// `0x00000000 || nonce[16..24]` (RFC-draft convention).  This lets
/// you sample nonces uniformly at random without birthday-bound
/// worries — the bottleneck moves to 2^96 instead of 2^48.
pub fn xchacha20_poly1305_encrypt(
    plaintext: &[u8],
    key: &[u8; 32],
    nonce: &[u8; 24],
    aad: &[u8],
) -> Vec<u8> {
    let mut hin = [0u8; 16];
    hin.copy_from_slice(&nonce[0..16]);
    let subkey = hchacha20(key, &hin);
    let mut inner_nonce = [0u8; 12];
    inner_nonce[4..12].copy_from_slice(&nonce[16..24]);
    chacha20_poly1305_encrypt(plaintext, &subkey, &inner_nonce, aad)
}

/// **XChaCha20-Poly1305 decrypt + verify**.  Returns `None` on tag failure.
pub fn xchacha20_poly1305_decrypt(
    ciphertext_and_tag: &[u8],
    key: &[u8; 32],
    nonce: &[u8; 24],
    aad: &[u8],
) -> Option<Vec<u8>> {
    let mut hin = [0u8; 16];
    hin.copy_from_slice(&nonce[0..16]);
    let subkey = hchacha20(key, &hin);
    let mut inner_nonce = [0u8; 12];
    inner_nonce[4..12].copy_from_slice(&nonce[16..24]);
    chacha20_poly1305_decrypt(ciphertext_and_tag, &subkey, &inner_nonce, aad)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn h(s: &str) -> Vec<u8> {
        hex::decode(s).unwrap()
    }

    // ── ChaCha20 block KATs (RFC 8439) ────────────────────────────────────────

    #[test]
    fn chacha20_block_zero_key() {
        // RFC 8439 §2.3.2: zero key, zero nonce, counter 0.
        let key = [0u8; 32];
        let nonce = [0u8; 12];
        let block = chacha20_block(&key, &nonce, 0);
        let expected = h("76b8e0ada0f13d90405d6ae55386bd28bdd219b8a08ded1aa836efcc8b770dc7da41597c5157488d7724e03fb8d84a376a43b8f41518a11cc387b669b2ee6586");
        assert_eq!(&block[..], expected.as_slice());
    }

    #[test]
    fn chacha20_block_rfc8439_2_3_2() {
        // RFC 8439 §2.3.2 named example.
        let key: [u8; 32] = h("000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f")
            .try_into()
            .unwrap();
        let nonce: [u8; 12] = h("000000090000004a00000000").try_into().unwrap();
        let block = chacha20_block(&key, &nonce, 1);
        let expected = h("10f1e7e4d13b5915500fdd1fa32071c4c7d1f4c733c068030422aa9ac3d46c4ed2826446079faa0914c2d705d98b02a2b5129cd1de164eb9cbd083e8a2503c4e");
        assert_eq!(&block[..], expected.as_slice());
    }

    // ── ChaCha20 stream cipher KAT (RFC 8439 §2.4.2) ─────────────────────────

    #[test]
    fn chacha20_xor_rfc8439_2_4_2() {
        let key: [u8; 32] = h("000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f")
            .try_into()
            .unwrap();
        let nonce: [u8; 12] = h("000000000000004a00000000").try_into().unwrap();
        let pt = b"Ladies and Gentlemen of the class of '99: If I could offer you only one tip for the future, sunscreen would be it.";
        let ct = chacha20_xor(pt, &key, &nonce);
        let expected = h("6e2e359a2568f98041ba0728dd0d6981e97e7aec1d4360c20a27afccfd9fae0bf91b65c5524733ab8f593dabcd62b3571639d624e65152ab8f530c359f0861d807ca0dbf500d6a6156a38e088a22b65e52bc514d16ccf806818ce91ab77937365af90bbf74a35be6b40b8eedf2785e42874d");
        assert_eq!(ct, expected);
        // Roundtrip
        let dec = chacha20_xor(&ct, &key, &nonce);
        assert_eq!(&dec, pt);
    }

    #[test]
    fn chacha20_roundtrip_random_lengths() {
        let key = [0x42u8; 32];
        let nonce = [0x07u8; 12];
        for len in [
            0usize, 1, 15, 16, 17, 63, 64, 65, 127, 128, 129, 255, 256, 257,
        ] {
            let pt: Vec<u8> = (0..len).map(|i| (i as u8).wrapping_mul(31)).collect();
            let ct = chacha20_xor(&pt, &key, &nonce);
            let dec = chacha20_xor(&ct, &key, &nonce);
            assert_eq!(dec, pt, "roundtrip failed at len={}", len);
        }
    }

    #[test]
    fn chacha20_rejects_counter_wrap_without_allocating() {
        let max_len = (u32::MAX as usize) * 64;
        assert!(chacha20_len_fits(max_len, 1));
        assert!(!chacha20_len_fits(max_len + 1, 1));
        assert!(chacha20_len_fits(64, u32::MAX));
        assert!(!chacha20_len_fits(65, u32::MAX));
    }

    // ── Poly1305 KATs (RFC 8439 §2.5.2) ──────────────────────────────────────

    #[test]
    fn poly1305_rfc8439_2_5_2() {
        let key: [u8; 32] = h("85d6be7857556d337f4452fe42d506a80103808afb0db2fd4abff6af4149f51b")
            .try_into()
            .unwrap();
        let msg = b"Cryptographic Forum Research Group";
        let tag = poly1305(&key, msg);
        assert_eq!(&tag, h("a8061dc1305136c6c22b8baf0c0127a9").as_slice());
    }

    // ── ChaCha20-Poly1305 AEAD KAT (RFC 8439 §2.8.2) ─────────────────────────

    #[test]
    fn chacha20_poly1305_rfc8439_2_8_2() {
        let key: [u8; 32] = h("808182838485868788898a8b8c8d8e8f909192939495969798999a9b9c9d9e9f")
            .try_into()
            .unwrap();
        let nonce: [u8; 12] = h("070000004041424344454647").try_into().unwrap();
        let aad = h("50515253c0c1c2c3c4c5c6c7");
        let pt = b"Ladies and Gentlemen of the class of '99: If I could offer you only one tip for the future, sunscreen would be it.";
        let expected = h("d31a8d34648e60db7b86afbc53ef7ec2a4aded51296e08fea9e2b5a736ee62d63dbea45e8ca9671282fafb69da92728b1a71de0a9e060b2905d6a5b67ecd3b3692ddbd7f2d778b8c9803aee328091b58fab324e4fad675945585808b4831d7bc3ff4def08e4b7a9de576d26586cec64b61161ae10b594f09e26a7e902ecbd0600691");
        let ct = chacha20_poly1305_encrypt(pt, &key, &nonce, &aad);
        assert_eq!(ct, expected);
        let dec = chacha20_poly1305_decrypt(&ct, &key, &nonce, &aad).unwrap();
        assert_eq!(&dec, pt);
    }

    #[test]
    fn chacha20_poly1305_tamper_ciphertext_fails() {
        let key = [0x42u8; 32];
        let nonce = [0u8; 12];
        let mut ct = chacha20_poly1305_encrypt(b"secret", &key, &nonce, b"");
        ct[0] ^= 0xff;
        assert!(chacha20_poly1305_decrypt(&ct, &key, &nonce, b"").is_none());
    }

    #[test]
    fn chacha20_poly1305_tamper_tag_fails() {
        let key = [0x42u8; 32];
        let nonce = [0u8; 12];
        let mut ct = chacha20_poly1305_encrypt(b"secret message", &key, &nonce, b"aad");
        let last = ct.len() - 1;
        ct[last] ^= 0x01;
        assert!(chacha20_poly1305_decrypt(&ct, &key, &nonce, b"aad").is_none());
    }

    #[test]
    fn chacha20_poly1305_tamper_aad_fails() {
        let key = [0x42u8; 32];
        let nonce = [0u8; 12];
        let ct = chacha20_poly1305_encrypt(b"data", &key, &nonce, b"original-aad");
        assert!(chacha20_poly1305_decrypt(&ct, &key, &nonce, b"different-aad").is_none());
    }

    #[test]
    fn chacha20_poly1305_short_input_fails() {
        let key = [0u8; 32];
        let nonce = [0u8; 12];
        // Less than 16 bytes is not even a valid tag, must reject.
        assert!(chacha20_poly1305_decrypt(&[0u8; 8], &key, &nonce, b"").is_none());
    }

    // ── ChaCha8 / ChaCha12 / HChaCha20 / XChaCha20 ───────────────────

    /// Self-consistency: `chacha_block_with(..., 10)` must equal the
    /// dedicated `chacha20_block`.
    #[test]
    fn chacha_param_matches_chacha20() {
        let key = [0x42u8; 32];
        let nonce = [0x11u8; 12];
        assert_eq!(
            chacha_block_with(&key, &nonce, 7, 10),
            chacha20_block(&key, &nonce, 7)
        );
    }

    /// ChaCha8 and ChaCha12 XOR round-trips.
    #[test]
    fn chacha8_chacha12_round_trip() {
        let key = [0x55u8; 32];
        let nonce = [0x22u8; 12];
        let msg = b"reduced-round ChaCha siblings".to_vec();
        let ct8 = chacha8_xor(&msg, &key, &nonce);
        let ct12 = chacha12_xor(&msg, &key, &nonce);
        assert_ne!(ct8, msg);
        assert_ne!(ct12, msg);
        assert_ne!(ct8, ct12);
        assert_eq!(chacha8_xor(&ct8, &key, &nonce), msg);
        assert_eq!(chacha12_xor(&ct12, &key, &nonce), msg);
    }

    /// **HChaCha20 test vector** from draft-irtf-cfrg-xchacha §2.2.1.
    #[test]
    fn hchacha20_irtf_vector() {
        let key: [u8; 32] = [
            0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d,
            0x0e, 0x0f, 0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1a, 0x1b,
            0x1c, 0x1d, 0x1e, 0x1f,
        ];
        let input: [u8; 16] = [
            0x00, 0x00, 0x00, 0x09, 0x00, 0x00, 0x00, 0x4a, 0x00, 0x00, 0x00, 0x00, 0x31, 0x41,
            0x59, 0x27,
        ];
        let subkey = hchacha20(&key, &input);
        let expected: [u8; 32] = [
            0x82, 0x41, 0x3b, 0x42, 0x27, 0xb2, 0x7b, 0xfe, 0xd3, 0x0e, 0x42, 0x50, 0x8a, 0x87,
            0x7d, 0x73, 0xa0, 0xf9, 0xe4, 0xd5, 0x8a, 0x74, 0xa8, 0x53, 0xc1, 0x2e, 0xc4, 0x13,
            0x26, 0xd3, 0xec, 0xdc,
        ];
        assert_eq!(subkey, expected);
    }

    /// XChaCha20 XOR round-trip + length sanity check.
    #[test]
    fn xchacha20_round_trip() {
        let key = [0x77u8; 32];
        let nonce = [0x33u8; 24];
        let msg = b"XChaCha20 with a 24-byte nonce is randomizable in practice".to_vec();
        let ct = xchacha20_xor(&msg, &key, &nonce);
        assert_ne!(ct, msg);
        assert_eq!(ct.len(), msg.len());
        assert_eq!(xchacha20_xor(&ct, &key, &nonce), msg);
    }

    /// **XChaCha20-Poly1305** AEAD round-trip + tamper.  No IETF
    /// has-finalised test vectors at the time of writing, so we
    /// verify the composition: encrypt → decrypt → match, plus all
    /// three failure modes (tampered CT, tampered tag, wrong AAD).
    #[test]
    fn xchacha20_poly1305_aead_round_trip_and_tamper() {
        let key = [0x42u8; 32];
        let nonce = [0x99u8; 24];
        let aad = b"associated data";
        let pt = b"the 24-byte nonce makes random sampling safe".to_vec();

        let ct = xchacha20_poly1305_encrypt(&pt, &key, &nonce, aad);
        assert_eq!(ct.len(), pt.len() + 16);
        let recovered = xchacha20_poly1305_decrypt(&ct, &key, &nonce, aad).expect("decrypt");
        assert_eq!(recovered, pt);

        // Tampered CT.
        let mut tampered = ct.clone();
        tampered[0] ^= 1;
        assert!(xchacha20_poly1305_decrypt(&tampered, &key, &nonce, aad).is_none());
        // Tampered tag.
        let mut tampered = ct.clone();
        let last = tampered.len() - 1;
        tampered[last] ^= 1;
        assert!(xchacha20_poly1305_decrypt(&tampered, &key, &nonce, aad).is_none());
        // Wrong AAD.
        assert!(xchacha20_poly1305_decrypt(&ct, &key, &nonce, b"other-aad").is_none());
    }

    /// XChaCha20-Poly1305 is equivalent to ChaCha20-Poly1305 with a
    /// derived subkey — verify the composition by hand to ensure
    /// the wrapper isn't doing anything subtle.
    #[test]
    fn xchacha20_poly1305_equals_subkey_chacha_poly() {
        let key = [0x33u8; 32];
        let nonce = [0x55u8; 24];
        let aad = b"";
        let pt = b"composition check".to_vec();

        let ct_via_xchacha = xchacha20_poly1305_encrypt(&pt, &key, &nonce, aad);

        let mut hin = [0u8; 16];
        hin.copy_from_slice(&nonce[0..16]);
        let subkey = hchacha20(&key, &hin);
        let mut inner_nonce = [0u8; 12];
        inner_nonce[4..12].copy_from_slice(&nonce[16..24]);
        let ct_via_chacha = chacha20_poly1305_encrypt(&pt, &subkey, &inner_nonce, aad);

        assert_eq!(ct_via_xchacha, ct_via_chacha);
    }
}
