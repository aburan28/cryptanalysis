//! AES (Advanced Encryption Standard) — FIPS 197, implemented from scratch.
//!
//! Supports AES-128 and AES-256 block encryption/decryption.
//! CTR streaming mode is built on top of the block cipher.
//! GCM authenticated encryption is provided via GHASH over GF(2¹²⁸).
//!
//! # Round structure
//! Each round applies four transformations to a 4×4 byte state:
//!   SubBytes  — non-linear byte substitution via S-box (built from GF(2⁸) inverse + affine map).
//!   ShiftRows — cyclic rotation of each row by its index.
//!   MixColumns — GF(2⁸) matrix multiply of each column (skipped in the final round).
//!   AddRoundKey — XOR with the round key derived by the key schedule.

// ── S-box / inverse S-box ────────────────────────────────────────────────────

#[rustfmt::skip]
const SBOX: [u8; 256] = [
    0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
    0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
    0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
    0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
    0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
    0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
    0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
    0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
    0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
    0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
    0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
    0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
    0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
    0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
    0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
    0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16,
];

#[rustfmt::skip]
const INV_SBOX: [u8; 256] = [
    0x52,0x09,0x6a,0xd5,0x30,0x36,0xa5,0x38,0xbf,0x40,0xa3,0x9e,0x81,0xf3,0xd7,0xfb,
    0x7c,0xe3,0x39,0x82,0x9b,0x2f,0xff,0x87,0x34,0x8e,0x43,0x44,0xc4,0xde,0xe9,0xcb,
    0x54,0x7b,0x94,0x32,0xa6,0xc2,0x23,0x3d,0xee,0x4c,0x95,0x0b,0x42,0xfa,0xc3,0x4e,
    0x08,0x2e,0xa1,0x66,0x28,0xd9,0x24,0xb2,0x76,0x5b,0xa2,0x49,0x6d,0x8b,0xd1,0x25,
    0x72,0xf8,0xf6,0x64,0x86,0x68,0x98,0x16,0xd4,0xa4,0x5c,0xcc,0x5d,0x65,0xb6,0x92,
    0x6c,0x70,0x48,0x50,0xfd,0xed,0xb9,0xda,0x5e,0x15,0x46,0x57,0xa7,0x8d,0x9d,0x84,
    0x90,0xd8,0xab,0x00,0x8c,0xbc,0xd3,0x0a,0xf7,0xe4,0x58,0x05,0xb8,0xb3,0x45,0x06,
    0xd0,0x2c,0x1e,0x8f,0xca,0x3f,0x0f,0x02,0xc1,0xaf,0xbd,0x03,0x01,0x13,0x8a,0x6b,
    0x3a,0x91,0x11,0x41,0x4f,0x67,0xdc,0xea,0x97,0xf2,0xcf,0xce,0xf0,0xb4,0xe6,0x73,
    0x96,0xac,0x74,0x22,0xe7,0xad,0x35,0x85,0xe2,0xf9,0x37,0xe8,0x1c,0x75,0xdf,0x6e,
    0x47,0xf1,0x1a,0x71,0x1d,0x29,0xc5,0x89,0x6f,0xb7,0x62,0x0e,0xaa,0x18,0xbe,0x1b,
    0xfc,0x56,0x3e,0x4b,0xc6,0xd2,0x79,0x20,0x9a,0xdb,0xc0,0xfe,0x78,0xcd,0x5a,0xf4,
    0x1f,0xdd,0xa8,0x33,0x88,0x07,0xc7,0x31,0xb1,0x12,0x10,0x59,0x27,0x80,0xec,0x5f,
    0x60,0x51,0x7f,0xa9,0x19,0xb5,0x4a,0x0d,0x2d,0xe5,0x7a,0x9f,0x93,0xc9,0x9c,0xef,
    0xa0,0xe0,0x3b,0x4d,0xae,0x2a,0xf5,0xb0,0xc8,0xeb,0xbb,0x3c,0x83,0x53,0x99,0x61,
    0x17,0x2b,0x04,0x7e,0xba,0x77,0xd6,0x26,0xe1,0x69,0x14,0x63,0x55,0x21,0x0c,0x7d,
];

