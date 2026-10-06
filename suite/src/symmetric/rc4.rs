//! **RC4** — Rivest Cipher 4 (Ron Rivest, 1987).
//!
//! Variable-key-length byte-wise stream cipher.  Famously simple
//! (~50 LoC), historically dominant (WEP, TLS RC4 cipher suites, SSL,
//! some BitTorrent / Microsoft OLE protocols), and now **comprehensively
//! broken**:
//!
//! - **Output bias** in the first ~256 bytes leaks key information
//!   (Mantin–Shamir 2001, Fluhrer–Mantin–Shamir 2001).
//! - **Plaintext recovery on TLS** (AlFardan–Bernstein–Paterson–
//!   Poettering–Schuldt USENIX 2013) recovers cookies after ~2³² captures.
//! - **WEP attacks** (FMS 2001, KoreK 2004, PTW 2007) recover the
//!   key from passive captures in seconds.
//!
//! Ship the algorithm here for **teaching and cryptanalysis only**.
//! For any new design, use ChaCha20 instead.
//!
//! ## Algorithm
//!
//! State: a 256-byte permutation `S` and two byte counters `i, j`.
//!
//! **KSA (Key Scheduling Algorithm)** — given key `K`:
//!
//! ```text
//!     for i = 0..256:  S[i] = i
//!     j = 0
//!     for i = 0..256:
//!         j = (j + S[i] + K[i mod |K|]) mod 256
//!         swap(S[i], S[j])
//! ```
//!
//! **PRGA (Pseudo-Random Generation Algorithm)** — per output byte:
//!
//! ```text
//!     i = (i + 1) mod 256
//!     j = (j + S[i]) mod 256
//!     swap(S[i], S[j])
//!     output S[(S[i] + S[j]) mod 256]
//! ```
//!
//! Encrypt / decrypt: XOR plaintext / ciphertext with the keystream.
//! Symmetric operation.
//!
//! ## References
//!
//! - **R. Rivest** (1987), unpublished but later leaked as
//!   "alleged RC4" on sci.crypt in 1994.
//! - **B. Schneier**, *Applied Cryptography*, 2nd ed., §17.1.
//! - **RFC 6229** — test vectors for the alleged-RC4 stream cipher.

/// RC4 state: the 256-byte permutation `S` plus the two byte counters
/// `i, j` that drive the PRGA.
pub struct Rc4 {
    s: [u8; 256],
    i: u8,
    j: u8,
}

impl Rc4 {
    /// Initialise RC4 with `key` (length 1..256).  Runs the KSA to
    /// install the per-key permutation.
    pub fn new(key: &[u8]) -> Result<Self, &'static str> {
        if key.is_empty() || key.len() > 256 {
            return Err("RC4: key length must be in 1..=256 bytes");
        }
        let mut s = [0u8; 256];
        for k in 0..256 {
            s[k] = k as u8;
        }
        let mut j: u8 = 0;
        for i in 0..256 {
            j = j.wrapping_add(s[i]).wrapping_add(key[i % key.len()]);
            s.swap(i, j as usize);
        }
        Ok(Rc4 { s, i: 0, j: 0 })
    }

    /// Emit the next keystream byte (advances the PRGA state).
    pub fn next_byte(&mut self) -> u8 {
        self.i = self.i.wrapping_add(1);
        self.j = self.j.wrapping_add(self.s[self.i as usize]);
        self.s.swap(self.i as usize, self.j as usize);
        let k = self
            .s
            .get((self.s[self.i as usize].wrapping_add(self.s[self.j as usize])) as usize)
            .copied()
            .unwrap();
        k
    }

    /// XOR `data` with the next `data.len()` keystream bytes (in place).
    pub fn apply_keystream(&mut self, data: &mut [u8]) {
        for byte in data {
            *byte ^= self.next_byte();
        }
    }
}

