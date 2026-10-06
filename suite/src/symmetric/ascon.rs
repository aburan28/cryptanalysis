//! **Ascon-128 AEAD** — NIST Lightweight Cryptography winner (2023).
//!
//! Ascon is an authenticated-encryption scheme built around a 320-bit
//! sponge permutation operating on five 64-bit words.  The Ascon-128
//! variant uses a 128-bit key, 128-bit nonce, 128-bit tag, and processes
//! AD/PT at a 64-bit rate, applying the 12-round permutation `p^a`
//! during initialization and finalization and the 6-round permutation
//! `p^b` between data blocks.
//!
//! ## Permutation
//!
//! Each round of `p^r` applies:
//!   1. **Constant addition** to word `x2` (round-dependent).
//!   2. **Substitution layer**: 5-bit S-box applied column-wise across
//!      the five words (64 parallel S-boxes).
//!   3. **Linear diffusion**: per-word `Σ(x)` of two cyclic rotations,
//!      with rotation pairs (19,28), (61,39), (1,6), (10,17), (7,41).
//!
//! ## Mode (Ascon-128, rate r = 64 bits)
//!
//! - **Init**: state = IV ‖ K ‖ N, then `p^12`, then XOR `0^192 ‖ K`.
//! - **AD**: XOR each 8-byte block into `x0`, apply `p^6`.  An AD
//!   processed (even if empty after the domain-separation constant) is
//!   followed by `state ⊕= (0…0, 1)` to separate from the next phase.
//! - **PT/CT**: XOR-then-output each 8-byte block at `x0`, apply `p^6`
//!   between blocks (no `p^6` after the last block).
//! - **Final**: XOR `K` into words `x1..x3`, apply `p^12`, then the tag
//!   is `x3 ‖ x4` XOR `K` (low 128 bits).
//!
//! ## Padding
//!
//! Each absorbed block is padded with the byte `0x80` followed by zeros
//! to the next rate boundary.  When the input length is an exact
//! multiple of the rate, a *whole extra padding block* (`0x80 0x00…`)
//! is absorbed.
//!
//! ## Security note
//!
//! Implemented from the specification for pedagogy; not constant-time
//! against side-channel attackers beyond the tag-comparison step.
//! Reusing a (key, nonce) pair catastrophically breaks confidentiality
//! and authenticity.

use subtle::ConstantTimeEq;

/// Ascon-128 IV: `k=128 ‖ r=64 ‖ a=12 ‖ b=6 ‖ 0^32` packed big-endian
/// into a single 64-bit word.
const IV_ASCON128: u64 = 0x80400c0600000000;

const RATE: usize = 8; // 64 bits
const ROUNDS_A: usize = 12;
const ROUNDS_B: usize = 6;

/// Round constants for `p^12`; `p^r` uses the *last* `r` of these.
const RC: [u64; 12] = [
    0xf0, 0xe1, 0xd2, 0xc3, 0xb4, 0xa5, 0x96, 0x87, 0x78, 0x69, 0x5a, 0x4b,
];

/// One Ascon round on the 320-bit state `s` with round constant `c`.
#[inline]
fn round(s: &mut [u64; 5], c: u64) {
    // Add round constant.
    s[2] ^= c;

    // S-box layer (5-bit S-box, column-wise across the five words).
    let mut x0 = s[0];
    let mut x1 = s[1];
    let mut x2 = s[2];
    let mut x3 = s[3];
    let mut x4 = s[4];

    x0 ^= x4;
    x4 ^= x3;
    x2 ^= x1;
    // T[i] = (~S[i]) & S[(i+1) mod 5]; then S[i] ^= T[(i+1) mod 5].
    let t0 = !x0 & x1;
    let t1 = !x1 & x2;
    let t2 = !x2 & x3;
    let t3 = !x3 & x4;
    let t4 = !x4 & x0;
    x0 ^= t1;
    x1 ^= t2;
    x2 ^= t3;
    x3 ^= t4;
    x4 ^= t0;
    x1 ^= x0;
    x0 ^= x4;
    x3 ^= x2;
    x2 = !x2;

    // Linear diffusion: Σᵢ(x) = x ⊕ ROR(x, r1) ⊕ ROR(x, r2).
    s[0] = x0 ^ x0.rotate_right(19) ^ x0.rotate_right(28);
    s[1] = x1 ^ x1.rotate_right(61) ^ x1.rotate_right(39);
    s[2] = x2 ^ x2.rotate_right(1) ^ x2.rotate_right(6);
    s[3] = x3 ^ x3.rotate_right(10) ^ x3.rotate_right(17);
    s[4] = x4 ^ x4.rotate_right(7) ^ x4.rotate_right(41);
}