// Round constant (Rcon) for key schedule — powers of 2 in GF(2⁸).
const RCON: [u8; 11] = [
    0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1b, 0x36,
];

// ── GF(2⁸) arithmetic ────────────────────────────────────────────────────────

/// Branchless multiplication in GF(2⁸).  The peasant-multiply loop always
/// runs eight iterations and uses bit-mask arithmetic instead of `if`
/// branches on secret bits, so the runtime and memory access pattern do
/// not depend on the operand values.
fn gmul(mut a: u8, mut b: u8) -> u8 {
    let mut p = 0u8;
    for _ in 0..8 {
        // p ^= a iff lsb(b) == 1   →  build a 0xFF/0x00 mask from that bit
        let bit_mask = 0u8.wrapping_sub(b & 1);
        p ^= a & bit_mask;
        // a = (a << 1) XOR 0x1b iff msb(a) was 1
        let hi_mask = 0u8.wrapping_sub(a >> 7);
        a = (a << 1) ^ (0x1b & hi_mask);
        b >>= 1;
    }
    p
}

// ── Constant-time S-box / inverse S-box ──────────────────────────────────────
//
// Cache-timing attacks against table-driven AES (Bernstein 2005,
// Osvik–Shamir–Tromer 2006) exploit the fact that a 256-byte lookup
// table spans multiple cache lines: which line is touched leaks the
// upper bits of the secret index.
//
// We close that channel by scanning the full table on every byte
// substitution: the same 256 reads happen regardless of the input, and
// the matching entry is selected via `subtle::ConditionallySelectable`,
// which uses optimisation-resistant primitives the compiler must not
// rewrite into a data-dependent branch.  This costs ~256× per S-box
// call vs. the direct lookup, which is acceptable for everything
// except bulk-throughput symmetric encryption.  Bulk users on hardware
// with AES-NI should call into the hardware path; we don't have one
// here.

fn sbox_ct(x: u8) -> u8 {
    use subtle::{ConditionallySelectable, ConstantTimeEq};
    let mut result: u8 = 0;
    for i in 0u16..256 {
        let candidate = SBOX[i as usize];
        let choice = (i as u8).ct_eq(&x);
        result = u8::conditional_select(&result, &candidate, choice);
    }
    result
}

fn inv_sbox_ct(x: u8) -> u8 {
    use subtle::{ConditionallySelectable, ConstantTimeEq};
    let mut result: u8 = 0;
    for i in 0u16..256 {
        let candidate = INV_SBOX[i as usize];
        let choice = (i as u8).ct_eq(&x);
        result = u8::conditional_select(&result, &candidate, choice);
    }
    result
}

// ── AES key types ─────────────────────────────────────────────────────────────

/// AES key variants.
pub enum AesKey {
    Aes128([u8; 16]),
    Aes256([u8; 32]),
}

impl AesKey {
    pub fn key_len(&self) -> usize {
        match self {
            AesKey::Aes128(_) => 16,
            AesKey::Aes256(_) => 32,
        }
    }
    pub fn nk(&self) -> usize {
        self.key_len() / 4
    }
    pub fn nr(&self) -> usize {
        self.nk() + 6
    }
    pub fn as_bytes(&self) -> &[u8] {
        match self {
            AesKey::Aes128(k) => k,
            AesKey::Aes256(k) => k,
        }
    }

    /// Construct an `AesKey` from a raw byte slice.  Accepts 16 (AES-128)
    /// or 32 (AES-256) bytes; returns `Err` for any other length.
    /// AES-192 is intentionally not supported (24-byte variant has no
    /// strong reason to ship at the educational scale).
    pub fn new(bytes: &[u8]) -> Result<Self, &'static str> {
        match bytes.len() {
            16 => {
                let mut k = [0u8; 16];
                k.copy_from_slice(bytes);
                Ok(AesKey::Aes128(k))
            }
            32 => {
                let mut k = [0u8; 32];
                k.copy_from_slice(bytes);
                Ok(AesKey::Aes256(k))
            }
            _ => Err("AES key must be 16 or 32 bytes"),
        }
    }
}

