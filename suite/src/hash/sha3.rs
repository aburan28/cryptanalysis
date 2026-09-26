//! SHA-3 (Keccak-p1600,24) implemented from scratch per NIST FIPS 202.
//!
//! # Keccak sponge construction
//! The state is a 5×5 matrix of 64-bit lanes (1600 bits total).
//! The sponge absorbs `rate` bits at a time, then squeezes output.
//!
//! Five step mappings per round (θ, ρ, π, χ, ι):
//!   θ — XOR each lane with the parity of two neighbouring columns.
//!   ρ — Rotate each lane by a fixed offset.
//!   π — Permute lane positions.
//!   χ — Non-linear mixing within each row.
//!   ι — XOR the (0,0) lane with a round constant to break symmetry.

/// Round constants (ι step), derived from an LFSR over GF(2).
const RC: [u64; 24] = [
    0x0000000000000001,
    0x0000000000008082,
    0x800000000000808a,
    0x8000000080008000,
    0x000000000000808b,
    0x0000000080000001,
    0x8000000080008081,
    0x8000000000008009,
    0x000000000000008a,
    0x0000000000000088,
    0x0000000080008009,
    0x000000008000000a,
    0x000000008000808b,
    0x800000000000008b,
    0x8000000000008089,
    0x8000000000008003,
    0x8000000000008002,
    0x8000000000000080,
    0x000000000000800a,
    0x800000008000000a,
    0x8000000080008081,
    0x8000000000008080,
    0x0000000080000001,
    0x8000000080008008,
];

/// Lane rotation offsets for the ρ step (indexed by [x][y] with x,y in 0..5).
const RHO_OFFSETS: [[u32; 5]; 5] = [
    [0, 36, 3, 41, 18],
    [1, 44, 10, 45, 2],
    [62, 6, 43, 15, 61],
    [28, 55, 25, 21, 56],
    [27, 20, 39, 8, 14],
];

/// Apply Keccak-p1600,24 permutation in-place on a 25-lane (200-byte) state.
pub fn keccak_f(state: &mut [u64; 25]) {
    for rc in &RC {
        // θ: XOR with column parities
        let mut c = [0u64; 5];
        for x in 0..5 {
            c[x] = state[x] ^ state[x + 5] ^ state[x + 10] ^ state[x + 15] ^ state[x + 20];
        }
        let mut d = [0u64; 5];
        for x in 0..5 {
            d[x] = c[(x + 4) % 5] ^ c[(x + 1) % 5].rotate_left(1);
        }
        for i in 0..25 {
            state[i] ^= d[i % 5];
        }

        // ρ and π combined: rotate then permute
        let mut b = [0u64; 25];
        for x in 0..5usize {
            for y in 0..5usize {
                let src = x + 5 * y;
                let dst = y + 5 * ((2 * x + 3 * y) % 5);
                b[dst] = state[src].rotate_left(RHO_OFFSETS[x][y]);
            }
        }

        // χ: non-linear row mixing
        for x in 0..5usize {
            for y in 0..5usize {
                state[x + 5 * y] =
                    b[x + 5 * y] ^ ((!b[(x + 1) % 5 + 5 * y]) & b[(x + 2) % 5 + 5 * y]);
            }
        }

        // ι: add round constant to lane (0,0)
        state[0] ^= rc;
    }
}

/// Generic Keccak sponge. `rate` is in bytes; `capacity = 200 - rate`.
/// `suffix` is the domain-separation byte (0x06 for SHA-3, 0x1f for SHAKE).
fn keccak_sponge(msg: &[u8], rate: usize, output_len: usize, suffix: u8) -> Vec<u8> {
    let mut state = [0u64; 25];

    // Absorb: pad and XOR message into state in `rate`-byte chunks.
    let mut padded = msg.to_vec();
    padded.push(suffix);
    while !padded.len().is_multiple_of(rate) {
        padded.push(0x00);
    }
    // Set the last padding byte's high bit (multi-rate padding)
    *padded.last_mut().unwrap() |= 0x80;

    for block in padded.chunks(rate) {
        // XOR block into state (little-endian lanes)
        for (i, chunk) in block.chunks(8).enumerate() {
            let mut word = [0u8; 8];
            word[..chunk.len()].copy_from_slice(chunk);
            state[i] ^= u64::from_le_bytes(word);
        }
        keccak_f(&mut state);
    }

    // Squeeze: extract `output_len` bytes from the state.
    let mut out = Vec::with_capacity(output_len);
    while out.len() < output_len {
        for i in 0..(rate / 8) {
            out.extend_from_slice(&state[i].to_le_bytes());
            if out.len() >= output_len {
                break;
            }
        }
        if out.len() < output_len {
            keccak_f(&mut state);
        }
    }
    out.truncate(output_len);
    out
}