/// **RC4 encrypt / decrypt** — same operation, since RC4 is an XOR
/// stream cipher.  Convenience wrapper around `Rc4::new` and
/// `apply_keystream`.
pub fn rc4(key: &[u8], data: &[u8]) -> Vec<u8> {
    let mut out = data.to_vec();
    let mut state = Rc4::new(key).expect("invalid key");
    state.apply_keystream(&mut out);
    out
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn h(s: &str) -> Vec<u8> {
        let s: String = s.chars().filter(|c| !c.is_whitespace()).collect();
        (0..s.len())
            .step_by(2)
            .map(|i| u8::from_str_radix(&s[i..i + 2], 16).unwrap())
            .collect()
    }

    /// **RFC 6229 §2 Test Vector #1** — key = 0102030405 (5 bytes),
    /// keystream[0..16] = b2 39 63 05 f0 3d c0 27 cc c3 52 4a 0a 11 18 a8.
    #[test]
    fn rc4_rfc6229_test_vector_1() {
        let key = h("0102030405");
        let mut rc = Rc4::new(&key).unwrap();
        let mut ks = vec![0u8; 16];
        rc.apply_keystream(&mut ks);
        let expected = h("b2 39 63 05 f0 3d c0 27 cc c3 52 4a 0a 11 18 a8");
        assert_eq!(ks, expected);
    }

    /// **RFC 6229 §2 Test Vector #2** — key = 01020304050607 (7 bytes),
    /// keystream[0..16] = 29 3f 02 d4 7f 37 c9 b6 33 f2 af 52 85 fe b4 6b.
    #[test]
    fn rc4_rfc6229_test_vector_2() {
        let key = h("01020304050607");
        let mut rc = Rc4::new(&key).unwrap();
        let mut ks = vec![0u8; 16];
        rc.apply_keystream(&mut ks);
        let expected = h("29 3f 02 d4 7f 37 c9 b6 33 f2 af 52 85 fe b4 6b");
        assert_eq!(ks, expected);
    }

    /// **Plaintext-encrypt example from Wikipedia / RFC 6229**:
    ///   key = "Key", plaintext = "Plaintext"
    ///   ciphertext = BBF316E8 D940AF0A D3
    #[test]
    fn rc4_encrypt_plaintext_example() {
        let key = b"Key";
        let pt = b"Plaintext";
        let ct = rc4(key, pt);
        let expected = h("BBF316E8 D940AF0A D3");
        assert_eq!(ct, expected);
    }

    /// **RFC 6229 — key "Wiki", plaintext "pedia"**:
    ///   ciphertext = 1021BF0420
    #[test]
    fn rc4_encrypt_wiki_pedia() {
        let key = b"Wiki";
        let pt = b"pedia";
        let ct = rc4(key, pt);
        let expected = h("1021BF0420");
        assert_eq!(ct, expected);
    }

    /// **RFC 6229 — key "Secret", plaintext "Attack at dawn"**:
    ///   ciphertext = 45A01F645FC35B383552544B9BF5
    #[test]
    fn rc4_encrypt_attack_at_dawn() {
        let key = b"Secret";
        let pt = b"Attack at dawn";
        let ct = rc4(key, pt);
        let expected = h("45A01F645FC35B383552544B9BF5");
        assert_eq!(ct, expected);
    }

    /// **Round-trip property**: encrypt-then-encrypt-with-same-key
    /// yields the original (RC4 is XOR-symmetric).
    #[test]
    fn rc4_round_trip() {
        let key = b"a longer test key for round trip";
        let pt = b"the quick brown fox jumps over the lazy dog 123456789";
        let ct = rc4(key, pt);
        assert_ne!(&ct[..], &pt[..]);
        let pt2 = rc4(key, &ct);
        assert_eq!(&pt2[..], &pt[..]);
    }

    /// **Key rejection**: empty or too-long keys return Err.
    #[test]
    fn rc4_rejects_bad_key_lengths() {
        assert!(Rc4::new(&[]).is_err());
        assert!(Rc4::new(&vec![0u8; 257]).is_err());
        assert!(Rc4::new(&[1u8]).is_ok());
        assert!(Rc4::new(&vec![0u8; 256]).is_ok());
    }
}