// ── Key expansion ─────────────────────────────────────────────────────────────

/// Expand a key into the full round key schedule (Nb*(Nr+1) words = 4*(Nr+1) 32-bit words).
pub fn key_expansion(key: &AesKey) -> Vec<[u8; 4]> {
    let nk = key.nk();
    let nr = key.nr();
    let total = 4 * (nr + 1);
    let mut w: Vec<[u8; 4]> = Vec::with_capacity(total);
    let k = key.as_bytes();

    for i in 0..nk {
        w.push([k[4 * i], k[4 * i + 1], k[4 * i + 2], k[4 * i + 3]]);
    }

    for i in nk..total {
        let mut temp = w[i - 1];
        if i % nk == 0 {
            temp = sub_word(rot_word(temp));
            temp[0] ^= RCON[i / nk];
        } else if nk > 6 && i % nk == 4 {
            temp = sub_word(temp);
        }
        let prev = w[i - nk];
        w.push([
            prev[0] ^ temp[0],
            prev[1] ^ temp[1],
            prev[2] ^ temp[2],
            prev[3] ^ temp[3],
        ]);
    }
    w
}

fn rot_word(w: [u8; 4]) -> [u8; 4] {
    [w[1], w[2], w[3], w[0]]
}
fn sub_word(w: [u8; 4]) -> [u8; 4] {
    [sbox_ct(w[0]), sbox_ct(w[1]), sbox_ct(w[2]), sbox_ct(w[3])]
}

// ── State helpers ─────────────────────────────────────────────────────────────

/// AES state: 4×4 bytes, stored column-major.
type State = [[u8; 4]; 4];

fn bytes_to_state(block: &[u8]) -> State {
    let mut s = [[0u8; 4]; 4];
    for c in 0..4 {
        for r in 0..4 {
            s[c][r] = block[c * 4 + r];
        }
    }
    s
}

fn state_to_bytes(s: &State) -> [u8; 16] {
    let mut out = [0u8; 16];
    for c in 0..4 {
        for r in 0..4 {
            out[c * 4 + r] = s[c][r];
        }
    }
    out
}

fn add_round_key(s: &mut State, round_key: &[[u8; 4]]) {
    for c in 0..4 {
        for r in 0..4 {
            s[c][r] ^= round_key[c][r];
        }
    }
}

// ── Forward transformations ───────────────────────────────────────────────────

fn sub_bytes(s: &mut State) {
    for col in s.iter_mut() {
        for b in col.iter_mut() {
            *b = sbox_ct(*b);
        }
    }
}

fn shift_rows(s: &mut State) {
    // Row 0: no shift. Row 1: shift left 1. Row 2: shift left 2. Row 3: shift left 3.
    let r1 = [s[1][1], s[2][1], s[3][1], s[0][1]];
    let r2 = [s[2][2], s[3][2], s[0][2], s[1][2]];
    let r3 = [s[3][3], s[0][3], s[1][3], s[2][3]];
    for c in 0..4 {
        s[c][1] = r1[c];
        s[c][2] = r2[c];
        s[c][3] = r3[c];
    }
}

fn mix_columns(s: &mut State) {
    for c in 0..4 {
        let a = s[c];
        s[c][0] = gmul(0x02, a[0]) ^ gmul(0x03, a[1]) ^ a[2] ^ a[3];
        s[c][1] = a[0] ^ gmul(0x02, a[1]) ^ gmul(0x03, a[2]) ^ a[3];
        s[c][2] = a[0] ^ a[1] ^ gmul(0x02, a[2]) ^ gmul(0x03, a[3]);
        s[c][3] = gmul(0x03, a[0]) ^ a[1] ^ a[2] ^ gmul(0x02, a[3]);
    }
}

// ── Inverse transformations ───────────────────────────────────────────────────

fn inv_sub_bytes(s: &mut State) {
    for col in s.iter_mut() {
        for b in col.iter_mut() {
            *b = inv_sbox_ct(*b);
        }
    }
}

