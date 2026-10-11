//! **Grain v1** — eSTREAM hardware portfolio finalist stream cipher
//! (Hell, Johansson & Meier, 2005, finalised 2008).
//!
//! 80-bit key, 64-bit IV, 160-bit internal state: an 80-bit linear
//! feedback shift register (LFSR) coupled with an 80-bit non-linear
//! feedback shift register (NFSR) by a 5-input non-linear filter `h`.
//! Like Trivium, Grain v1 was designed for extreme hardware economy
//! (≈1300 gates).  The 80-bit key makes it a teaching-grade cipher.
//!
//! ## Algorithm
//!
//! With `b_0..b_79` the NFSR contents (index 0 = oldest = output side)
//! and `s_0..s_79` the LFSR contents, each clock computes:
//!
//! ```text
//!     s_80 = s_62 ⊕ s_51 ⊕ s_38 ⊕ s_23 ⊕ s_13 ⊕ s_0
//!     b_80 = s_0  ⊕ b_62 ⊕ b_60 ⊕ b_52 ⊕ b_45 ⊕ b_37 ⊕ b_33
//!                ⊕ b_28 ⊕ b_21 ⊕ b_14 ⊕ b_9 ⊕ b_0
//!                ⊕ NL(b) -- 11 non-linear monomials, see source
//!     z    = h(s_3, s_25, s_46, s_64, b_63)
//!                ⊕ b_1 ⊕ b_2 ⊕ b_4 ⊕ b_10 ⊕ b_31 ⊕ b_43 ⊕ b_56
//! ```
//!
//! and then both registers shift down by one with `s_80`, `b_80` as
//! the new top bits.  During the 160-clock initialisation `z` is XORed
//! into both feedback bits (`s_80 ⊕= z`, `b_80 ⊕= z`) and not emitted.
//! After init the cipher emits one keystream bit per clock.
//!
//! ## Byte / bit conventions (eSTREAM)
//!
//! Following the official ECRYPT C reference: NFSR is loaded with the
//! key byte-by-byte, **LSB-first within each byte** — `NFSR[8i + j] =
//! bit j of key[i]`.  LFSR positions 0..63 are loaded from the IV the
//! same way; positions 64..79 are filled with ones (the LFSR must not
//! start all-zero).  Keystream is emitted LSB-first: `z_1` is bit 0
//! of byte 0.
//!
//! ## References
//!
//! - M. Hell, T. Johansson, W. Meier, *Grain — A Stream Cipher for
//!   Constrained Environments*, IJWMC 2007 / eSTREAM 2008.
//!   <https://www.ecrypt.eu.org/stream/p3ciphers/grain/Grain_p3.pdf>
//! - Test vector cross-checked against the eSTREAM-style C reference
//!   at `gulshanRaj/Grain_V1_implementation` (which follows the
//!   official ECRYPT API conventions documented above).

/// Grain v1 cipher state: an 80-bit NFSR plus an 80-bit LFSR.  Index 0
/// is the "output side" (bit shifted out on the next clock); new bits
/// land at index 79.
pub struct Grain {
    nfsr: [u8; 80],
    lfsr: [u8; 80],
}

impl Grain {
    /// Initialise Grain v1 from an 80-bit key and 64-bit IV, then run
    /// the 160-clock warm-up with output feedback.
    pub fn new(key: &[u8; 10], iv: &[u8; 8]) -> Self {
        let mut nfsr = [0u8; 80];
        let mut lfsr = [0u8; 80];
        for i in 0..10 {
            for j in 0..8 {
                nfsr[i * 8 + j] = (key[i] >> j) & 1;
            }
        }
        for i in 0..8 {
            for j in 0..8 {
                lfsr[i * 8 + j] = (iv[i] >> j) & 1;
            }
        }
        for s in lfsr.iter_mut().skip(64) {
            *s = 1;
        }
        let mut g = Grain { nfsr, lfsr };
        for _ in 0..160 {
            g.step(true);
        }
        g
    }