// ── Public API ───────────────────────────────────────────────────────────────

/// SHA3-256: rate=136 bytes, output=32 bytes, domain suffix=0x06.
pub fn sha3_256(data: &[u8]) -> [u8; 32] {
    let v = keccak_sponge(data, 136, 32, 0x06);
    v.try_into().unwrap()
}

/// SHA3-512: rate=72 bytes, output=64 bytes.
pub fn sha3_512(data: &[u8]) -> [u8; 64] {
    let v = keccak_sponge(data, 72, 64, 0x06);
    v.try_into().unwrap()
}

/// SHAKE128: variable-length XOF with rate=168 bytes.
pub fn shake128(data: &[u8], output_len: usize) -> Vec<u8> {
    keccak_sponge(data, 168, output_len, 0x1f)
}

/// SHAKE256: variable-length XOF with rate=136 bytes.
pub fn shake256(data: &[u8], output_len: usize) -> Vec<u8> {
    keccak_sponge(data, 136, output_len, 0x1f)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn h(s: &str) -> Vec<u8> {
        hex::decode(s).unwrap()
    }

    #[test]
    fn sha3_256_empty() {
        // NIST KAT
        assert_eq!(
            sha3_256(b"").as_slice(),
            h("a7ffc6f8bf1ed76651c14756a061d662f580ff4de43b49fa82d80a4b80f8434a").as_slice(),
        );
    }

    #[test]
    fn sha3_256_abc() {
        // NIST KAT
        assert_eq!(
            sha3_256(b"abc").as_slice(),
            h("3a985da74fe225b2045c172d6bd390bd855f086e3e9d525b46bfe24511431532").as_slice(),
        );
    }

    #[test]
    fn sha3_256_long() {
        // Crosses the 136-byte rate boundary.
        let msg = vec![0xa3u8; 200];
        // Verified against `openssl dgst -sha3-256` reference:
        let expected = h("79f38adec5c20307a98ef76e8324afbfd46cfd81b22e3973c65fa1bd9de31787");
        assert_eq!(sha3_256(&msg).as_slice(), expected.as_slice());
    }

    #[test]
    fn sha3_512_empty() {
        // NIST KAT
        assert_eq!(
            sha3_512(b"").as_slice(),
            h("a69f73cca23a9ac5c8b567dc185a756e97c982164fe25859e0d1dcc1475c80a615b2123af1f5f94c11e3e9402c3ac558f500199d95b6d3e301758586281dcd26").as_slice(),
        );
    }

    #[test]
    fn sha3_512_abc() {
        // NIST KAT
        assert_eq!(
            sha3_512(b"abc").as_slice(),
            h("b751850b1a57168a5693cd924b6b096e08f621827444f70d884f5d0240d2712e10e116e9192af3c91a7ec57647e3934057340b4cf408d5a56592f8274eec53f0").as_slice(),
        );
    }

    #[test]
    fn shake256_abc_32() {
        // 32-byte SHAKE-256 output of "abc"
        assert_eq!(
            shake256(b"abc", 32),
            h("483366601360a8771c6863080cc4114d8db44530f8f1e1ee4f94ea37e78b5739"),
        );
    }

    #[test]
    fn shake128_empty_32() {
        // NIST KAT
        assert_eq!(
            shake128(b"", 32),
            h("7f9c2ba4e88f827d616045507605853ed73b8093f6efbc88eb1a6eacfa66ef26"),
        );
    }
}