fn inv_shift_rows(s: &mut State) {
    let r1 = [s[3][1], s[0][1], s[1][1], s[2][1]];
    let r2 = [s[2][2], s[3][2], s[0][2], s[1][2]];
    let r3 = [s[1][3], s[2][3], s[3][3], s[0][3]];
    for c in 0..4 {
        s[c][1] = r1[c];
        s[c][2] = r2[c];
        s[c][3] = r3[c];
    }
}

fn inv_mix_columns(s: &mut State) {
    for c in 0..4 {
        let a = s[c];
        s[c][0] = gmul(0x0e, a[0]) ^ gmul(0x0b, a[1]) ^ gmul(0x0d, a[2]) ^ gmul(0x09, a[3]);
        s[c][1] = gmul(0x09, a[0]) ^ gmul(0x0e, a[1]) ^ gmul(0x0b, a[2]) ^ gmul(0x0d, a[3]);
        s[c][2] = gmul(0x0d, a[0]) ^ gmul(0x09, a[1]) ^ gmul(0x0e, a[2]) ^ gmul(0x0b, a[3]);
        s[c][3] = gmul(0x0b, a[0]) ^ gmul(0x0d, a[1]) ^ gmul(0x09, a[2]) ^ gmul(0x0e, a[3]);
    }
}

// ── Block encrypt / decrypt ───────────────────────────────────────────────────

/// Encrypt a single 16-byte block with `key`.
pub fn encrypt_block(block: &[u8; 16], key: &AesKey) -> [u8; 16] {
    let nr = key.nr();
    let w = key_expansion(key);
    let mut s = bytes_to_state(block);

    add_round_key(&mut s, &w[..4]);

    for round in 1..nr {
        sub_bytes(&mut s);
        shift_rows(&mut s);
        mix_columns(&mut s);
        add_round_key(&mut s, &w[round * 4..(round + 1) * 4]);
    }

    // Final round (no MixColumns)
    sub_bytes(&mut s);
    shift_rows(&mut s);
    add_round_key(&mut s, &w[nr * 4..(nr + 1) * 4]);

    state_to_bytes(&s)
}

/// Decrypt a single 16-byte block.
pub fn decrypt_block(block: &[u8; 16], key: &AesKey) -> [u8; 16] {
    let nr = key.nr();
    let w = key_expansion(key);
    let mut s = bytes_to_state(block);

    add_round_key(&mut s, &w[nr * 4..(nr + 1) * 4]);

    for round in (1..nr).rev() {
        inv_shift_rows(&mut s);
        inv_sub_bytes(&mut s);
        add_round_key(&mut s, &w[round * 4..(round + 1) * 4]);
        inv_mix_columns(&mut s);
    }

    inv_shift_rows(&mut s);
    inv_sub_bytes(&mut s);
    add_round_key(&mut s, &w[..4]);

    state_to_bytes(&s)
}

// ── CTR mode ─────────────────────────────────────────────────────────────────

/// AES-CTR encryption/decryption (symmetric operation).
///
/// Counter block layout: `nonce` (12 bytes) || counter (4 bytes, big-endian).
/// The counter starts at 1 (matching RFC 3686).
pub fn aes_ctr(data: &[u8], key: &AesKey, nonce: &[u8; 12]) -> Vec<u8> {
    aes_ctr_checked(data, key, nonce).expect("AES-CTR counter would wrap")
}

/// Checked AES-CTR encryption/decryption.
///
/// Returns an error if processing `data` would wrap the 32-bit counter field.
pub fn aes_ctr_checked(
    data: &[u8],
    key: &AesKey,
    nonce: &[u8; 12],
) -> Result<Vec<u8>, &'static str> {
    aes_ctr_from_checked(data, key, nonce, 1)
}

/// AES-CTR with explicit starting counter. Used by GCM (which needs counter=2
/// because counter=1 is consumed by J₀ for tag derivation).
fn aes_ctr_from(data: &[u8], key: &AesKey, nonce: &[u8; 12], start: u32) -> Vec<u8> {
    aes_ctr_from_checked(data, key, nonce, start).expect("AES-CTR counter would wrap")
}