    /// Advance the cipher by one clock.  Returns the keystream bit
    /// produced this cycle; when `feedback`, that bit is also XORed
    /// into both feedback bits (used during initialisation only).
    fn step(&mut self, feedback: bool) -> u8 {
        let n = &self.nfsr;
        let l = &self.lfsr;
        // Output filter h(x0, x1, x2, x3, x4)
        let (x0, x1, x2, x3, x4) = (l[3], l[25], l[46], l[64], n[63]);
        let h = x1
            ^ x4
            ^ (x0 & x3)
            ^ (x2 & x3)
            ^ (x3 & x4)
            ^ (x0 & x1 & x2)
            ^ (x0 & x2 & x3)
            ^ (x0 & x2 & x4)
            ^ (x1 & x2 & x4)
            ^ (x2 & x3 & x4);
        let z = h ^ n[1] ^ n[2] ^ n[4] ^ n[10] ^ n[31] ^ n[43] ^ n[56];

        // LFSR feedback (linear).
        let mut lbit = l[62] ^ l[51] ^ l[38] ^ l[23] ^ l[13] ^ l[0];
        // NFSR feedback: linear taps + 11 non-linear monomials per spec.
        let mut nbit = l[0]
            ^ n[62]
            ^ n[60]
            ^ n[52]
            ^ n[45]
            ^ n[37]
            ^ n[33]
            ^ n[28]
            ^ n[21]
            ^ n[14]
            ^ n[9]
            ^ n[0]
            ^ (n[63] & n[60])
            ^ (n[37] & n[33])
            ^ (n[15] & n[9])
            ^ (n[60] & n[52] & n[45])
            ^ (n[33] & n[28] & n[21])
            ^ (n[63] & n[45] & n[28] & n[9])
            ^ (n[60] & n[52] & n[37] & n[33])
            ^ (n[63] & n[60] & n[21] & n[15])
            ^ (n[63] & n[60] & n[52] & n[45] & n[37])
            ^ (n[33] & n[28] & n[21] & n[15] & n[9])
            ^ (n[52] & n[45] & n[37] & n[33] & n[28] & n[21]);

        if feedback {
            lbit ^= z;
            nbit ^= z;
        }

        self.lfsr.copy_within(1..80, 0);
        self.nfsr.copy_within(1..80, 0);
        self.lfsr[79] = lbit;
        self.nfsr[79] = nbit;
        z
    }

    /// Produce the next `n` bytes of keystream (LSB-first within byte).
    pub fn keystream(&mut self, n: usize) -> Vec<u8> {
        let mut out = vec![0u8; n];
        for byte in out.iter_mut() {
            let mut b = 0u8;
            for j in 0..8 {
                b |= self.step(false) << j;
            }
            *byte = b;
        }
        out
    }
}

/// Encrypt or decrypt `data` by XORing it with a fresh Grain v1
/// keystream derived from `(key, iv)`.  Symmetric (encrypt = decrypt).
pub fn grain_xor(data: &[u8], key: &[u8; 10], iv: &[u8; 8]) -> Vec<u8> {
    let mut g = Grain::new(key, iv);
    let ks = g.keystream(data.len());
    data.iter().zip(ks.iter()).map(|(a, b)| a ^ b).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn h(s: &str) -> Vec<u8> {
        hex::decode(s).unwrap()
    }

    /// **All-zero key & IV** — sanity vector reproduced from the
    /// official ECRYPT C reference (`gulshanRaj/Grain_V1_implementation`,
    /// TestCase 1: key = 00…0, IV = 00…0, first 10 keystream bytes).
    #[test]
    fn grain_zero_key_zero_iv() {
        let key: [u8; 10] = h("00000000000000000000").try_into().unwrap();
        let iv: [u8; 8] = h("0000000000000000").try_into().unwrap();
        let mut g = Grain::new(&key, &iv);
        assert_eq!(g.keystream(10), h("DEE931CF1662A72F77D0"));
    }

    /// **Set 1, vector#0** — key = 80…0, IV = 0…0.  First 10 keystream
    /// bytes match the eSTREAM-style C reference (TestCase 3 of
    /// `gulshanRaj/Grain_V1_implementation`); the remaining six bytes
    /// were derived from the same reference at the time of writing.
    #[test]
    fn grain_set1_vector0() {
        let key: [u8; 10] = h("80000000000000000000").try_into().unwrap();
        let iv: [u8; 8] = h("0000000000000000").try_into().unwrap();
        let mut g = Grain::new(&key, &iv);
        assert_eq!(g.keystream(16), h("FF7710B30F198D75A454AB7A6B92A022"));
    }

    /// XOR symmetry: encrypt-then-encrypt = identity.
    #[test]
    fn grain_round_trip() {
        let key: [u8; 10] = [0x33; 10];
        let iv: [u8; 8] = [0x66; 8];
        let pt = b"Pack my box with five dozen liquor jugs.";
        let ct = grain_xor(pt, &key, &iv);
        assert_ne!(&ct[..], &pt[..]);
        assert_eq!(grain_xor(&ct, &key, &iv), pt.to_vec());
    }

    /// Continuing the keystream across two calls equals one big call.
    #[test]
    fn grain_continuous_stream() {
        let key: [u8; 10] = h("80000000000000000000").try_into().unwrap();
        let iv: [u8; 8] = h("0000000000000000").try_into().unwrap();
        let mut g = Grain::new(&key, &iv);
        let mut got = g.keystream(7);
        got.extend(g.keystream(9));
        assert_eq!(got, h("FF7710B30F198D75A454AB7A6B92A022"));
    }

    /// Different IVs under the same key must give different streams.
    #[test]
    fn grain_iv_changes_stream() {
        let key: [u8; 10] = [0x5a; 10];
        let iv1: [u8; 8] = [0x00; 8];
        let mut iv2 = iv1;
        iv2[7] = 0x01;
        let ks1 = Grain::new(&key, &iv1).keystream(32);
        let ks2 = Grain::new(&key, &iv2).keystream(32);
        assert_ne!(ks1, ks2);
    }
}
