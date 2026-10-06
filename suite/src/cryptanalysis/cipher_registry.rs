//! **Named-cipher registry** for the auto-attack CLI.
//!
//! Maps short string identifiers (`toyspn-2r`, `aes-2r`, …) to concrete
//! cipher instances + their structural metadata (S-box, round count,
//! block size).  The metadata is what lets `auto_attack` decide which
//! techniques are applicable to which cipher.
//!
//! ## Why this exists
//!
//! The cryptanalysis suite (boomerang, rectangle, sandwich, trail
//! search, …) is generic over the `BlockCipher` trait, but to run
//! attacks end-to-end you still need:
//!
//! 1. **A cipher instance** with a concrete key.
//! 2. **Its DDT / S-box / linear-layer** to feed the trail-search
//!    pipeline.
//! 3. **A canonical bench `(α, δ)`** for differential-attack demos.
//!
//! This module collects all three behind a single `RegisteredCipher`
//! enum so the CLI can say "`auto cryptanalysis on cipher X`" without
//! the user having to know how to wire each component.

use crate::cryptanalysis::aes::reduced::ReducedAes128;
use crate::cryptanalysis::boomerang::{BlockCipher, ToySpn};
use crate::cryptanalysis::sbox::Sbox;

/// A named cipher entry: identifier, instance, and structural metadata.
pub struct CipherEntry {
    /// Stable short identifier, e.g. `"toyspn-2r"`.
    pub name: &'static str,
    /// One-line description.
    pub description: &'static str,
    /// Block size in bytes.
    pub block_bytes: usize,
    /// Number of "rounds" — interpretation depends on the cipher
    /// (SubBytes-MixColumns-AddRoundKey rounds for AES, S-box rounds
    /// for ToySpn).
    pub rounds: usize,
    /// Whether this cipher is a 4×4-bit-S-box SPN that supports
    /// `differential_trail_search` directly.
    pub trail_searchable: bool,
    /// A canonical `(α, δ)` pair for differential demos (low-byte
    /// active by default).
    pub canonical_alpha: Vec<u8>,
    pub canonical_delta: Vec<u8>,
}

/// One of the supported cipher families.  Distinct from `CipherEntry`
/// — the entry is metadata, this enum carries the instance.
pub enum RegisteredCipher {
    ToySpn {
        cipher: ToySpn,
        sbox: Sbox,
        rounds: usize,
    },
    ReducedAes {
        cipher: ReducedAes128,
        rounds: usize,
    },
}

impl RegisteredCipher {
    /// Lookup a cipher by its registered name.  Returns `None` if the
    /// name is not in the catalog.
    pub fn from_name(name: &str) -> Option<Self> {
        let sbox_serpent_s0 = || {
            Sbox::new(
                4,
                4,
                vec![3, 8, 15, 1, 10, 6, 5, 11, 14, 13, 4, 2, 7, 0, 9, 12],
            )
            .unwrap()
        };
        let sbox_present = || {
            Sbox::new(
                4,
                4,
                vec![0xC, 5, 6, 0xB, 9, 0, 0xA, 0xD, 3, 0xE, 0xF, 8, 4, 7, 1, 2],
            )
            .unwrap()
        };
        match name {
            "toyspn-1r" => Some(Self::ToySpn {
                cipher: ToySpn::new(sbox_serpent_s0(), 1, 0xC0FFEE),
                sbox: sbox_serpent_s0(),
                rounds: 1,
            }),
            "toyspn-2r" => Some(Self::ToySpn {
                cipher: ToySpn::new(sbox_serpent_s0(), 2, 0xC0FFEE),
                sbox: sbox_serpent_s0(),
                rounds: 2,
            }),
            "toyspn-3r" => Some(Self::ToySpn {
                cipher: ToySpn::new(sbox_serpent_s0(), 3, 0xC0FFEE),
                sbox: sbox_serpent_s0(),
                rounds: 3,
            }),
            "toyspn-4r" => Some(Self::ToySpn {
                cipher: ToySpn::new(sbox_serpent_s0(), 4, 0xC0FFEE),
                sbox: sbox_serpent_s0(),
                rounds: 4,
            }),
            "toyspn-present-2r" => Some(Self::ToySpn {
                cipher: ToySpn::new(sbox_present(), 2, 0xC0FFEE),
                sbox: sbox_present(),
                rounds: 2,
            }),
            "aes-1r" => Some(Self::ReducedAes {
                cipher: ReducedAes128::new(&[0u8; 16], 1, true),
                rounds: 1,
            }),
            "aes-2r" => Some(Self::ReducedAes {
                cipher: ReducedAes128::new(&[0u8; 16], 2, true),
                rounds: 2,
            }),
            "aes-3r" => Some(Self::ReducedAes {
                cipher: ReducedAes128::new(&[0u8; 16], 3, true),
                rounds: 3,
            }),
            "aes-4r" => Some(Self::ReducedAes {
                cipher: ReducedAes128::new(&[0u8; 16], 4, true),
                rounds: 4,
            }),
            _ => None,
        }
    }

