//! **Trivium** — eSTREAM hardware portfolio finalist stream cipher
//! (De Cannière & Preneel, 2005; finalised 2008).
//!
//! 80-bit key, 80-bit IV, 288-bit internal state arranged as three
//! coupled non-linear feedback shift registers (NLFSRs).  Designed to
//! be extremely cheap in hardware (≈3500 gates) while admitting bit-
//! parallel software implementations.  No practical attack better than
//! exhaustive key search is known as of writing, but the small key
//! and IV make this a teaching-grade cipher only.
//!
//! ## Algorithm
//!
//! Three NLFSRs hold bits `s_1..s_93` (A), `s_94..s_177` (B), and
//! `s_178..s_288` (C).  Initialisation places the 80-bit key in
//! `s_1..s_80`, the 80-bit IV in `s_94..s_173`, sets `s_286 = s_287 =
//! s_288 = 1`, zeros everything else, then runs 4·288 = 1152 warm-up
//! clocks producing no output.  Each subsequent clock produces one
//! keystream bit `z`:
//!
//! ```text
//!     t1 = s_66 ⊕ s_93
//!     t2 = s_162 ⊕ s_177
//!     t3 = s_243 ⊕ s_288
//!     z  = t1 ⊕ t2 ⊕ t3
//!     t1 ⊕= s_91·s_92 ⊕ s_171
//!     t2 ⊕= s_175·s_176 ⊕ s_264
//!     t3 ⊕= s_286·s_287 ⊕ s_69
//!     (s_1..s_93)   ← (t3, s_1..s_92)
//!     (s_94..s_177) ← (t1, s_94..s_176)
//!     (s_178..s_288)← (t2, s_178..s_287)
//! ```
//!
//! ## Byte / bit conventions (eSTREAM)
//!
//! The 10-byte key array is treated as an 80-bit big-endian integer:
//! the MSB of `key[0]` is the highest bit of the value.  That highest
//! bit goes to `s_73` (i.e. `s_{1+p}` is bit `(7 - p%8)` of
//! `key[9 - p/8]` for `p ∈ 0..80`).  The IV uses the same convention.
//! Keystream bytes are produced LSB-first: the first eight keystream
//! bits `z_1..z_8` are packed into byte 0 with `z_1` at bit 0 (LSB)
//! and `z_8` at bit 7 (MSB).  These conventions reproduce the eSTREAM
//! "Set 1, vector#0" test vector exactly.
//!
//! ## References
//!
//! - C. De Cannière, B. Preneel, *Trivium Specifications*, eSTREAM 2008.
//!   <https://www.ecrypt.eu.org/stream/p3ciphers/trivium/trivium_p3.pdf>
//! - eSTREAM KAT files (Set 1, vector#0, key = 80…0, IV = 0…0)
//!   reproduced e.g. in `bmkessler/trivium` and `uisyudha/Trivium`.

/// Trivium cipher state: the 288-bit internal state, indexed 0..288
/// with array index `p` corresponding to specification bit `s_{p+1}`.
pub struct Trivium {
    s: [u8; 288],
}

impl Trivium {
    /// Initialise Trivium from an 80-bit key and 80-bit IV, then run
    /// the 1152-clock warm-up.  After construction, the cipher is
    /// ready to emit keystream bytes.
    pub fn new(key: &[u8; 10], iv: &[u8; 10]) -> Self {
        let mut s = [0u8; 288];
        // Big-endian 80-bit load: key[0] is the most significant byte
        // (MSB of key[0] is bit 79 of the integer), and bit 79 → s_1
        // would be the highest-bit-first convention.  The eSTREAM
        // test vectors instead place the integer's MSB at s_73, which
        // is what the formula below produces: byte 9 fills s_1..s_8,
        // byte 0 fills s_73..s_80.
        for p in 0..80usize {
            let byte_idx = 9 - p / 8;
            let bit_pos = 7 - (p % 8);
            s[p] = (key[byte_idx] >> bit_pos) & 1;
            s[93 + p] = (iv[byte_idx] >> bit_pos) & 1;
        }
        s[285] = 1;
        s[286] = 1;
        s[287] = 1;
        let mut tr = Trivium { s };
        for _ in 0..1152 {
            tr.clock();
        }
        tr
    }