fn aes_ctr_from_checked(
    data: &[u8],
    key: &AesKey,
    nonce: &[u8; 12],
    start: u32,
) -> Result<Vec<u8>, &'static str> {
    ensure_ctr_capacity(data.len(), start)?;
    let mut out = data.to_vec();
    let mut counter = start;

    for chunk in out.chunks_mut(16) {
        let mut ctr_block = [0u8; 16];
        ctr_block[..12].copy_from_slice(nonce);
        ctr_block[12..].copy_from_slice(&counter.to_be_bytes());

        let keystream = encrypt_block(&ctr_block, key);
        for (b, k) in chunk.iter_mut().zip(keystream.iter()) {
            *b ^= k;
        }
        counter = counter.wrapping_add(1);
    }
    Ok(out)
}

pub fn aes_ctr_len_fits(len: usize, start: u32) -> bool {
    ensure_ctr_capacity(len, start).is_ok()
}

fn ensure_ctr_capacity(len: usize, start: u32) -> Result<(), &'static str> {
    let blocks = len.checked_add(15).ok_or("AES-CTR input length overflow")? / 16;
    let available = (u32::MAX as u64) - (start as u64) + 1;
    if (blocks as u64) > available {
        Err("AES-CTR counter would wrap")
    } else {
        Ok(())
    }
}

// ── GCM (GHASH + CTR) ─────────────────────────────────────────────────────────

/// Multiply two 128-bit values in GF(2¹²⁸) with the GCM modulus.
/// GCM uses the "bit-reflected" representation; the modulus is x¹²⁸+x⁷+x²+x+1.
fn gcm_mult(x: &[u8; 16], y: &[u8; 16]) -> [u8; 16] {
    let mut z = [0u8; 16];
    let mut v = *y;

    for i in 0..16 {
        for bit in (0..8).rev() {
            if (x[i] >> bit) & 1 == 1 {
                for j in 0..16 {
                    z[j] ^= v[j];
                }
            }
            let lsb = v[15] & 1;
            // Right-shift v by 1 bit
            for j in (1..16).rev() {
                v[j] = (v[j] >> 1) | (v[j - 1] << 7);
            }
            v[0] >>= 1;
            // Reduce mod the GCM polynomial if the shifted-out bit was 1
            if lsb == 1 {
                v[0] ^= 0xe1;
            }
        }
    }
    z
}

/// GHASH: authenticate `data` using hash key `h`, returning a 16-byte tag.
fn ghash(h: &[u8; 16], aad: &[u8], ciphertext: &[u8]) -> [u8; 16] {
    let mut y = [0u8; 16];

    // Process AAD padded to 16-byte boundary. Empty AAD contributes no block.
    for block in padded_blocks(aad) {
        xor_into(&mut y, &block);
        y = gcm_mult(&y, h);
    }

    // Process ciphertext. Empty ciphertext contributes no block.
    for block in padded_blocks(ciphertext) {
        xor_into(&mut y, &block);
        y = gcm_mult(&y, h);
    }

    // Length block: len(AAD)||len(ciphertext) in bits, each 64-bit big-endian
    let mut len_block = [0u8; 16];
    len_block[..8].copy_from_slice(&((aad.len() as u64 * 8).to_be_bytes()));
    len_block[8..].copy_from_slice(&((ciphertext.len() as u64 * 8).to_be_bytes()));
    xor_into(&mut y, &len_block);
    y = gcm_mult(&y, h);

    y
}

fn padded_blocks(data: &[u8]) -> Vec<[u8; 16]> {
    if data.is_empty() {
        return Vec::new();
    }
    let mut out = Vec::with_capacity(data.len().div_ceil(16));
    for chunk in data.chunks(16) {
        let mut block = [0u8; 16];
        block[..chunk.len()].copy_from_slice(chunk);
        out.push(block);
    }
    out
}

fn xor_into(dst: &mut [u8; 16], src: &[u8]) {
    for (a, b) in dst.iter_mut().zip(src.iter()) {
        *a ^= b;
    }
}