    /// Get the structural metadata for this cipher.
    pub fn entry(&self) -> CipherEntry {
        match self {
            Self::ToySpn { rounds, .. } => CipherEntry {
                name: match rounds {
                    1 => "toyspn-1r",
                    2 => "toyspn-2r",
                    3 => "toyspn-3r",
                    4 => "toyspn-4r",
                    _ => "toyspn",
                },
                description: "16-bit SPN: 4 × 4-bit S-boxes + PRESENT-style bit permutation",
                block_bytes: 2,
                rounds: *rounds,
                trail_searchable: true,
                canonical_alpha: vec![0x01, 0x00],
                canonical_delta: vec![0x01, 0x00],
            },
            Self::ReducedAes { rounds, .. } => CipherEntry {
                name: match rounds {
                    1 => "aes-1r",
                    2 => "aes-2r",
                    3 => "aes-3r",
                    4 => "aes-4r",
                    _ => "aes-Nr",
                },
                description: "AES-128 with reduced round count",
                block_bytes: 16,
                rounds: *rounds,
                trail_searchable: false, // AES S-box is 8-bit; trail search out of scope
                canonical_alpha: {
                    let mut v = vec![0u8; 16];
                    v[0] = 0x01;
                    v
                },
                canonical_delta: {
                    let mut v = vec![0u8; 16];
                    v[0] = 0x01;
                    v
                },
            },
        }
    }

    /// Encrypt one block.  Dispatches to the variant-specific
    /// implementation.
    pub fn encrypt(&self, block: &[u8]) -> Vec<u8> {
        match self {
            Self::ToySpn { cipher, .. } => <ToySpn as BlockCipher>::encrypt(cipher, block),
            Self::ReducedAes { cipher, .. } => {
                <ReducedAes128 as BlockCipher>::encrypt(cipher, block)
            }
        }
    }

    /// Decrypt one block.
    pub fn decrypt(&self, block: &[u8]) -> Vec<u8> {
        match self {
            Self::ToySpn { cipher, .. } => <ToySpn as BlockCipher>::decrypt(cipher, block),
            Self::ReducedAes { cipher, .. } => {
                <ReducedAes128 as BlockCipher>::decrypt(cipher, block)
            }
        }
    }

    /// Get the S-box if the cipher has a single user-visible one.
    pub fn sbox(&self) -> Option<Sbox> {
        match self {
            Self::ToySpn { sbox, .. } => Some(sbox.clone()),
            Self::ReducedAes { .. } => Some(aes_sbox()),
        }
    }
}

/// Wrap a `RegisteredCipher` so it satisfies the `BlockCipher` trait.
/// Needed because `RegisteredCipher`'s inherent `encrypt` returns
/// `Vec<u8>` but the trait method has a `&self` receiver and the
/// same signature.  Adapter avoids enum dispatch in attack hot loops.
impl BlockCipher for RegisteredCipher {
    fn block_bytes(&self) -> usize {
        self.entry().block_bytes
    }
    fn encrypt(&self, block: &[u8]) -> Vec<u8> {
        Self::encrypt(self, block)
    }
    fn decrypt(&self, block: &[u8]) -> Vec<u8> {
        Self::decrypt(self, block)
    }
}

/// Construct the AES S-box as an `Sbox` (the standard FIPS-197 table).
pub fn aes_sbox() -> Sbox {
    #[rustfmt::skip]
    let t: Vec<u32> = vec![
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
    Sbox::new(8, 8, t).unwrap()
}

/// List all registered cipher names.  For CLI `--list` discovery.
pub fn list_ciphers() -> Vec<&'static str> {
    vec![
        "toyspn-1r",
        "toyspn-2r",
        "toyspn-3r",
        "toyspn-4r",
        "toyspn-present-2r",
        "aes-1r",
        "aes-2r",
        "aes-3r",
        "aes-4r",
    ]
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// Every registered cipher is constructible and has a non-empty
    /// description.
    #[test]
    fn all_registered_ciphers_construct() {
        for name in list_ciphers() {
            let c = RegisteredCipher::from_name(name)
                .unwrap_or_else(|| panic!("cipher {} not registered", name));
            let e = c.entry();
            assert!(!e.description.is_empty());
            assert!(e.block_bytes > 0);
            assert!(e.rounds > 0);
        }
    }

    /// Unknown name returns None.
    #[test]
    fn unknown_cipher_name_returns_none() {
        assert!(RegisteredCipher::from_name("not-a-cipher").is_none());
    }

    /// Every registered cipher round-trips an arbitrary block.
    #[test]
    fn all_registered_ciphers_round_trip() {
        for name in list_ciphers() {
            let c = RegisteredCipher::from_name(name).unwrap();
            let block_bytes = c.entry().block_bytes;
            let p: Vec<u8> = (0..block_bytes).map(|i| i as u8).collect();
            let c_out = c.encrypt(&p);
            assert_eq!(c_out.len(), block_bytes);
            let p_back = c.decrypt(&c_out);
            assert_eq!(p_back, p, "round-trip failed for {}", name);
        }
    }

    /// The AES S-box helper returns the canonical FIPS-197 table —
    /// validated by checking `S(0) = 0x63`.
    #[test]
    fn aes_sbox_helper_matches_fips197() {
        let s = aes_sbox();
        assert_eq!(s.lookup(0), 0x63);
        assert_eq!(s.lookup(0x53), 0xed);
        // 8-bit / 8-bit, bijective.
        assert!(s.is_bijective());
    }

    /// Round trip via the `BlockCipher` trait impl.
    #[test]
    fn registered_cipher_via_blockcipher_trait() {
        let c = RegisteredCipher::from_name("toyspn-2r").unwrap();
        let p = [0xAB, 0xCD];
        let c_out = <RegisteredCipher as BlockCipher>::encrypt(&c, &p);
        let p_back = <RegisteredCipher as BlockCipher>::decrypt(&c, &c_out);
        assert_eq!(p_back, p.to_vec());
    }
}