#[inline]
fn permutation(s: &mut [u64; 5], rounds: usize) {
    let start = 12 - rounds;
    for i in start..12 {
        round(s, RC[i]);
    }
}

/// Big-endian u64 load of `bytes[..8]`.
#[inline]
fn load_u64_be(bytes: &[u8]) -> u64 {
    u64::from_be_bytes(bytes.try_into().unwrap())
}

/// Pad a partial block (`<8` bytes) into a u64 with `0x80` after the data.
#[inline]
fn pad_block(partial: &[u8]) -> u64 {
    let mut buf = [0u8; 8];
    buf[..partial.len()].copy_from_slice(partial);
    buf[partial.len()] = 0x80;
    u64::from_be_bytes(buf)
}

/// Build the initial state and absorb K at the end of `p^12`.
fn init_state(key: &[u8; 16], nonce: &[u8; 16]) -> ([u64; 5], u64, u64) {
    let k0 = load_u64_be(&key[0..8]);
    let k1 = load_u64_be(&key[8..16]);
    let n0 = load_u64_be(&nonce[0..8]);
    let n1 = load_u64_be(&nonce[8..16]);

    let mut s = [IV_ASCON128, k0, k1, n0, n1];
    permutation(&mut s, ROUNDS_A);
    s[3] ^= k0;
    s[4] ^= k1;
    (s, k0, k1)
}

/// Absorb associated data into `s` (no-op state-wise if `aad` is empty,
/// but always followed by the domain-separation constant by the caller).
fn absorb_aad(s: &mut [u64; 5], aad: &[u8]) {
    if !aad.is_empty() {
        let mut chunks = aad.chunks_exact(RATE);
        for blk in &mut chunks {
            s[0] ^= load_u64_be(blk);
            permutation(s, ROUNDS_B);
        }
        let rem = chunks.remainder();
        s[0] ^= pad_block(rem);
        permutation(s, ROUNDS_B);
    }
    // Domain-separation constant between AAD and message phases.
    s[4] ^= 1u64;
}

/// Encrypt the plaintext stream into `out`, mutating `s`.
fn encrypt_stream(s: &mut [u64; 5], plaintext: &[u8], out: &mut Vec<u8>) {
    let mut chunks = plaintext.chunks_exact(RATE);
    for blk in &mut chunks {
        s[0] ^= load_u64_be(blk);
        out.extend_from_slice(&s[0].to_be_bytes());
        permutation(s, ROUNDS_B);
    }
    let rem = chunks.remainder();
    s[0] ^= pad_block(rem);
    let block_bytes = s[0].to_be_bytes();
    out.extend_from_slice(&block_bytes[..rem.len()]);
    // No permutation after the final (padded) plaintext block.
}

/// Decrypt the ciphertext stream into `out`, mutating `s`.
fn decrypt_stream(s: &mut [u64; 5], ciphertext: &[u8], out: &mut Vec<u8>) {
    let mut chunks = ciphertext.chunks_exact(RATE);
    for blk in &mut chunks {
        let c = load_u64_be(blk);
        let p = s[0] ^ c;
        out.extend_from_slice(&p.to_be_bytes());
        s[0] = c;
        permutation(s, ROUNDS_B);
    }
    let rem = chunks.remainder();
    if !rem.is_empty() {
        let block_bytes = s[0].to_be_bytes();
        let mut p = [0u8; 8];
        for i in 0..rem.len() {
            p[i] = block_bytes[i] ^ rem[i];
        }
        out.extend_from_slice(&p[..rem.len()]);
        // Reconstruct the rate word: ciphertext bytes for the rem positions,
        // tail keeps `s[0]`'s bytes; then XOR the `0x80` pad at position rem.len().
        let mut new_x0 = [0u8; 8];
        new_x0[..rem.len()].copy_from_slice(rem);
        new_x0[rem.len()..].copy_from_slice(&block_bytes[rem.len()..]);
        s[0] = u64::from_be_bytes(new_x0);
        s[0] ^= 0x80u64 << (8 * (7 - rem.len()));
    } else {
        // Exact-multiple input: absorb the pad-only block (no permutation after).
        s[0] ^= 0x8000000000000000u64;
    }
}

