//! **Skein** — SHA-3 finalist (2008) by Ferguson, Lucks, Schneier,
//! Whiting, Bellare, Kohno, Callas, and Walker.  Not selected as
//! SHA-3 (Keccak won), and never received a NIST-issued FIPS, so it
//! lacks the widely-deployed standardization of SHA-2 / SHA-3 / BLAKE2.
//! Nevertheless well-studied: no break against the v1.3 design has
//! held up over a decade-plus of cryptanalysis, and it remains a
//! reasonable choice when a tweakable, parallel-friendly, ARX-only
//! hash is desired.
//!
//! # Structure
//!
//! Skein is built on top of **Threefish** (a tweakable block cipher,
//! see `crate::symmetric::threefish`) via the **UBI** (Unique Block
//! Iteration) chaining mode.  Each UBI invocation processes one
//! "type" of input (config, message, or output) under a tweak whose
//! 128 bits encode (a) byte position, (b) the block type, and
//! (c) first/final flags.  Hashing a message proceeds in three
//! phases:
//!
//! 1. **Config** — a 32-byte block encoding the schema "SHA3", the
//!    requested output length in bits, and the (trivial) tree
//!    parameters.  Processed under tweak type `CFG = 0x04`,
//!    starting from the all-zero state.
//! 2. **Message** — the input, zero-padded to a multiple of the
//!    state size.  Processed under tweak type `MSG = 0x30`.
//! 3. **Output** — UBI applied to a sequence of state-size blocks
//!    whose first 8 bytes are a little-endian counter `0, 1, 2, …`,
//!    rest zero.  Each call produces one state-size chunk of output;
//!    chunks are concatenated and truncated to the requested length.
//!    Type `OUT = 0x3F`.
//!
//! UBI itself is `G_i = E_{G_{i-1}, T_i}(M_i) XOR M_i` — Matyas–Meyer–
//! Oseas applied to Threefish, with the tweak `T_i` carrying the byte
//! position and flags.  This makes Skein a natural XOF: extending the
//! output costs only additional Threefish encryptions in OUT mode.
//!
//! # Variants
//!
//! Internal state size is configurable to match Threefish's three
//! block sizes:
//!
//! | Variant     | State (bits) | Threefish rounds |
//! |-------------|--------------|------------------|
//! | Skein-256   | 256          | 72               |
//! | Skein-512   | 512          | 72               |
//! | Skein-1024  | 1024         | 80               |
//!
//! All three expose arbitrary output length (Skein is naturally an
//! extendable-output function).
//!
//! # Test vectors
//!
//! KATs for the all-empty message at the natural output length
//! (state-size output) are taken from the Skein 1.3 NIST submission
//! package (`Skein_NIST_CD/Reference_Implementation`) — these are the
//! same bytes produced by the `pyskein` reference and the Skein team's
//! C reference, both of which descend from the v1.3 official source.

use crate::symmetric::threefish::{Threefish1024, Threefish256, Threefish512};

// ── UBI tweak helpers ───────────────────────────────────────────────────────
//
// The 128-bit tweak is laid out (LSB-first within each word) as:
//   bits   0..= 95  position (bytes processed so far, *including* this block)
//   bits  96..=111  reserved (zero)
//   bits 112..=118  tree level (0 for sequential hashing)
//   bit  119        bit-pad flag (1 iff final block had < state-size bytes of
//                                real data and was zero-padded on the byte level)
//   bits 120..=125  block type
//   bit  126        first-block flag
//   bit  127        final-block flag
//
// In little-endian serialization, the position fills the low 12 bytes of
// the 16-byte tweak; the upper 4 bytes (bits 96..127) carry the flags.

const T_CFG: u8 = 4;
const T_MSG: u8 = 48;
const T_OUT: u8 = 63;

const FLAG_FIRST: u64 = 1u64 << (126 - 64);
const FLAG_FINAL: u64 = 1u64 << (127 - 64);
const FLAG_BITPAD: u64 = 1u64 << (119 - 64);