/// AES-GCM encrypt. Returns `ciphertext || 16-byte tag`.
///
/// `key`:   AES-128 or AES-256 key.
/// `nonce`: 12-byte IV (use a unique value for each message).
/// `aad`:   Additional Authenticated Data (not encrypted, but authenticated).
pub fn aes_gcm_encrypt(plaintext: &[u8], key: &AesKey, nonce: &[u8; 12], aad: &[u8]) -> Vec<u8> {
    // Derive GHASH key H = E(K, 0¹²⁸)
    let h: [u8; 16] = encrypt_block(&[0u8; 16], key);

    // Encrypt plaintext with CTR starting at J₀ + 1 = 2 (96-bit IV case).
    // Counter 1 (= J₀) is reserved for tag derivation in `encrypt_j0`.
    let ciphertext = aes_ctr_from(plaintext, key, nonce, 2);

    // Compute tag: GHASH(H, AAD, CT) XOR E(K, J₀)
    let mut tag = ghash(&h, aad, &ciphertext);
    let j0 = encrypt_j0(key, nonce);
    for (t, j) in tag.iter_mut().zip(j0.iter()) {
        *t ^= j;
    }

    let mut out = ciphertext;
    out.extend_from_slice(&tag);
    out
}

/// AES-GCM decrypt. Returns the plaintext if the tag verifies, `None` otherwise.
pub fn aes_gcm_decrypt(
    ciphertext_and_tag: &[u8],
    key: &AesKey,
    nonce: &[u8; 12],
    aad: &[u8],
) -> Option<Vec<u8>> {
    if ciphertext_and_tag.len() < 16 {
        return None;
    }
    let (ciphertext, tag_bytes) = ciphertext_and_tag.split_at(ciphertext_and_tag.len() - 16);

    let h: [u8; 16] = encrypt_block(&[0u8; 16], key);
    let mut expected_tag = ghash(&h, aad, ciphertext);
    let j0 = encrypt_j0(key, nonce);
    for (t, j) in expected_tag.iter_mut().zip(j0.iter()) {
        *t ^= j;
    }

    // Constant-time tag comparison via `subtle::ConstantTimeEq` to defeat
    // timing side-channels.  A hand-rolled XOR-fold compiles to constant
    // time today but the compiler is permitted to introduce branches; the
    // `subtle` crate uses optimisation-resistant primitives (volatile reads,
    // `core::hint::black_box`-style barriers) to keep the comparison safe
    // across compiler versions and optimisation levels.
    use subtle::ConstantTimeEq;
    if expected_tag.ct_eq(tag_bytes).unwrap_u8() != 1 {
        return None;
    }

    // Decrypt plaintext with CTR starting at counter=2 (J₀ + 1).
    Some(aes_ctr_from(ciphertext, key, nonce, 2))
}