/// Finalize: XOR K into x1‖x2, run `p^12`, then tag = (x3‖x4) ⊕ K.
fn finalize(s: &mut [u64; 5], k0: u64, k1: u64) -> [u8; 16] {
    s[1] ^= k0;
    s[2] ^= k1;
    permutation(s, ROUNDS_A);
    let t0 = s[3] ^ k0;
    let t1 = s[4] ^ k1;
    let mut tag = [0u8; 16];
    tag[0..8].copy_from_slice(&t0.to_be_bytes());
    tag[8..16].copy_from_slice(&t1.to_be_bytes());
    tag
}

/// Encrypt under Ascon-128. Returns `ciphertext || 16-byte tag`.
pub fn ascon128_encrypt(key: &[u8; 16], nonce: &[u8; 16], aad: &[u8], plaintext: &[u8]) -> Vec<u8> {
    let (mut s, k0, k1) = init_state(key, nonce);
    absorb_aad(&mut s, aad);

    let mut out = Vec::with_capacity(plaintext.len() + 16);
    encrypt_stream(&mut s, plaintext, &mut out);

    let tag = finalize(&mut s, k0, k1);
    out.extend_from_slice(&tag);
    out
}

/// Decrypt under Ascon-128. Returns `Some(plaintext)` on tag verification,
/// or `None` on failure.
pub fn ascon128_decrypt(
    key: &[u8; 16],
    nonce: &[u8; 16],
    aad: &[u8],
    ciphertext_and_tag: &[u8],
) -> Option<Vec<u8>> {
    if ciphertext_and_tag.len() < 16 {
        return None;
    }
    let (ciphertext, tag_bytes) = ciphertext_and_tag.split_at(ciphertext_and_tag.len() - 16);

    let (mut s, k0, k1) = init_state(key, nonce);
    absorb_aad(&mut s, aad);

    let mut out = Vec::with_capacity(ciphertext.len());
    decrypt_stream(&mut s, ciphertext, &mut out);

    let expected = finalize(&mut s, k0, k1);
    if expected.ct_eq(tag_bytes).unwrap_u8() != 1 {
        return None;
    }
    Some(out)
}

// ── Ascon-128a ──────────────────────────────────────────────────────────────
//
// Same construction as Ascon-128 but with a 128-bit rate (two state words
// per absorb) and 8 rounds in p^b instead of 6.  Faster on long messages
// at the cost of slightly less margin per round of p^b.
//
// IV:    k=128 ‖ r=128 ‖ a=12 ‖ b=8 ‖ 0^32  =  0x80800c0800000000.

const IV_ASCON128A: u64 = 0x80800c0800000000;
const RATE_A: usize = 16;
const ROUNDS_B_A: usize = 8;

fn pad_block_a(partial: &[u8]) -> (u64, u64) {
    let mut buf = [0u8; 16];
    buf[..partial.len()].copy_from_slice(partial);
    buf[partial.len()] = 0x80;
    let lo = u64::from_be_bytes(buf[0..8].try_into().unwrap());
    let hi = u64::from_be_bytes(buf[8..16].try_into().unwrap());
    (lo, hi)
}

fn init_state_a(key: &[u8; 16], nonce: &[u8; 16]) -> ([u64; 5], u64, u64) {
    let k0 = load_u64_be(&key[0..8]);
    let k1 = load_u64_be(&key[8..16]);
    let n0 = load_u64_be(&nonce[0..8]);
    let n1 = load_u64_be(&nonce[8..16]);
    let mut s = [IV_ASCON128A, k0, k1, n0, n1];
    permutation(&mut s, ROUNDS_A);
    s[3] ^= k0;
    s[4] ^= k1;
    (s, k0, k1)
}