/// Build the 16-byte tweak from byte position, block-type byte, and
/// first/final/bit-pad flags.  Position is a `u128` because it can in
/// principle exceed 2^64 bytes (the spec allots 96 bits).
fn make_tweak(position: u128, type_byte: u8, first: bool, final_: bool, bit_pad: bool) -> [u8; 16] {
    // Low 12 bytes: position.
    let pos_lo = position as u64;
    let pos_hi = ((position >> 64) as u64) & 0x0000_0000_FFFF_FFFF;
    // High 4 bytes of the upper u64 carry: type (bits 120..125), first
    // (126), final (127), and the bit-pad flag (119).
    let mut hi = pos_hi;
    hi |= (type_byte as u64) << (120 - 64);
    if first {
        hi |= FLAG_FIRST;
    }
    if final_ {
        hi |= FLAG_FINAL;
    }
    if bit_pad {
        hi |= FLAG_BITPAD;
    }
    let mut t = [0u8; 16];
    t[0..8].copy_from_slice(&pos_lo.to_le_bytes());
    t[8..16].copy_from_slice(&hi.to_le_bytes());
    t
}

// ── Per-variant UBI: Threefish-block-sized encrypt-then-XOR ─────────────────
//
// UBI step: G_i = E_{G_{i-1}, T_i}(M_i) XOR M_i.
// `state` carries G_{i-1}; we overwrite it with G_i.  Threefish's
// `encrypt` works in place on a buffer that starts as M_i.

fn ubi_block_256(state: &mut [u8; 32], msg_block: &[u8; 32], tweak: &[u8; 16]) {
    let cipher = Threefish256::new(state, tweak);
    let mut block = *msg_block;
    cipher.encrypt(&mut block);
    for i in 0..32 {
        state[i] = block[i] ^ msg_block[i];
    }
}

fn ubi_block_512(state: &mut [u8; 64], msg_block: &[u8; 64], tweak: &[u8; 16]) {
    let cipher = Threefish512::new(state, tweak);
    let mut block = *msg_block;
    cipher.encrypt(&mut block);
    for i in 0..64 {
        state[i] = block[i] ^ msg_block[i];
    }
}

fn ubi_block_1024(state: &mut [u8; 128], msg_block: &[u8; 128], tweak: &[u8; 16]) {
    let cipher = Threefish1024::new(state, tweak);
    let mut block = *msg_block;
    cipher.encrypt(&mut block);
    for i in 0..128 {
        state[i] = block[i] ^ msg_block[i];
    }
}

// ── Config block ────────────────────────────────────────────────────────────
//
// 32 bytes (Skein 1.3 §3.5.1):
//   [0..4]   schema = "SHA3" (0x53, 0x48, 0x41, 0x33)
//   [4..6]   version = 1 (LE u16)
//   [6..8]   reserved (zero)
//   [8..16]  output length in bits (LE u64)
//   [16]     tree leaf size encoding (0 for non-tree)
//   [17]     fan-out encoding (0 for non-tree)
//   [18]     max tree height (0 for non-tree)
//   [19..32] reserved (zero)

fn config_block(output_bits: u64) -> [u8; 32] {
    let mut cfg = [0u8; 32];
    cfg[0] = b'S';
    cfg[1] = b'H';
    cfg[2] = b'A';
    cfg[3] = b'3';
    cfg[4..6].copy_from_slice(&1u16.to_le_bytes());
    cfg[8..16].copy_from_slice(&output_bits.to_le_bytes());
    cfg
}

// ── Skein-256 ───────────────────────────────────────────────────────────────