/// Encrypt the J₀ counter block (nonce || 0x00000001) for the authentication tag.
fn encrypt_j0(key: &AesKey, nonce: &[u8; 12]) -> [u8; 16] {
    let mut j0 = [0u8; 16];
    j0[..12].copy_from_slice(nonce);
    j0[15] = 1;
    encrypt_block(&j0, key)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn h(s: &str) -> Vec<u8> {
        hex::decode(s).unwrap()
    }

    // ── AES-128 single-block KAT (FIPS 197 §B / Appendix C.1) ────────────────

    #[test]
    fn aes128_fips197_appendix_b() {
        let key = AesKey::Aes128(h("2b7e151628aed2a6abf7158809cf4f3c").try_into().unwrap());
        let pt: [u8; 16] = h("3243f6a8885a308d313198a2e0370734").try_into().unwrap();
        let ct = encrypt_block(&pt, &key);
        assert_eq!(&ct, h("3925841d02dc09fbdc118597196a0b32").as_slice());
        assert_eq!(decrypt_block(&ct, &key), pt);
    }

    #[test]
    fn aes128_fips197_appendix_c1() {
        // FIPS 197 §C.1
        let key = AesKey::Aes128(h("000102030405060708090a0b0c0d0e0f").try_into().unwrap());
        let pt: [u8; 16] = h("00112233445566778899aabbccddeeff").try_into().unwrap();
        let ct = encrypt_block(&pt, &key);
        assert_eq!(&ct, h("69c4e0d86a7b0430d8cdb78070b4c55a").as_slice());
        assert_eq!(decrypt_block(&ct, &key), pt);
    }

    // ── AES-256 single-block KAT (FIPS 197 §C.3) ─────────────────────────────

    #[test]
    fn aes256_fips197_appendix_c3() {
        let key = AesKey::Aes256(
            h("000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f")
                .try_into()
                .unwrap(),
        );
        let pt: [u8; 16] = h("00112233445566778899aabbccddeeff").try_into().unwrap();
        let ct = encrypt_block(&pt, &key);
        assert_eq!(&ct, h("8ea2b7ca516745bfeafc49904b496089").as_slice());
        assert_eq!(decrypt_block(&ct, &key), pt);
    }

    #[test]
    fn aes_decrypt_inverse() {
        // Roundtrip AES-128 and AES-256 over many random-ish blocks.
        for seed in 0..16u8 {
            let mut k128 = [0u8; 16];
            for (i, b) in k128.iter_mut().enumerate() {
                *b = seed.wrapping_mul(i as u8 + 1);
            }
            let key128 = AesKey::Aes128(k128);
            let mut pt = [0u8; 16];
            for (i, b) in pt.iter_mut().enumerate() {
                *b = seed.wrapping_add((i * 7) as u8);
            }
            assert_eq!(decrypt_block(&encrypt_block(&pt, &key128), &key128), pt);

            let mut k256 = [0u8; 32];
            for (i, b) in k256.iter_mut().enumerate() {
                *b = seed.wrapping_mul(i as u8 + 3);
            }
            let key256 = AesKey::Aes256(k256);
            assert_eq!(decrypt_block(&encrypt_block(&pt, &key256), &key256), pt);
        }
    }

    // ── AES-CTR KAT (matches Python cryptography backend with counter starting at 1) ─

    #[test]
    fn ctr_known_answer() {
        let key = AesKey::Aes128(h("2b7e151628aed2a6abf7158809cf4f3c").try_into().unwrap());
        let nonce: [u8; 12] = h("f0f1f2f3f4f5f6f7f8f9fafb").try_into().unwrap();
        let pt = h("6bc1bee22e409f96e93d7e117393172a\
                    ae2d8a571e03ac9c9eb76fac45af8e51\
                    30c81c46a35ce411e5fbc1191a0a52ef");
        let ct = aes_ctr(&pt, &key, &nonce);
        assert_eq!(
            ct,
            h(
                "288028c71599c5a8dd53c2671b86b813ab25397ad21f8b4b94892b65cf891edd\
               d47cfd8d0ecd23a4eb8c0558454a6344"
            ),
        );
        // Roundtrip
        assert_eq!(aes_ctr(&ct, &key, &nonce), pt);
    }

    #[test]
    fn ctr_handles_partial_last_block() {
        let key = AesKey::Aes128([0u8; 16]);
        let nonce = [0u8; 12];
        // Length not a multiple of 16
        for len in [1usize, 15, 17, 31, 33, 100] {
            let pt: Vec<u8> = (0..len).map(|i| i as u8).collect();
            let ct = aes_ctr(&pt, &key, &nonce);
            assert_eq!(aes_ctr(&ct, &key, &nonce), pt, "len={}", len);
        }
    }

    #[test]
    fn ctr_rejects_counter_wrap_without_allocating() {
        let max_len = (u32::MAX as usize) * 16;
        assert!(aes_ctr_len_fits(max_len, 1));
        assert!(!aes_ctr_len_fits(max_len + 1, 1));
        assert!(aes_ctr_len_fits(16, u32::MAX));
        assert!(!aes_ctr_len_fits(17, u32::MAX));
    }

    // ── AES-GCM KATs (NIST GCM Spec test cases #1, #2) ───────────────────────

    #[test]
    fn aes128_gcm_nist_test1_empty() {
        // Test #1: zero key/IV/AAD/PT; tag-only output
        let key = AesKey::Aes128([0u8; 16]);
        let nonce = [0u8; 12];
        let out = aes_gcm_encrypt(b"", &key, &nonce, b"");
        // Output is just the 16-byte tag
        assert_eq!(out, h("58e2fccefa7e3061367f1d57a4e7455a"));
    }

    #[test]
    fn aes128_gcm_aad_only_known_answer() {
        let key = AesKey::Aes128([0u8; 16]);
        let nonce = [0u8; 12];
        let out = aes_gcm_encrypt(b"", &key, &nonce, b"aad");
        assert_eq!(out, h("5fe5978c14764479f5aba1acb37df1d8"));
        assert!(aes_gcm_decrypt(&out, &key, &nonce, b"aad")
            .unwrap()
            .is_empty());
    }

    #[test]
    fn aes128_gcm_nist_test2_one_block() {
        let key = AesKey::Aes128([0u8; 16]);
        let nonce = [0u8; 12];
        let pt = [0u8; 16];
        let out = aes_gcm_encrypt(&pt, &key, &nonce, b"");
        assert_eq!(
            out,
            h("0388dace60b6a392f328c2b971b2fe78ab6e47d42cec13bdf53a67b21257bddf"),
        );
        // Decrypt back
        let dec = aes_gcm_decrypt(&out, &key, &nonce, b"").unwrap();
        assert_eq!(dec, pt);
    }

    #[test]
    fn aes256_gcm_zeros_one_block() {
        let key = AesKey::Aes256([0u8; 32]);
        let nonce = [0u8; 12];
        let pt = [0u8; 16];
        let out = aes_gcm_encrypt(&pt, &key, &nonce, b"");
        assert_eq!(
            out,
            h("cea7403d4d606b6e074ec5d3baf39d18d0d1c8a799996bf0265b98b5d48ab919"),
        );
        let dec = aes_gcm_decrypt(&out, &key, &nonce, b"").unwrap();
        assert_eq!(dec, pt);
    }

    #[test]
    fn aes_gcm_with_aad_roundtrip() {
        let key = AesKey::Aes128([0x42u8; 16]);
        let nonce = [0x07u8; 12];
        let pt = b"authenticated payload";
        let aad = b"unencrypted-but-authenticated-header";
        let ct = aes_gcm_encrypt(pt, &key, &nonce, aad);
        assert_eq!(aes_gcm_decrypt(&ct, &key, &nonce, aad).unwrap(), pt);
    }

    #[test]
    fn aes_gcm_tamper_ciphertext_fails() {
        let key = AesKey::Aes128([0u8; 16]);
        let nonce = [0u8; 12];
        let mut ct = aes_gcm_encrypt(b"msg", &key, &nonce, b"aad");
        ct[0] ^= 0xff;
        assert!(aes_gcm_decrypt(&ct, &key, &nonce, b"aad").is_none());
    }

    #[test]
    fn aes_gcm_tamper_aad_fails() {
        let key = AesKey::Aes128([0u8; 16]);
        let nonce = [0u8; 12];
        let ct = aes_gcm_encrypt(b"data", &key, &nonce, b"original");
        assert!(aes_gcm_decrypt(&ct, &key, &nonce, b"different").is_none());
    }

    #[test]
    fn aes_gcm_tamper_tag_fails() {
        let key = AesKey::Aes128([0u8; 16]);
        let nonce = [0u8; 12];
        let mut ct = aes_gcm_encrypt(b"msg", &key, &nonce, b"");
        let last = ct.len() - 1;
        ct[last] ^= 0x01;
        assert!(aes_gcm_decrypt(&ct, &key, &nonce, b"").is_none());
    }

    #[test]
    fn aes_gcm_short_input_fails() {
        let key = AesKey::Aes128([0u8; 16]);
        let nonce = [0u8; 12];
        // Anything shorter than 16 bytes can't be a valid (CT||tag).
        assert!(aes_gcm_decrypt(&[0u8; 8], &key, &nonce, b"").is_none());
    }
}