fn absorb_aad_a(s: &mut [u64; 5], aad: &[u8]) {
    if !aad.is_empty() {
        let mut chunks = aad.chunks_exact(RATE_A);
        for blk in &mut chunks {
            s[0] ^= load_u64_be(&blk[0..8]);
            s[1] ^= load_u64_be(&blk[8..16]);
            permutation(s, ROUNDS_B_A);
        }
        let rem = chunks.remainder();
        let (lo, hi) = pad_block_a(rem);
        s[0] ^= lo;
        s[1] ^= hi;
        permutation(s, ROUNDS_B_A);
    }
    s[4] ^= 1u64;
}

fn encrypt_stream_a(s: &mut [u64; 5], plaintext: &[u8], out: &mut Vec<u8>) {
    let mut chunks = plaintext.chunks_exact(RATE_A);
    for blk in &mut chunks {
        s[0] ^= load_u64_be(&blk[0..8]);
        s[1] ^= load_u64_be(&blk[8..16]);
        out.extend_from_slice(&s[0].to_be_bytes());
        out.extend_from_slice(&s[1].to_be_bytes());
        permutation(s, ROUNDS_B_A);
    }
    let rem = chunks.remainder();
    let (lo, hi) = pad_block_a(rem);
    s[0] ^= lo;
    s[1] ^= hi;
    let lo_bytes = s[0].to_be_bytes();
    let hi_bytes = s[1].to_be_bytes();
    let mut tail = [0u8; 16];
    tail[0..8].copy_from_slice(&lo_bytes);
    tail[8..16].copy_from_slice(&hi_bytes);
    out.extend_from_slice(&tail[..rem.len()]);
}

fn decrypt_stream_a(s: &mut [u64; 5], ciphertext: &[u8], out: &mut Vec<u8>) {
    let mut chunks = ciphertext.chunks_exact(RATE_A);
    for blk in &mut chunks {
        let c0 = load_u64_be(&blk[0..8]);
        let c1 = load_u64_be(&blk[8..16]);
        let p0 = s[0] ^ c0;
        let p1 = s[1] ^ c1;
        out.extend_from_slice(&p0.to_be_bytes());
        out.extend_from_slice(&p1.to_be_bytes());
        s[0] = c0;
        s[1] = c1;
        permutation(s, ROUNDS_B_A);
    }
    let rem = chunks.remainder();
    if !rem.is_empty() {
        let mut state_bytes = [0u8; 16];
        state_bytes[0..8].copy_from_slice(&s[0].to_be_bytes());
        state_bytes[8..16].copy_from_slice(&s[1].to_be_bytes());
        let mut p = [0u8; 16];
        for i in 0..rem.len() {
            p[i] = state_bytes[i] ^ rem[i];
        }
        out.extend_from_slice(&p[..rem.len()]);

        // Reconstruct the rate words: ciphertext bytes for positions <rem.len(),
        // keep the original state byte at exactly rem.len() XOR 0x80, then
        // state bytes for the rest.
        let mut new_rate = [0u8; 16];
        new_rate[..rem.len()].copy_from_slice(rem);
        new_rate[rem.len()..].copy_from_slice(&state_bytes[rem.len()..]);
        new_rate[rem.len()] ^= 0x80;
        s[0] = u64::from_be_bytes(new_rate[0..8].try_into().unwrap());
        s[1] = u64::from_be_bytes(new_rate[8..16].try_into().unwrap());
    } else {
        // Exact-multiple: pad-only block.
        s[0] ^= 0x8000000000000000u64;
    }
}