/// Run one UBI pass of type `type_byte` consuming `data` (zero-padded
/// up to a multiple of 32 bytes if non-empty, or one zero block if
/// empty).  Updates `state` in place.
fn ubi_pass_256(state: &mut [u8; 32], data: &[u8], type_byte: u8) {
    let block_size = 32usize;
    let n = data.len();
    if n == 0 {
        // One all-zero block, first+final, bit_pad=false, position=0.
        // (UBI with empty input is degenerate; we never call ubi_pass
        // on an empty message in hash mode — but we keep the branch
        // for clarity.)
        let tweak = make_tweak(0, type_byte, true, true, false);
        ubi_block_256(state, &[0u8; 32], &tweak);
        return;
    }

    let mut pos = 0usize;
    let mut first = true;
    while pos + block_size < n {
        let mut block = [0u8; 32];
        block.copy_from_slice(&data[pos..pos + block_size]);
        let new_pos = pos + block_size;
        let tweak = make_tweak(new_pos as u128, type_byte, first, false, false);
        ubi_block_256(state, &block, &tweak);
        first = false;
        pos = new_pos;
    }
    // Final block: real bytes followed by zero padding (if needed).
    let remaining = n - pos;
    let mut last = [0u8; 32];
    last[..remaining].copy_from_slice(&data[pos..]);
    let tweak = make_tweak(n as u128, type_byte, first, true, false);
    ubi_block_256(state, &last, &tweak);
}

fn skein256_inner(data: &[u8], output_len: usize) -> Vec<u8> {
    let output_bits = (output_len as u64).wrapping_mul(8);
    // 1. Configuration: starts from the all-zero state.
    let mut state = [0u8; 32];
    let cfg = config_block(output_bits);
    let tweak = make_tweak(32, T_CFG, true, true, false);
    ubi_block_256(&mut state, &cfg, &tweak);

    // 2. Message.
    ubi_pass_256(&mut state, data, T_MSG);

    // 3. Output: counter blocks 0, 1, 2, ...; each is one UBI(type=OUT).
    let mut out = Vec::with_capacity(output_len);
    let mut counter: u64 = 0;
    while out.len() < output_len {
        let mut ctr_block = [0u8; 32];
        ctr_block[..8].copy_from_slice(&counter.to_le_bytes());
        let mut block_state = state;
        let tweak = make_tweak(8, T_OUT, true, true, false);
        ubi_block_256(&mut block_state, &ctr_block, &tweak);
        let take = core::cmp::min(32, output_len - out.len());
        out.extend_from_slice(&block_state[..take]);
        counter += 1;
    }
    out
}

/// Skein-256 hash: 256-bit internal state, arbitrary output length.
/// `output_len` is in bytes.
pub fn skein256(data: &[u8], output_len: usize) -> Vec<u8> {
    skein256_inner(data, output_len)
}

// ── Skein-512 ───────────────────────────────────────────────────────────────

fn ubi_pass_512(state: &mut [u8; 64], data: &[u8], type_byte: u8) {
    let block_size = 64usize;
    let n = data.len();
    if n == 0 {
        let tweak = make_tweak(0, type_byte, true, true, false);
        ubi_block_512(state, &[0u8; 64], &tweak);
        return;
    }
    let mut pos = 0usize;
    let mut first = true;
    while pos + block_size < n {
        let mut block = [0u8; 64];
        block.copy_from_slice(&data[pos..pos + block_size]);
        let new_pos = pos + block_size;
        let tweak = make_tweak(new_pos as u128, type_byte, first, false, false);
        ubi_block_512(state, &block, &tweak);
        first = false;
        pos = new_pos;
    }
    let remaining = n - pos;
    let mut last = [0u8; 64];
    last[..remaining].copy_from_slice(&data[pos..]);
    let tweak = make_tweak(n as u128, type_byte, first, true, false);
    ubi_block_512(state, &last, &tweak);
}