    /// One Trivium clock: advance the state and return the keystream
    /// bit produced during this cycle.
    fn clock(&mut self) -> u8 {
        let s = &self.s;
        let t1 = s[65] ^ s[92];
        let t2 = s[161] ^ s[176];
        let t3 = s[242] ^ s[287];
        let z = t1 ^ t2 ^ t3;
        let t1n = t1 ^ (s[90] & s[91]) ^ s[170];
        let t2n = t2 ^ (s[174] & s[175]) ^ s[263];
        let t3n = t3 ^ (s[285] & s[286]) ^ s[68];
        // Shift each NLFSR by one position; new bits go to s_1, s_94, s_178.
        // The old s_93 / s_177 / s_288 (== s[92], s[176], s[287]) are
        // discarded — they've already been used above.
        self.s.copy_within(0..92, 1);
        self.s.copy_within(93..176, 94);
        self.s.copy_within(177..287, 178);
        self.s[0] = t3n;
        self.s[93] = t1n;
        self.s[177] = t2n;
        z
    }

    /// Produce the next `n` bytes of keystream (LSB-first packed:
    /// the first generated bit `z_1` lands in bit 0 of byte 0).
    pub fn keystream(&mut self, n: usize) -> Vec<u8> {
        let mut out = vec![0u8; n];
        for byte in out.iter_mut() {
            let mut b = 0u8;
            for j in 0..8 {
                b |= self.clock() << j;
            }
            *byte = b;
        }
        out
    }
}

/// Encrypt or decrypt `data` by XORing it with a fresh Trivium
/// keystream derived from `(key, iv)`.  Symmetric (encrypt = decrypt).
pub fn trivium_xor(data: &[u8], key: &[u8; 10], iv: &[u8; 10]) -> Vec<u8> {
    let mut cipher = Trivium::new(key, iv);
    let ks = cipher.keystream(data.len());
    data.iter().zip(ks.iter()).map(|(a, b)| a ^ b).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn h(s: &str) -> Vec<u8> {
        hex::decode(s).unwrap()
    }

    /// **eSTREAM Set 1, vector#0** — key = 80…0, IV = 0…0.
    /// First 64 bytes of keystream taken from the official KAT file
    /// (reproduced in `bmkessler/trivium`'s test-vector dump).
    #[test]
    fn trivium_estream_set1_vec0() {
        let key: [u8; 10] = h("80000000000000000000").try_into().unwrap();
        let iv: [u8; 10] = h("00000000000000000000").try_into().unwrap();
        let mut tr = Trivium::new(&key, &iv);
        let ks = tr.keystream(64);
        let expected = h("38EB86FF730D7A9CAF8DF13A4420540D\
             BB7B651464C87501552041C249F29A64\
             D2FBF515610921EBE06C8F92CECF7F80\
             98FF20CCCC6A62B97BE8EF7454FC80F9");
        assert_eq!(ks, expected);
    }

    /// First 16 bytes shortcut for quick visual diff in CI failure logs.
    #[test]
    fn trivium_first_16_bytes() {
        let key: [u8; 10] = h("80000000000000000000").try_into().unwrap();
        let iv: [u8; 10] = h("00000000000000000000").try_into().unwrap();
        let mut tr = Trivium::new(&key, &iv);
        let ks = tr.keystream(16);
        assert_eq!(ks, h("38EB86FF730D7A9CAF8DF13A4420540D"));
    }

    /// XOR is its own inverse: encrypt-then-encrypt = identity.
    #[test]
    fn trivium_round_trip() {
        let key: [u8; 10] = [0x42; 10];
        let iv: [u8; 10] = [0x11; 10];
        let pt = b"the quick brown fox jumps over the lazy dog 0123456789";
        let ct = trivium_xor(pt, &key, &iv);
        assert_ne!(&ct[..], &pt[..]);
        let pt2 = trivium_xor(&ct, &key, &iv);
        assert_eq!(&pt2[..], &pt[..]);
    }

    /// Keystream is independent of the data — calling `keystream`
    /// twice on the same cipher continues the stream.
    #[test]
    fn trivium_continuous_stream() {
        let key: [u8; 10] = h("80000000000000000000").try_into().unwrap();
        let iv: [u8; 10] = h("00000000000000000000").try_into().unwrap();
        let mut tr = Trivium::new(&key, &iv);
        let mut got = tr.keystream(8);
        got.extend(tr.keystream(8));
        assert_eq!(got, h("38EB86FF730D7A9CAF8DF13A4420540D"));
    }

    /// Different IVs produce different keystreams (basic sanity).
    #[test]
    fn trivium_iv_changes_stream() {
        let key: [u8; 10] = [0xaa; 10];
        let iv1: [u8; 10] = [0x00; 10];
        let mut iv2 = iv1;
        iv2[0] = 0x01;
        let ks1 = Trivium::new(&key, &iv1).keystream(32);
        let ks2 = Trivium::new(&key, &iv2).keystream(32);
        assert_ne!(ks1, ks2);
    }
}