/// Finalize for Ascon-128a: K is absorbed into x2‖x3 (one word later
/// than Ascon-128 since the rate is wider).  Tag = (x3‖x4) ⊕ K.
fn finalize_a(s: &mut [u64; 5], k0: u64, k1: u64) -> [u8; 16] {
    s[2] ^= k0;
    s[3] ^= k1;
    permutation(s, ROUNDS_A);
    let t0 = s[3] ^ k0;
    let t1 = s[4] ^ k1;
    let mut tag = [0u8; 16];
    tag[0..8].copy_from_slice(&t0.to_be_bytes());
    tag[8..16].copy_from_slice(&t1.to_be_bytes());
    tag
}

/// **Ascon-128a encrypt** — 128-bit rate, 8-round p^b variant.  Returns
/// `ciphertext || 16-byte tag`.
pub fn ascon128a_encrypt(
    key: &[u8; 16],
    nonce: &[u8; 16],
    aad: &[u8],
    plaintext: &[u8],
) -> Vec<u8> {
    let (mut s, k0, k1) = init_state_a(key, nonce);
    absorb_aad_a(&mut s, aad);
    let mut out = Vec::with_capacity(plaintext.len() + 16);
    encrypt_stream_a(&mut s, plaintext, &mut out);
    let tag = finalize_a(&mut s, k0, k1);
    out.extend_from_slice(&tag);
    out
}