fn skein512_inner(data: &[u8], output_len: usize) -> Vec<u8> {
    let output_bits = (output_len as u64).wrapping_mul(8);
    let mut state = [0u8; 64];
    let cfg = config_block(output_bits);
    let mut cfg_block = [0u8; 64];
    cfg_block[..32].copy_from_slice(&cfg);
    let tweak = make_tweak(32, T_CFG, true, true, false);
    ubi_block_512(&mut state, &cfg_block, &tweak);

    ubi_pass_512(&mut state, data, T_MSG);

    let mut out = Vec::with_capacity(output_len);
    let mut counter: u64 = 0;
    while out.len() < output_len {
        let mut ctr_block = [0u8; 64];
        ctr_block[..8].copy_from_slice(&counter.to_le_bytes());
        let mut block_state = state;
        let tweak = make_tweak(8, T_OUT, true, true, false);
        ubi_block_512(&mut block_state, &ctr_block, &tweak);
        let take = core::cmp::min(64, output_len - out.len());
        out.extend_from_slice(&block_state[..take]);
        counter += 1;
    }
    out
}

/// Skein-512 hash: 512-bit internal state, arbitrary output length.
/// `output_len` is in bytes.
pub fn skein512(data: &[u8], output_len: usize) -> Vec<u8> {
    skein512_inner(data, output_len)
}

// ── Skein-1024 ──────────────────────────────────────────────────────────────

fn ubi_pass_1024(state: &mut [u8; 128], data: &[u8], type_byte: u8) {
    let block_size = 128usize;
    let n = data.len();
    if n == 0 {
        let tweak = make_tweak(0, type_byte, true, true, false);
        ubi_block_1024(state, &[0u8; 128], &tweak);
        return;
    }
    let mut pos = 0usize;
    let mut first = true;
    while pos + block_size < n {
        let mut block = [0u8; 128];
        block.copy_from_slice(&data[pos..pos + block_size]);
        let new_pos = pos + block_size;
        let tweak = make_tweak(new_pos as u128, type_byte, first, false, false);
        ubi_block_1024(state, &block, &tweak);
        first = false;
        pos = new_pos;
    }
    let remaining = n - pos;
    let mut last = [0u8; 128];
    last[..remaining].copy_from_slice(&data[pos..]);
    let tweak = make_tweak(n as u128, type_byte, first, true, false);
    ubi_block_1024(state, &last, &tweak);
}

fn skein1024_inner(data: &[u8], output_len: usize) -> Vec<u8> {
    let output_bits = (output_len as u64).wrapping_mul(8);
    let mut state = [0u8; 128];
    let cfg = config_block(output_bits);
    let mut cfg_block = [0u8; 128];
    cfg_block[..32].copy_from_slice(&cfg);
    let tweak = make_tweak(32, T_CFG, true, true, false);
    ubi_block_1024(&mut state, &cfg_block, &tweak);

    ubi_pass_1024(&mut state, data, T_MSG);

    let mut out = Vec::with_capacity(output_len);
    let mut counter: u64 = 0;
    while out.len() < output_len {
        let mut ctr_block = [0u8; 128];
        ctr_block[..8].copy_from_slice(&counter.to_le_bytes());
        let mut block_state = state;
        let tweak = make_tweak(8, T_OUT, true, true, false);
        ubi_block_1024(&mut block_state, &ctr_block, &tweak);
        let take = core::cmp::min(128, output_len - out.len());
        out.extend_from_slice(&block_state[..take]);
        counter += 1;
    }
    out
}

