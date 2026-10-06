//! **3DES (TDEA — Triple Data Encryption Algorithm)** — NIST SP 800-67.
//!
//! Triple-application of DES under three keys K1, K2, K3 in
//! **EDE3** mode (Encrypt–Decrypt–Encrypt):
//!
//! ```text
//!     C = E_K3(D_K2(E_K1(P)))
//! ```
//!
//! Decrypt: `P = D_K1(E_K2(D_K3(C)))`.
//!
//! ## Keying options (NIST SP 800-67)
//!
//! - **Three-key 3DES** (`3TDEA`): `K1, K2, K3` all distinct.
//!   168-bit nominal key, ~112-bit effective security (meet-in-the-middle).
//! - **Two-key 3DES** (`2TDEA`): `K3 = K1`.  Deprecated by NIST since
//!   2017 — use 3-key only.
//! - If `K1 = K2 = K3`, the EDE collapses to plain DES (compatibility mode).
//!
//! ## Status
//!
//! NIST SP 800-67 Rev. 2 (2017) **disallows** 3DES for new applications
//! and limits any existing usage to **≤ 2²⁰ blocks per key** (Sweet32
//! birthday-bound attack, Bhargavan-Leurent 2016).  Banking and PKCS#12
//! still ship 3DES at the time of writing.

use super::des;

/// 3DES context with all three round-key schedules pre-expanded.
pub struct TripleDes {
    k1: des::Des,
    k2: des::Des,
    k3: des::Des,
}

impl TripleDes {
    /// New 3-key 3DES.  Caller must supply three distinct 8-byte keys.
    pub fn new(k1: &[u8; 8], k2: &[u8; 8], k3: &[u8; 8]) -> Self {
        TripleDes {
            k1: des::Des::new(k1),
            k2: des::Des::new(k2),
            k3: des::Des::new(k3),
        }
    }

    /// 2-key 3DES (`K3 = K1`).  **Deprecated** — kept for legacy
    /// interoperability with PKCS#12 etc.
    pub fn new_two_key(k1: &[u8; 8], k2: &[u8; 8]) -> Self {
        Self::new(k1, k2, k1)
    }

    /// Encrypt one 64-bit block.
    pub fn encrypt_block(&self, block: &mut [u8; 8]) {
        self.k1.encrypt_block(block);
        self.k2.decrypt_block(block);
        self.k3.encrypt_block(block);
    }

    /// Decrypt one 64-bit block.
    pub fn decrypt_block(&self, block: &mut [u8; 8]) {
        self.k3.decrypt_block(block);
        self.k2.encrypt_block(block);
        self.k1.decrypt_block(block);
    }
}

/// Free-function 3DES encrypt with a 24-byte key (K1 || K2 || K3).
pub fn encrypt_block(key: &[u8; 24], block: &[u8; 8]) -> [u8; 8] {
    let mut k1 = [0u8; 8];
    let mut k2 = [0u8; 8];
    let mut k3 = [0u8; 8];
    k1.copy_from_slice(&key[0..8]);
    k2.copy_from_slice(&key[8..16]);
    k3.copy_from_slice(&key[16..24]);
    let tdes = TripleDes::new(&k1, &k2, &k3);
    let mut out = *block;
    tdes.encrypt_block(&mut out);
    out
}

/// Free-function 3DES decrypt.
pub fn decrypt_block(key: &[u8; 24], block: &[u8; 8]) -> [u8; 8] {
    let mut k1 = [0u8; 8];
    let mut k2 = [0u8; 8];
    let mut k3 = [0u8; 8];
    k1.copy_from_slice(&key[0..8]);
    k2.copy_from_slice(&key[8..16]);
    k3.copy_from_slice(&key[16..24]);
    let tdes = TripleDes::new(&k1, &k2, &k3);
    let mut out = *block;
    tdes.decrypt_block(&mut out);
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

    /// **3DES collapses to DES** when K1 = K2 = K3.  Encrypt one
    /// block under EDE-with-identical-keys and verify it matches
    /// plain DES.
    #[test]
    fn tdes_compat_with_des_when_keys_equal() {
        let k = [0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC, 0xDE, 0xF0];
        let p = [0x01, 0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xEF];
        let tdes = TripleDes::new(&k, &k, &k);
        let mut blk = p;
        tdes.encrypt_block(&mut blk);
        let des_ct = crate::symmetric::des::encrypt_block(&k, &p);
        assert_eq!(blk, des_ct);
    }

    /// **NIST CAVS TECB-Multi-3DES vector** with three distinct keys:
    /// K1 = 0123456789ABCDEF
    /// K2 = 23456789ABCDEF01
    /// K3 = 456789ABCDEF0123
    /// PT = 5468652071756663  ("The quc" — first 8 chars of test string)
    /// CT = A826FD8CE53B855F
    ///
    /// (Standard published example also appearing in Schneier
    /// *Applied Cryptography* §12.2.)
    #[test]
    fn tdes_three_key_canonical_vector() {
        let mut k1 = [0u8; 8];
        let mut k2 = [0u8; 8];
        let mut k3 = [0u8; 8];
        k1.copy_from_slice(&h("0123456789ABCDEF"));
        k2.copy_from_slice(&h("23456789ABCDEF01"));
        k3.copy_from_slice(&h("456789ABCDEF0123"));
        let mut p = [0u8; 8];
        p.copy_from_slice(&h("5468652071756663"));
        let expected = h("A826FD8CE53B855F");
        let tdes = TripleDes::new(&k1, &k2, &k3);
        let mut blk = p;
        tdes.encrypt_block(&mut blk);
        assert_eq!(&blk[..], &expected[..]);
        tdes.decrypt_block(&mut blk);
        assert_eq!(blk, p);
    }

    /// Free-function API matches the struct version.
    #[test]
    fn tdes_free_function_matches_struct() {
        let mut key24 = [0u8; 24];
        for i in 0..24 {
            key24[i] = i as u8;
        }
        let p = [0xAAu8; 8];
        let ct_free = encrypt_block(&key24, &p);
        let mut k1 = [0u8; 8];
        let mut k2 = [0u8; 8];
        let mut k3 = [0u8; 8];
        k1.copy_from_slice(&key24[0..8]);
        k2.copy_from_slice(&key24[8..16]);
        k3.copy_from_slice(&key24[16..24]);
        let tdes = TripleDes::new(&k1, &k2, &k3);
        let mut block = p;
        tdes.encrypt_block(&mut block);
        assert_eq!(block, ct_free);
    }

    /// 2-key 3DES (deprecated) also round-trips.
    #[test]
    fn tdes_two_key_round_trip() {
        let k1 = [0x01u8; 8];
        let k2 = [0x02u8; 8];
        let p = [0xDEu8; 8];
        let tdes = TripleDes::new_two_key(&k1, &k2);
        let mut blk = p;
        tdes.encrypt_block(&mut blk);
        assert_ne!(blk, p);
        tdes.decrypt_block(&mut blk);
        assert_eq!(blk, p);
    }
}