/// **Ascon-128a decrypt + verify**.
pub fn ascon128a_decrypt(
    key: &[u8; 16],
    nonce: &[u8; 16],
    aad: &[u8],
    ciphertext_and_tag: &[u8],
) -> Option<Vec<u8>> {
    if ciphertext_and_tag.len() < 16 {
        return None;
    }
    let (ciphertext, tag_bytes) = ciphertext_and_tag.split_at(ciphertext_and_tag.len() - 16);
    let (mut s, k0, k1) = init_state_a(key, nonce);
    absorb_aad_a(&mut s, aad);
    let mut out = Vec::with_capacity(ciphertext.len());
    decrypt_stream_a(&mut s, ciphertext, &mut out);
    let expected = finalize_a(&mut s, k0, k1);
    if expected.ct_eq(tag_bytes).unwrap_u8() != 1 {
        return None;
    }
    Some(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn h(s: &str) -> Vec<u8> {
        hex::decode(s).unwrap()
    }

    fn k16(s: &str) -> [u8; 16] {
        h(s).try_into().unwrap()
    }

    /// **Vector 1** (pyascon reference): empty PT, empty AD.
    /// `Key = Nonce = 000102…0F`; expected output is the bare 16-byte tag.
    #[test]
    fn ascon128_vector_empty() {
        let key = k16("000102030405060708090A0B0C0D0E0F");
        let nonce = k16("000102030405060708090A0B0C0D0E0F");
        let ct = ascon128_encrypt(&key, &nonce, b"", b"");
        assert_eq!(ct, h("E355159F292911F794CB1432A0103A8A"));
    }

    /// **Vector 2** (pyascon reference): AD = 8 bytes, PT = 10 bytes
    /// (exact-rate AD + partial-rate PT).
    #[test]
    fn ascon128_vector_aad_and_pt() {
        let key = k16("000102030405060708090A0B0C0D0E0F");
        let nonce = k16("000102030405060708090A0B0C0D0E0F");
        let aad = h("0001020304050607");
        let pt = h("00010203040506070809");
        let ct = ascon128_encrypt(&key, &nonce, &aad, &pt);
        assert_eq!(
            ct,
            h("69FFEE6F5505A4897E2EC93B4AF37A996A1CDCDD047F83D55553")
        );
    }

    /// **Vector 3**: no AD, exact-multiple PT (24 bytes = 3 full rate blocks).
    /// Exercises the "no permutation after final block" rule and the
    /// pad-only block handling on decrypt.
    #[test]
    fn ascon128_vector_no_aad_exact_blocks() {
        let key = k16("000102030405060708090A0B0C0D0E0F");
        let nonce = k16("000102030405060708090A0B0C0D0E0F");
        let pt = h("000102030405060708090A0B0C0D0E0F1011121314151617");
        let ct = ascon128_encrypt(&key, &nonce, b"", &pt);
        assert_eq!(
            ct,
            h("BC820DBDF7A4631C5B29884AD69175C3389655CA8135C9E6576F4D9312543671819CBE00BFF09ED5")
        );
    }

    /// **Vector 4**: 16-byte AD (exact 2 rate blocks), empty PT.
    #[test]
    fn ascon128_vector_aad_only() {
        let key = k16("000102030405060708090A0B0C0D0E0F");
        let nonce = k16("000102030405060708090A0B0C0D0E0F");
        let aad = h("000102030405060708090A0B0C0D0E0F");
        let ct = ascon128_encrypt(&key, &nonce, &aad, b"");
        assert_eq!(ct, h("EF5763E75FE32F96D7863410FF0B4786"));
    }

    /// **Vector 5**: longer ASCII plaintext + 6-byte AD.
    #[test]
    fn ascon128_vector_long_message() {
        let key = k16("000102030405060708090A0B0C0D0E0F");
        let nonce = k16("000102030405060708090A0B0C0D0E0F");
        let aad = b"header";
        let pt = b"Hello, Ascon-128! This is a longer test message.";
        let ct = ascon128_encrypt(&key, &nonce, aad, pt);
        assert_eq!(
            ct,
            h("A4C01F99ACE086D3C4DB4D3B14FA067ED744321E2975573023FE4F5AFC6B9B8C5014E514EBB69E38FB46489BE98B0DE3856E67625361501A9929787F5D2A21D7")
        );
    }

    /// Decrypt every encryption vector and confirm the plaintext round-trips.
    #[test]
    fn ascon128_decrypt_vectors_roundtrip() {
        let key = k16("000102030405060708090A0B0C0D0E0F");
        let nonce = k16("000102030405060708090A0B0C0D0E0F");
        let cases: &[(&[u8], &[u8])] = &[
            (b"", b""),
            (b"\x00\x01\x02\x03\x04\x05\x06\x07", b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09"),
            (b"", b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0A\x0B\x0C\x0D\x0E\x0F\x10\x11\x12\x13\x14\x15\x16\x17"),
            (b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0A\x0B\x0C\x0D\x0E\x0F", b""),
            (b"header", b"Hello, Ascon-128! This is a longer test message."),
        ];
        for (aad, pt) in cases {
            let ct = ascon128_encrypt(&key, &nonce, aad, pt);
            let dec = ascon128_decrypt(&key, &nonce, aad, &ct).expect("tag verified");
            assert_eq!(&dec, pt);
        }
    }

    /// Random round-trips across lengths spanning rate-boundary edges.
    #[test]
    fn ascon128_roundtrip_random_lengths() {
        let key = [0x42u8; 16];
        let nonce = [0x07u8; 16];
        for len in [0usize, 1, 7, 8, 9, 15, 16, 17, 23, 24, 25, 63, 64, 65, 200] {
            let pt: Vec<u8> = (0..len).map(|i| (i as u8).wrapping_mul(31)).collect();
            let aad: Vec<u8> = (0..(len % 17))
                .map(|i| (i as u8).wrapping_mul(17))
                .collect();
            let ct = ascon128_encrypt(&key, &nonce, &aad, &pt);
            assert_eq!(ct.len(), pt.len() + 16);
            let dec = ascon128_decrypt(&key, &nonce, &aad, &ct).expect("roundtrip tag verified");
            assert_eq!(dec, pt, "roundtrip failed at len={}", len);
        }
    }

    #[test]
    fn ascon128_tamper_ciphertext_fails() {
        let key = [0x42u8; 16];
        let nonce = [0u8; 16];
        let mut ct = ascon128_encrypt(&key, &nonce, b"", b"secret payload");
        ct[0] ^= 0xff;
        assert!(ascon128_decrypt(&key, &nonce, b"", &ct).is_none());
    }

    #[test]
    fn ascon128_tamper_tag_fails() {
        let key = [0x42u8; 16];
        let nonce = [0u8; 16];
        let mut ct = ascon128_encrypt(&key, &nonce, b"aad", b"secret");
        let last = ct.len() - 1;
        ct[last] ^= 0x01;
        assert!(ascon128_decrypt(&key, &nonce, b"aad", &ct).is_none());
    }

    #[test]
    fn ascon128_tamper_aad_fails() {
        let key = [0x42u8; 16];
        let nonce = [0u8; 16];
        let ct = ascon128_encrypt(&key, &nonce, b"original-aad", b"data");
        assert!(ascon128_decrypt(&key, &nonce, b"different-aad", &ct).is_none());
    }

    #[test]
    fn ascon128_short_input_fails() {
        let key = [0u8; 16];
        let nonce = [0u8; 16];
        assert!(ascon128_decrypt(&key, &nonce, b"", &[0u8; 8]).is_none());
    }

    // ── Ascon-128a KATs cross-checked against `ascon` PyPI reference ─

    fn key_nonce_seq() -> ([u8; 16], [u8; 16]) {
        let mut k = [0u8; 16];
        let mut n = [0u8; 16];
        for i in 0..16 {
            k[i] = i as u8;
            n[i] = i as u8;
        }
        (k, n)
    }

    /// Ascon-128a, empty AAD, empty plaintext.  Verified against
    /// pyca's `ascon` package (variant="Ascon-128a") with
    /// key = nonce = 00 01 .. 0f.
    #[test]
    fn ascon128a_empty() {
        let (key, nonce) = key_nonce_seq();
        let out = ascon128a_encrypt(&key, &nonce, b"", b"");
        assert_eq!(&out[..], &h("7a834e6f09210957067b10fd831f0078")[..]);
        let pt = ascon128a_decrypt(&key, &nonce, b"", &out).expect("decrypt");
        assert!(pt.is_empty());
    }

    /// AAD-only (3-byte AAD, empty PT).
    #[test]
    fn ascon128a_aad_only() {
        let (key, nonce) = key_nonce_seq();
        let out = ascon128a_encrypt(&key, &nonce, b"AD!", b"");
        assert_eq!(&out[..], &h("6c909bd0013cd15c94b5ee62ed727897")[..]);
        assert!(ascon128a_decrypt(&key, &nonce, b"AD!", &out)
            .unwrap()
            .is_empty());
    }

    /// Empty AAD, 7-byte plaintext (partial rate block).
    #[test]
    fn ascon128a_pt_only_partial() {
        let (key, nonce) = key_nonce_seq();
        let out = ascon128a_encrypt(&key, &nonce, b"", b"PT data");
        assert_eq!(
            &out[..],
            &h("3e1c2e99b0c23324268fb53d1281569009e6092ac2b57f")[..]
        );
        let pt = ascon128a_decrypt(&key, &nonce, b"", &out).expect("decrypt");
        assert_eq!(pt, b"PT data");
    }

    /// Both AAD and a longer plaintext that spans multiple rate blocks.
    #[test]
    fn ascon128a_aad_and_long_pt() {
        let (key, nonce) = key_nonce_seq();
        let pt = b"the plaintext is longer than 16 bytes here yo!";
        let out = ascon128a_encrypt(&key, &nonce, b"associated", pt);
        let expected = h(
            "ddfe7d99790ba4d3faa5e8f6bf48534c37ecf6e5c486741adec01d8468e1ac\
             772a9f386b411a58e54da8a1f5a441785e7005c65a5749558764afa11c4ff1",
        );
        assert_eq!(&out[..], &expected[..]);
        let recovered = ascon128a_decrypt(&key, &nonce, b"associated", &out).expect("decrypt");
        assert_eq!(recovered, pt);
    }

    /// Tamper detection for Ascon-128a.
    #[test]
    fn ascon128a_tamper_fails() {
        let (key, nonce) = key_nonce_seq();
        let ct = ascon128a_encrypt(&key, &nonce, b"aad", b"plaintext");
        // CT tamper.
        let mut t = ct.clone();
        t[0] ^= 1;
        assert!(ascon128a_decrypt(&key, &nonce, b"aad", &t).is_none());
        // Tag tamper.
        let mut t = ct.clone();
        let last = t.len() - 1;
        t[last] ^= 1;
        assert!(ascon128a_decrypt(&key, &nonce, b"aad", &t).is_none());
        // AAD tamper.
        assert!(ascon128a_decrypt(&key, &nonce, b"AAD", &ct).is_none());
    }
}