/// Skein-1024 hash: 1024-bit internal state, arbitrary output length.
/// `output_len` is in bytes.
pub fn skein1024(data: &[u8], output_len: usize) -> Vec<u8> {
    skein1024_inner(data, output_len)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn hex_to_vec(s: &str) -> Vec<u8> {
        hex::decode(s).expect("valid hex literal")
    }

    // ── Published KAT vectors ────────────────────────────────────────
    //
    // Sourced from the Skein 1.3 NIST submission package
    // (Reference_Implementation), cross-checked against `pyskein`'s
    // output for the same inputs.  Skein-N-N over the empty string
    // with the default tree-less config (schema "SHA3", version 1,
    // output length = state size).

    #[test]
    fn kat_skein256_empty() {
        let h = skein256(b"", 32);
        let expect = hex_to_vec("c8877087da56e072870daa843f176e9453115929094c3a40c463a196c29bf7ba");
        assert_eq!(h, expect);
    }

    #[test]
    fn kat_skein512_empty() {
        let h = skein512(b"", 64);
        let expect = hex_to_vec(
            "bc5b4c50925519c290cc634277ae3d6257212395cba733bbad37a4af0fa06af4\
             1fca7903d06564fea7a2d3730dbdb80c1f85562dfcc070334ea4d1d9e72cba7a",
        );
        assert_eq!(h, expect);
    }

    #[test]
    fn kat_skein1024_empty() {
        let h = skein1024(b"", 128);
        let expect = hex_to_vec(
            "0fff9563bb3279289227ac77d319b6fff8d7e9f09da1247b72a0a265cd6d2a62\
             645ad547ed8193db48cff847c06494a03f55666d3b47eb4c20456c9373c86297\
             d630d5578ebd34cb40991578f9f52b18003efa35d3da6553ff35db91b81ab890\
             bec1b189b7f52cb2a783ebb7d823d725b0b4a71f6824e88f68f982eefc6d19c6",
        );
        assert_eq!(h, expect);
    }

    // ── Determinism / length flexibility ─────────────────────────────

    #[test]
    fn skein_is_deterministic() {
        let a = skein256(b"hello world", 32);
        let b = skein256(b"hello world", 32);
        assert_eq!(a, b);
        let a = skein512(b"hello world", 64);
        let b = skein512(b"hello world", 64);
        assert_eq!(a, b);
        let a = skein1024(b"hello world", 128);
        let b = skein1024(b"hello world", 128);
        assert_eq!(a, b);
    }

    #[test]
    fn skein_output_length_changes_digest() {
        // Per spec, the output bit-length is encoded into the config
        // block, so a 32-byte digest must NOT be a prefix of a 64-byte
        // digest of the same input.
        let h32 = skein512(b"abc", 32);
        let h64 = skein512(b"abc", 64);
        assert_eq!(h32.len(), 32);
        assert_eq!(h64.len(), 64);
        assert_ne!(&h64[..32], &h32[..]);
    }

    #[test]
    fn skein_output_length_arbitrary() {
        // Skein is an XOF.  Asking for 100 bytes should produce 100
        // bytes; asking for 1 byte should produce 1.
        assert_eq!(skein512(b"abc", 100).len(), 100);
        assert_eq!(skein256(b"abc", 1).len(), 1);
        assert_eq!(skein1024(b"abc", 200).len(), 200);
    }

    // ── Differential / boundary properties ───────────────────────────

    #[test]
    fn skein_avalanche_single_bit() {
        let m1 = b"The quick brown fox jumps over the lazy dog".to_vec();
        let mut m2 = m1.clone();
        m2[0] ^= 1;
        let h1 = skein512(&m1, 64);
        let h2 = skein512(&m2, 64);
        let diff: usize = h1
            .iter()
            .zip(h2.iter())
            .map(|(a, b)| (a ^ b).count_ones() as usize)
            .sum();
        // 512 output bits; expect ~256 to flip.  Require ≥ 200.
        assert!(diff >= 200, "weak avalanche: {} bits", diff);
    }

    #[test]
    fn skein_blocksize_boundary() {
        // Right on the boundary (one full state block) and one byte
        // past (two blocks, second is bytePad-style padded) must give
        // different digests, and both must terminate without panic.
        let exactly_one_block = vec![0xa5u8; 64];
        let one_block_plus = vec![0xa5u8; 65];
        let h1 = skein512(&exactly_one_block, 64);
        let h2 = skein512(&one_block_plus, 64);
        assert_ne!(h1, h2);
        assert_eq!(h1.len(), 64);
        assert_eq!(h2.len(), 64);
    }

    #[test]
    fn skein_long_input() {
        // 10 KiB to exercise multi-block paths in all three variants.
        let m: Vec<u8> = (0..10_000).map(|i| (i & 0xff) as u8).collect();
        assert_eq!(skein256(&m, 32).len(), 32);
        assert_eq!(skein512(&m, 64).len(), 64);
        assert_eq!(skein1024(&m, 128).len(), 128);
    }
}
